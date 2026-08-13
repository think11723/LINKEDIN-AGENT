"""In-process asyncio scheduler runner.

Started by the FastAPI lifespan; polls Mongo every ``poll_interval``
seconds for due jobs. Each job is owned by a Firebase UID and runs
with that user's LinkedIn credentials.

This is a single-process runner by design. Restart-safe (jobs persist
in Mongo) but not horizontally scalable. Migrating to Celery/Redis is
intentionally deferred.

Phase 8B P1-9: the publish HTTP call and person-urn resolution were
extracted into ``backend.app.services.publishing`` so the on-demand
``POST /api/v1/drafts/{id}/publish`` endpoint and the scheduler
share the exact same code path.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.app.core.security import get_firebase_app  # noqa: F401  (ensures init)
from backend.app.db.mongo import get_database
from backend.app.repositories import (
    AuditRepository,
    DraftRepository,
    LinkedInRepository,
    SchedulerRepository,
)
from backend.app.services.publishing import (
    _publish_ugc_post,
    resolve_person_urn,
)

logger = logging.getLogger(__name__)


class SchedulerRunner:
    def __init__(self, *, poll_interval: float = 5.0) -> None:
        self.poll_interval = poll_interval
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="scheduler-runner")
        logger.info("Scheduler runner started.")

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
        logger.info("Scheduler runner stopped.")

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("Scheduler tick failed: %s", exc)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.poll_interval
                )
            except asyncio.TimeoutError:
                pass

    async def _tick(self) -> None:
        scheduler = SchedulerRepository(get_database())
        audit = AuditRepository(get_database())
        drafts = DraftRepository(get_database())
        linkedin = LinkedInRepository(get_database())

        now = datetime.now(timezone.utc)
        job = await scheduler.claim_due_job(now)
        if not job:
            return

        user_id = job["user_id"]
        await audit.log(
            user_id=user_id,
            event_type="JOB_DISPATCHED",
            description=job.get("title", ""),
            details={"job_id": job["_id"]},
        )

        tokens = await linkedin.get_decrypted_tokens(user_id)
        if not tokens or not tokens.get("access_token"):
            await scheduler.fail_job(
                job["_id"],
                error="LINKEDIN_NOT_CONNECTED",
                retry=False,
            )
            await audit.log(
                user_id=user_id,
                event_type="JOB_FAILED",
                description=job.get("title", ""),
                details={"job_id": job["_id"], "reason": "LINKEDIN_NOT_CONNECTED"},
            )
            return

        # Phase 8B P1-9 — share the publish path with the on-demand
        # endpoint. Same code, same P0-8 log hygiene.
        person_urn = job.get("person_urn") or (
            tokens.get("person_urn") or await resolve_person_urn(tokens["access_token"])
        )
        if not person_urn:
            await scheduler.fail_job(
                job["_id"],
                error="LINKEDIN_URN_UNRESOLVED",
                retry=False,
            )
            await audit.log(
                user_id=user_id,
                event_type="JOB_FAILED",
                description=job.get("title", ""),
                details={"job_id": job["_id"], "reason": "LINKEDIN_URN_UNRESOLVED"},
            )
            return

        success, linkedin_post_id, err = await _publish_ugc_post(
            access_token=tokens["access_token"],
            person_urn=person_urn,
            title=job.get("title", ""),
            content=job.get("content", ""),
            hashtags=job.get("hashtags") or [],
        )
        if not success:
            retry_count = int(job.get("retry_count", 0)) + 1
            max_retries = int(job.get("max_retries", 3))
            retry = retry_count < max_retries
            await scheduler.fail_job(
                job["_id"],
                error="LINKEDIN_PUBLISH_FAILED",
                retry=retry,
            )
            await audit.log(
                user_id=user_id,
                event_type="JOB_FAILED",
                description=job.get("title", ""),
                details={
                    "job_id": job["_id"],
                    "retry": retry,
                    "reason": err or "LINKEDIN_PUBLISH_FAILED",
                },
            )
            return

        await scheduler.complete_job(job["_id"], linkedin_post_id=linkedin_post_id)
        if job.get("draft_id"):
            await drafts.mark_published(
                user_id, job["draft_id"], linkedin_post_id=linkedin_post_id
            )
        await audit.log(
            user_id=user_id,
            event_type="JOB_COMPLETED",
            description=job.get("title", ""),
            details={"job_id": job["_id"], "linkedin_post_id": linkedin_post_id},
        )