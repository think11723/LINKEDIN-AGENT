"""In-process source-job runner — Phase 8D / URL-to-LinkedIn feature.

Mirrors ``backend/app/services/scheduler_runner.py`` exactly:

* An ``asyncio.Task`` started in the FastAPI lifespan.
* ``_tick()`` polls Mongo every ``poll_interval`` seconds for the next
  ``queued`` source-job and atomically claims it.
* The per-job body fetches + analyzes the URL via the adapter layer
  and runs the existing writer + reviewer pipeline with the
  ``research_package`` seam.

Single-process runner by design — restart-safe via Mongo. Two
backend instances would double-process jobs; the atomic claim makes
this safe-ish, but throughput / ownership is undefined. Revisit only
when horizontal scaling is real.

On startup, ``recover_stale_running`` flips ``running`` jobs older than
``SOURCE_FETCH_TOTAL_TIMEOUT_SECONDS`` back to ``queued`` so a crashed
process does not strand jobs permanently.

Retries: transient failures (``5xx``, timeout, rate-limit) are retried
up to ``max_retries`` times. ``SourceBlockedError`` (SSRF) is **never**
retried — the URL is rejected and the job is marked failed.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from backend.app.core.config import get_settings
from backend.app.db.mongo import get_database
from backend.app.repositories import (
    ApprovalRepository,
    AuditRepository,
    DraftRepository,
    SourceJobRepository,
    UserRepository,
)
from backend.app.services.sources import (
    SourceBlockedError,
    SourceFetchError,
    SourcePackage,
    resolve_adapter,
)

logger = logging.getLogger(__name__)


class SourceJobRunner:
    """Polls ``source_jobs`` for ``queued`` rows and executes them.

    Concurrency:
      * A single ``asyncio.Semaphore`` caps in-flight jobs at
        ``MAX_CONCURRENCY`` (default 2). The tick schedules new jobs
        while there is headroom.
      * ``_tick()`` swallows exceptions so a transient failure in one
        tick doesn't kill the loop.
    """

    #: Cap on simultaneously-running jobs.
    MAX_CONCURRENCY = 2

    def __init__(self, *, poll_interval: float = 2.0) -> None:
        self.poll_interval = poll_interval
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENCY)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="source-job-runner")
        logger.info("SourceJobRunner started.")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        self._task = None
        logger.info("SourceJobRunner stopped.")

    async def _run(self) -> None:
        """Main loop: tick every ``poll_interval`` seconds."""
        # Recover stale running jobs (crash recovery) before the first tick.
        try:
            settings = get_settings()
            await self._recover_stale(settings.source_fetch_total_timeout_seconds)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Initial stale-job recovery failed: %s", exc)

        while not self._stop_event.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("SourceJobRunner tick failed: %s", exc)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.poll_interval
                )
            except asyncio.TimeoutError:
                pass

    # ------------------------------------------------------------------
    # Tick / per-job execution
    # ------------------------------------------------------------------

    async def _recover_stale(self, total_timeout_seconds: float) -> None:
        """Reset ``running`` jobs older than the per-job timeout to ``queued``.

        Called once at startup. Mirrors the scheduler-runner recovery
        helper (P0-3 in Phase 8A).
        """
        db = get_database()
        repo = SourceJobRepository(db)
        n = await repo.recover_stale_running(
            older_than_seconds=int(total_timeout_seconds)
        )
        if n:
            logger.warning(
                "Recovered %d stale source-job(s) from a previous process.", n
            )

    # ------------------------------------------------------------------
    # Transient-retry policy (P1)
    # ------------------------------------------------------------------
    # Only the codes listed in the plan retry. Permanent failures
    # (SourceBlockedError, repository_not_found, github_unauthorized,
    # github_forbidden, dmca, bad_response, http_4xx_unexpected) skip
    # the loop and are surfaced to the user on first attempt.
    _TRANSIENT_RETRY_CODES: frozenset = frozenset(
        {"http_5xx", "timeout", "github_rate_limited"}
    )
    _MAX_RETRIES: int = 2  # total of 3 attempts (initial + 2 retries)
    _RETRY_BACKOFF_SECONDS: float = 1.0

    async def _fetch_with_retry(
        self,
        adapter: Any,
        url: str,
        *,
        request_id: str,
    ) -> SourcePackage:
        """Call ``adapter.fetch`` with transient-error retry.

        Retries up to ``_MAX_RETRIES`` times with a fixed backoff for
        ``SourceFetchError`` instances whose ``code`` is in
        ``_TRANSIENT_RETRY_CODES``. Other errors propagate immediately.
        """
        last_exc: Optional[SourceFetchError] = None
        for attempt in range(self._MAX_RETRIES + 1):
            try:
                return await adapter.fetch(url, request_id=request_id)
            except SourceBlockedError:
                # SSRF is a security concern — never retried.
                raise
            except SourceFetchError as exc:
                if exc.code not in self._TRANSIENT_RETRY_CODES:
                    raise
                last_exc = exc
                if attempt >= self._MAX_RETRIES:
                    # Out of attempts — surface the last transient error.
                    raise
                logger.info(
                    "source-job fetch attempt %d/%d transient error code=%s; "
                    "retrying in %.1fs",
                    attempt + 1,
                    self._MAX_RETRIES + 1,
                    exc.code,
                    self._RETRY_BACKOFF_SECONDS,
                )
                await asyncio.sleep(self._RETRY_BACKOFF_SECONDS)
        # Unreachable: the loop returns or raises on the last iteration.
        assert last_exc is not None
        raise last_exc

    async def _tick(self) -> None:
        """Pick up at most one queued job and schedule it.

        Multiple jobs can run concurrently thanks to the semaphore;
        this tick just tries to fill available headroom once.
        """
        # If the semaphore is fully consumed, skip this tick.
        if self._semaphore.locked() and self._semaphore._value <= 0:  # type: ignore[attr-defined]
            return

        async with self._semaphore:
            db = get_database()
            repo = SourceJobRepository(db)
            job = await repo.claim_next_queued()
            if not job:
                return
            # Process the job while still holding the semaphore slot —
            # released on exit.
            await self._execute_job(job, repo)

    async def _execute_job(self, job: dict, repo: SourceJobRepository) -> None:
        """Run a claimed job end-to-end."""
        job_id = job["job_id"]
        user_id = job["user_id"]
        url = job["url"]
        settings = get_settings()

        try:
            await asyncio.wait_for(
                self._run_job_inner(job, repo, settings),
                timeout=settings.source_fetch_total_timeout_seconds,
            )
        except asyncio.TimeoutError:
            await repo.mark_failed(
                job_id=job_id,
                error=(
                    f"Job exceeded total timeout of "
                    f"{settings.source_fetch_total_timeout_seconds}s."
                ),
                error_code="total_timeout",
                stage=repo.STAGE_WRITING,
            )
            await self._audit(
                user_id=user_id,
                event_type="URL_DRAFT_FAILED",
                description="URL-generation job timed out",
                details={
                    "job_id": job_id,
                    "url": url,
                    "stage": repo.STAGE_WRITING,
                    "error_code": "total_timeout",
                    "total_timeout_seconds": settings.source_fetch_total_timeout_seconds,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Source-job %s crashed", job_id)
            await repo.mark_failed(
                job_id=job_id,
                error="Internal server error.",
                error_code="runner_crash",
                stage=None,
            )
            await self._audit(
                user_id=user_id,
                event_type="URL_DRAFT_FAILED",
                description="URL-generation runner crashed",
                details={
                    "job_id": job_id,
                    "url": url,
                    "error_code": "runner_crash",
                    "exception_type": exc.__class__.__name__,
                },
            )

    async def _run_job_inner(
        self,
        job: dict,
        repo: SourceJobRepository,
        settings,
    ) -> None:
        """The actual job body."""
        job_id = job["job_id"]
        user_id = job["user_id"]
        url = job["url"]
        db = get_database()
        drafts = DraftRepository(db)
        approvals = ApprovalRepository(db)
        audit = AuditRepository(db)
        users = UserRepository(db)

        # ------------------------------------------------------------------
        # Stage 1: fetch + analyze via the adapter.
        # ------------------------------------------------------------------
        await repo.set_stage(job_id, repo.STAGE_FETCHING)
        await self._audit(
            user_id=user_id,
            event_type="SOURCE_FETCH_STARTED",
            description="Source fetch started",
            details={"job_id": job_id, "url": url, "adapter": job.get("adapter")},
        )

        adapter = resolve_adapter(url)
        request_id = job.get("request_id", "")
        try:
            package: SourcePackage = await self._fetch_with_retry(
                adapter, url, request_id=request_id
            )
        except SourceBlockedError as exc:
            # SSRF — never retried.
            await repo.mark_failed(
                job_id=job_id,
                error=exc.message,
                error_code=exc.code,
                stage=repo.STAGE_FETCHING,
            )
            await self._audit(
                user_id=user_id,
                event_type="SOURCE_FETCH_BLOCKED",
                description="Source fetch blocked by SSRF guard",
                details={
                    "job_id": job_id,
                    "url": url,
                    "reason": exc.code,
                    "host": exc.details.get("host"),
                    "resolved_ip": exc.details.get("ip"),
                },
            )
            return
        except SourceFetchError as exc:
            # Other fetch errors (unavailable, paywall, etc.) — fail.
            await repo.mark_failed(
                job_id=job_id,
                error=exc.message,
                error_code=exc.code,
                stage=repo.STAGE_FETCHING,
            )
            await self._audit(
                user_id=user_id,
                event_type="SOURCE_FETCH_FAILED",
                description="Source fetch failed",
                details={
                    "job_id": job_id,
                    "url": url,
                    "error_code": exc.code,
                },
            )
            return

        await repo.set_stage(job_id, repo.STAGE_ANALYZING)
        await self._audit(
            user_id=user_id,
            event_type="SOURCE_ANALYZED",
            description="Source analyzed",
            details={
                "job_id": job_id,
                "url": url,
                "adapter": adapter.name,
                "analyzer": package.metadata.get("analyzer", "deterministic"),
                "key_fact_count": len(package.key_facts),
                "truncated": bool(package.metadata.get("truncated", False)),
            },
        )

        # ------------------------------------------------------------------
        # Stage 2: write + review via the existing workflow.
        # ------------------------------------------------------------------
        await repo.set_stage(job_id, repo.STAGE_WRITING)

        # Phase 8 — source-quality gate. A WEAK source does NOT
        # generate a hallucinated LinkedIn post. We mark the job
        # failed with a user-safe error and audit the reason.
        from backend.app.services.sources.quality import (
            SourceQuality,
            evaluate_source_quality,
            is_weak_or_failed,
        )
        quality, quality_reason = evaluate_source_quality(package)
        package.metadata["quality"] = quality.value
        package.metadata["quality_reason"] = quality_reason
        if is_weak_or_failed(quality):
            await repo.mark_failed(
                job_id=job_id,
                error="This source doesn't contain enough readable information to create a grounded LinkedIn post.",
                error_code="source_too_weak",
                stage=repo.STAGE_ANALYZING,
            )
            await self._audit(
                user_id=user_id,
                event_type="SOURCE_PREVIEW_WEAK",
                description="Source rejected by quality gate",
                details={
                    "url": url,
                    "adapter": getattr(adapter, "name", "unknown"),
                    "source_type": package.metadata.get("source_type"),
                    "quality": quality.value,
                    "reason": quality_reason,
                    "body_char_count": int(
                        package.metadata.get("body_char_count") or 0
                    ),
                    "job_id": job_id,
                    "request_id": request_id,
                },
            )
            return
        research_package = adapter.to_research_package(package)

        # Phase 5 — build the structured source context the
        # Writer/Reviewer consume for source-aware generation. The
        # async job runner does not take a framing hint from the
        # user; one can be passed via ``intent`` on the job row.
        from shared.schemas import GenerateContentRequest
        from backend.app.api.v1.content import _build_source_context

        source_type = package.metadata.get("source_type") or "generic_webpage"
        source_context = _build_source_context(
            package=package,
            source_type=source_type,
            canonical_url=(
                package.metadata.get("canonical_url") or url
            ),
            framing_hint=job.get("intent") or None,
        )

        request = GenerateContentRequest(
            topic=package.metadata.get("topic_hint") or package.title or "",
            image_path=None,
        )

        # Lazy import — WorkflowService pulls in the LangGraph stack.
        from backend.app.services.workflow_service import WorkflowService
        from backend.app.api.v1.content import _persist_result
        from backend.app.core.security import AuthenticatedUser

        service = WorkflowService()
        try:
            # ``WorkflowService.generate_content`` is async (the
            # LangGraph it runs contains async Writer/Reviewer nodes
            # that await the LLM). ``await`` is required; without
            # it, ``workflow_result`` is a coroutine and the next
            # access would raise "'coroutine' object has no
            # attribute 'final_post'".
            workflow_result = await service.generate_content(
                request,
                research_package=research_package,
                source=source_context,
            )
        except Exception as exc:  # noqa: BLE001
            # The global error envelope would have produced a 500;
            # here we just fail the job with a user-safe message.
            await repo.mark_failed(
                job_id=job_id,
                error="Workflow execution failed.",
                error_code="workflow_error",
                stage=repo.STAGE_WRITING,
            )
            await self._audit(
                user_id=user_id,
                event_type="URL_DRAFT_FAILED",
                description="Workflow execution failed",
                details={
                    "job_id": job_id,
                    "url": url,
                    "stage": repo.STAGE_WRITING,
                    "error_code": "workflow_error",
                    "exception_type": exc.__class__.__name__,
                },
            )
            return

        await repo.set_stage(job_id, repo.STAGE_REVIEWING)
        await repo.set_stage(job_id, repo.STAGE_PERSISTING)

        # ------------------------------------------------------------------
        # Stage 3: persist + audit.
        # ------------------------------------------------------------------
        # We re-use the existing _persist_result helper so the URL-mode
        # and topic-mode drafts share one persistence path. The helper
        # produces a GenerateContentResponse with the embedded draft
        # block; we only need its ``draft_id`` + ``approval_token`` for
        # the job record.
        response = await _persist_result(
            user=AuthenticatedUser(
                uid=user_id,
                email=None,
                email_verified=False,
                name=None,
                picture=None,
            ),
            workflow_result=workflow_result,
            drafts=drafts,
            approvals=approvals,
            audit=audit,
            users=users,
            source_url=url,
            source_metadata=package.metadata,
        )

        source_summary = {
            "title": package.title,
            "summary": package.summary,
            "key_facts": package.key_facts,
            "adapter": adapter.name,
            "truncated": bool(package.metadata.get("truncated", False)),
        }
        await repo.mark_succeeded(
            job_id=job_id,
            draft_id=response.draft_id or "",
            approval_token=response.approval_token,
            source_summary=source_summary,
            source_metadata=package.metadata,
        )
        await self._audit(
            user_id=user_id,
            event_type="URL_DRAFT_SUCCEEDED",
            description="URL draft generated",
            details={
                "job_id": job_id,
                "draft_id": response.draft_id,
                "url": url,
                "adapter": adapter.name,
                "analyst": package.metadata.get("analyzer", "deterministic"),
            },
        )

    async def _audit(
        self,
        *,
        user_id: str,
        event_type: str,
        description: str,
        details: dict,
    ) -> None:
        db = get_database()
        audit = AuditRepository(db)
        try:
            await audit.log(
                user_id=user_id,
                event_type=event_type,
                description=description,
                details=details,
            )
        except Exception as exc:  # noqa: BLE001
            # Audit failures must never block the job.
            logger.warning(
                "Audit log failed for %s: %s", event_type, exc
            )


__all__ = ["SourceJobRunner"]