"""Content API endpoints for the web application.

Now requires Firebase authentication. Generated drafts are persisted in
MongoDB owned by the authenticated user, and ``draft_id`` +
``approval_token`` are surfaced at the top level of the response.

Phase 8D / URL-to-LinkedIn adds two async-job endpoints:

* ``POST /api/v1/content/generate-from-url`` — synchronous SSRF
  pre-check, then enqueue a background job and return 202.
* ``GET  /api/v1/content/generate-from-url/{job_id}`` — poll the job.
  Returns 404 for unknown / cross-user jobs (never 403).

The actual fetch + analysis + writer + reviewer pipeline runs in
``backend/app/services/source_job_runner.py``.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from backend.app.api.deps import (
    get_approval_repository,
    get_audit_repository,
    get_draft_repository,
    get_source_job_repository,
    get_user_repository,
)
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.models.source import (
    GenerateFromUrlAcceptedResponse,
    GenerateFromUrlJobResponse,
    GenerateFromUrlRequest,
    SourceSummary,
)
from backend.app.repositories import (
    ApprovalRepository,
    AuditRepository,
    DraftRepository,
    SourceJobRepository,
    UserRepository,
)
from backend.app.services.sources import (
    GITHUB_ALLOWLIST,
    SourceBlockedError,
    SourceFetchError,
    resolve_adapter,
    validate_url,
)
from backend.app.services.workflow_service import WorkflowService
from shared.schemas import GenerateContentRequest, GenerateContentResponse

router = APIRouter(prefix="/api/v1/content", tags=["content"])


def get_workflow_service() -> WorkflowService:
    return WorkflowService()


# ---------------------------------------------------------------------------
# Topic-mode endpoint (existing — unchanged behaviour)
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=GenerateContentResponse)
async def generate_content(
    payload: GenerateContentRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service),
    drafts: DraftRepository = Depends(get_draft_repository),
    approvals: ApprovalRepository = Depends(get_approval_repository),
    audit: AuditRepository = Depends(get_audit_repository),
    users: UserRepository = Depends(get_user_repository),
) -> GenerateContentResponse:
    """Generate a LinkedIn draft using the existing LangGraph workflow.

    The result is persisted in MongoDB owned by the authenticated user.

    Phase 8A / P0-1: the global exception handler in
    ``backend.app.core.error_handlers`` produces a safe envelope for any
    uncaught exception — never ``str(exc)``.
    """
    # WorkflowService raises HTTPException for empty topics; re-raise.
    # ``WorkflowService.generate_content`` is async because the
    # LangGraph it runs contains async nodes (Writer and Reviewer
    # await the LLM). The FastAPI handler is already async, so
    # ``await`` is safe and natural.
    workflow_result = await service.generate_content(payload)

    response = workflow_result
    try:
        response = await _persist_result(
            user=user,
            workflow_result=workflow_result,
            drafts=drafts,
            approvals=approvals,
            audit=audit,
            users=users,
            source_url=None,
            source_metadata=None,
        )
    except Exception:  # pragma: no cover - defensive
        # Persistence failure must not mask the workflow output. The
        # global exception handler logs the traceback server-side; here
        # we just continue and return the workflow result unchanged.
        import logging
        logging.getLogger(__name__).exception(
            "Persistence failed for generated draft; returning workflow result."
        )

    return response


# ---------------------------------------------------------------------------
# URL-mode endpoints (Phase 8D / URL-to-LinkedIn)
# ---------------------------------------------------------------------------


@router.post(
    "/generate-from-url",
    response_model=GenerateFromUrlAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_from_url(
    payload: GenerateFromUrlRequest,
    response: Response,
    user: AuthenticatedUser = Depends(get_current_user),
    jobs: SourceJobRepository = Depends(get_source_job_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> GenerateFromUrlAcceptedResponse:
    """Enqueue a URL-based generation job. Returns 202 + ``job_id``.

    Behaviour:
      * Synchronous SSRF pre-check via ``validate_url`` so obvious
        garbage (bad scheme, userinfo, port, IDN failures, private/loopback
        IPs) returns 400 immediately with no job row created.
      * Per-user active-job cap (default 3) → 429.
      * Per-user rate limit (default 10/hour, Mongo-counted) → 429.
      * Adapter hint — ``github.com``/``api.github.com``/``raw.githubusercontent.com``
        is detected synchronously and recorded on the job.
    """
    # ------------------------------------------------------------------
    # Synchronous SSRF pre-check (cheap; obvious garbage 400s immediately).
    # ------------------------------------------------------------------
    try:
        parsed = validate_url(payload.url, allow_hosts=None)
    except SourceBlockedError as exc:
        # Per plan §9: SSRF-blocked URLs return 400 *synchronously* with
        # an audit row, no job row created.
        await audit.log(
            user_id=user.uid,
            event_type="SOURCE_FETCH_BLOCKED",
            description="URL rejected by SSRF pre-check",
            details={"url": payload.url, "reason": exc.code},
        )
        raise HTTPException(status_code=400, detail=exc.message) from exc

    # ------------------------------------------------------------------
    # Per-user caps.
    # ------------------------------------------------------------------
    from backend.app.core.config import get_settings

    settings = get_settings()
    active = await jobs.count_active_for_user(user.uid)
    if active >= settings.source_jobs_max_active_per_user:
        raise HTTPException(
            status_code=429,
            detail=(
                f"You have {active} active URL-generation job(s); "
                f"max {settings.source_jobs_max_active_per_user}."
            ),
        )
    recent = await jobs.count_recent_for_user(
        user.uid, window=timedelta(hours=1)
    )
    if recent >= settings.source_jobs_rate_per_hour:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded: {settings.source_jobs_rate_per_hour} "
                f"URL-generation jobs per hour."
            ),
        )

    # ------------------------------------------------------------------
    # Adapter hint (no network call here — cheap).
    # ------------------------------------------------------------------
    adapter_hint: Optional[str] = None
    try:
        # Validate against the GitHub allowlist (cheap path).
        validate_url(payload.url, allow_hosts=GITHUB_ALLOWLIST)
        adapter_hint = "github"
    except SourceBlockedError:
        # Not GitHub-shaped → web-page catch-all.
        adapter_hint = "webpage"

    # ------------------------------------------------------------------
    # Persist the job.
    # ------------------------------------------------------------------
    doc = await jobs.create(
        user_id=user.uid,
        url=payload.url,
        adapter=adapter_hint,
        intent=payload.intent,
        tone=payload.tone,
        audience=payload.audience,
    )
    await audit.log(
        user_id=user.uid,
        event_type="URL_DRAFT_REQUESTED",
        description="URL-based draft requested",
        details={
            "url": payload.url,
            "host": parsed.hostname or "",
            "adapter_hint": adapter_hint,
            "job_id": doc["job_id"],
            "request_id": doc["request_id"],
        },
    )

    # Tell clients (and proxies) not to cache this 202.
    response.headers["Cache-Control"] = "no-store"

    return GenerateFromUrlAcceptedResponse(
        job_id=doc["job_id"],
        status=doc["status"],
        request_id=doc["request_id"],
        poll_url=f"/api/v1/content/generate-from-url/{doc['job_id']}",
    )


@router.get(
    "/generate-from-url/{job_id}",
    response_model=GenerateFromUrlJobResponse,
)
async def get_generate_from_url_job(
    user: AuthenticatedUser = Depends(get_current_user),
    jobs: SourceJobRepository = Depends(get_source_job_repository),
    response: Response = None,  # type: ignore[assignment]
) -> GenerateFromUrlJobResponse:
    """Poll a URL-generation job. 404 for unknown / cross-user jobs."""
    if response is not None:
        response.headers["Cache-Control"] = "no-store"
    job_id = Path(..., description="Job id returned by /generate-from-url")
    return await _get_job_response(job_id=job_id, user_id=user.uid, jobs=jobs)


async def _get_job_response(
    *,
    job_id: str,
    user_id: str,
    jobs: SourceJobRepository,
) -> GenerateFromUrlJobResponse:
    doc = await jobs.get(job_id, user_id)
    if doc is None:
        # 404 (not 403) — never leak whether a job exists for another user.
        raise HTTPException(status_code=404, detail="Job not found")
    response = SourceJobRepository.to_response(doc)
    # Project source_summary into a typed SourceSummary.
    ss = response.get("source_summary") or None
    typed_summary = None
    if ss:
        typed_summary = SourceSummary(
            title=ss.get("title", ""),
            summary=ss.get("summary", ""),
            key_facts=ss.get("key_facts") or [],
            adapter=ss.get("adapter") or response.get("adapter"),
            truncated=bool(ss.get("truncated", False)),
        )
    return GenerateFromUrlJobResponse(
        job_id=response["job_id"],
        status=response["status"],
        stage=response.get("stage"),
        url=response.get("url") or "",
        adapter=response.get("adapter"),
        created_at=response.get("created_at"),
        started_at=response.get("started_at"),
        finished_at=response.get("finished_at"),
        draft_id=response.get("draft_id"),
        approval_token=response.get("approval_token"),
        source_summary=typed_summary,
        source_metadata=response.get("source_metadata"),
        request_id=response.get("request_id"),
        error=response.get("error"),
        error_code=response.get("error_code"),
    )


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


async def _persist_result(
    *,
    user: AuthenticatedUser,
    workflow_result: GenerateContentResponse,
    drafts: DraftRepository,
    approvals: ApprovalRepository,
    audit: AuditRepository,
    users: Optional[UserRepository] = None,
    source_url: Optional[str] = None,
    source_metadata: Optional[dict] = None,
) -> GenerateContentResponse:
    """Persist the generated draft + create an approval token owned by the user.

    Phase 8D: ``source_url`` and ``source_metadata`` are only set on
    the persisted draft when supplied (URL mode). Topic mode passes
    ``None`` for both — the repository writes no ``source_*`` keys and
    existing topic-mode drafts are unchanged.
    """
    if not workflow_result.final_post:
        return workflow_result

    draft_id = uuid.uuid4().hex
    approval = await approvals.create(user_id=user.uid, draft_id=draft_id)

    # Phase 9: normalize the post through the canonical LinkedIn content
    # normalizer. This is the FINAL defense layer — the Writer and
    # Reviewer also normalize, but if any path bypasses them (a future
    # agent, a fallback provider, a manual edit via the approval
    # endpoint) we still persist LinkedIn-native content. The Draft
    # Viewer, approval email, and LinkedIn publishing all consume the
    # normalized fields directly with no further cleanup.
    from utils.linkedin_content import normalize_linkedin_post

    _normalized = normalize_linkedin_post(
        title=workflow_result.final_post.title or workflow_result.topic,
        content=workflow_result.final_post.content or "",
        hashtags=workflow_result.final_post.hashtags or [],
    )
    title = _normalized.title
    content = _normalized.content
    hashtags = list(_normalized.hashtags)

    review_score = None
    review_feedback = None
    if workflow_result.review_scores:
        try:
            review_score = int(workflow_result.review_scores.get("overall", 0)) or None
        except (TypeError, ValueError):
            review_score = None
    if workflow_result.review_feedback:
        review_feedback = str(workflow_result.review_feedback)

    research_summary = None
    if workflow_result.metadata:
        package = workflow_result.metadata.get("research_package") or {}
        research_summary = package.get("summary")

    # Phase 8A / P0-5: persist the provider/model used by writer + reviewer.
    meta = dict(workflow_result.metadata or {})
    llm_meta: dict[str, str] = {}
    if "writer_provider" in meta:
        llm_meta["writer_provider"] = meta["writer_provider"]
    if "writer_model" in meta:
        llm_meta["writer_model"] = meta["writer_model"]
    if "reviewer_provider" in meta:
        llm_meta["reviewer_provider"] = meta["reviewer_provider"]
    if "reviewer_model" in meta:
        llm_meta["reviewer_model"] = meta["reviewer_model"]
    # Phase 8D / URL-to-LinkedIn: analyst provider/model when present.
    if "analyst_provider" in meta:
        llm_meta["analyst_provider"] = meta["analyst_provider"]
    if "analyst_model" in meta:
        llm_meta["analyst_model"] = meta["analyst_model"]

    draft_doc = await drafts.create(
        user_id=user.uid,
        draft_id=draft_id,
        topic=workflow_result.topic,
        title=title,
        content=content,
        hashtags=hashtags,
        image_path=workflow_result.final_post.image_path,
        review_score=review_score,
        review_feedback=review_feedback,
        research_summary=research_summary,
        status="draft" if not workflow_result.approved else "approved",
        approval_token=approval["_id"],
        metadata={"llm": llm_meta} if llm_meta else None,
        source_url=source_url,
        source_metadata=source_metadata,
    )

    await audit.log(
        user_id=user.uid,
        event_type="DRAFT_GENERATED",
        description=title,
        details={
            "draft_id": draft_id,
            "approved": workflow_result.approved,
            "iterations": workflow_result.iterations,
            "source_url": source_url,
        },
    )

    # Approval-email notification. Only when the user has opted in
    # via ``approval_mode == "email"`` and provided a notification
    # address. Failure here must NEVER prevent the draft from being
    # returned to the caller — the email is best-effort and is
    # recorded as APPROVAL_EMAIL_SENT / APPROVAL_EMAIL_FAILED.
    if users is not None:
        await _maybe_send_approval_email(
            users=users,
            audit=audit,
            user_id=user.uid,
            draft_id=draft_id,
            draft_title=title,
            draft_topic=workflow_result.topic,
            approval_token=approval["_id"],
        )

    payload = workflow_result.model_dump(exclude_none=True)
    payload["draft_id"] = draft_id
    payload["approval_token"] = approval["_id"]
    payload["draft"] = {
        "id": draft_doc["_id"],
        "title": title,
        "topic": draft_doc.get("topic"),
        "content": content,
        "hashtags": hashtags,
        "status": draft_doc.get("status"),
        "approval_token": approval["_id"],
        "created_at": (
            draft_doc["created_at"].isoformat()
            if hasattr(draft_doc.get("created_at"), "isoformat")
            else draft_doc.get("created_at")
        ),
        "source_url": source_url,
        "source_metadata": source_metadata,
    }
    payload["source_url"] = source_url
    payload["source_metadata"] = source_metadata
    return GenerateContentResponse.model_validate(payload)


async def _maybe_send_approval_email(
    *,
    users: "UserRepository",
    audit: "AuditRepository",
    user_id: str,
    draft_id: str,
    draft_title: str,
    draft_topic: str,
    approval_token: str,
) -> None:
    """Send an approval-email notification if the user has opted in.

    Behaviour:
      * If ``preferences.approval_mode != "email"`` → no email.
      * If no ``preferences.notification_email`` is set → no email.
      * If SMTP is not configured on the server → no email (audit
        event records the reason).
      * If SMTP send fails → ``APPROVAL_EMAIL_FAILED`` audit event
        with the SMTP error class name and the body fingerprint.
      * If SMTP send succeeds → ``APPROVAL_EMAIL_SENT`` audit event
        with the body fingerprint.

    The email body itself is NEVER logged — only its SHA-256[:16]
    fingerprint. The approval token is never echoed into any log.
    """
    import hashlib

    from backend.app.core.config import get_settings
    from backend.app.services.email import (
        build_approval_email_body,
        send_email,
    )

    user_doc = await users.get_preferences(user_id) or {}
    prefs = user_doc.get("preferences") or {}

    # IMPORTANT: every skip path writes an APPROVAL_EMAIL_SKIPPED
    # audit event so the operator has diagnostic visibility. The
    # previous implementation silently returned when preferences were
    # missing or approval_mode was not 'email', leaving the user with
    # no observable reason for the missing email.
    if prefs.get("approval_mode") != "email":
        await audit.log(
            user_id=user_id,
            event_type="APPROVAL_EMAIL_SKIPPED",
            description=draft_title,
            details={
                "reason": "approval_mode_not_email",
                "approval_mode": prefs.get("approval_mode"),
                "preferences_present": bool(prefs),
                "draft_id": draft_id,
            },
        )
        return

    to_address = prefs.get("notification_email")
    if not to_address:
        await audit.log(
            user_id=user_id,
            event_type="APPROVAL_EMAIL_SKIPPED",
            description=draft_title,
            details={
                "reason": "notification_email_not_set",
                "draft_id": draft_id,
            },
        )
        return

    settings = get_settings()
    approval_url = (
        f"{settings.frontend_url.rstrip('/')}/settings"
        f"?approval_token={approval_token}"
    )
    subject = f"Approval needed: {draft_title[:80]}"
    body = build_approval_email_body(
        draft_title=draft_title,
        draft_topic=draft_topic,
        approval_token=approval_token,
        approval_url=approval_url,
    )

    recipient_fp = hashlib.sha256(
        to_address.encode("utf-8")
    ).hexdigest()[:16]

    result = await send_email(
        to=to_address,
        subject=subject,
        body=body,
    )

    if result.success:
        await audit.log(
            user_id=user_id,
            event_type="APPROVAL_EMAIL_SENT",
            description=draft_title,
            details={
                "draft_id": draft_id,
                "approval_token": approval_token,
                "body_fingerprint_sha256_16": result.fingerprint_sha256_16,
                "recipient_fingerprint_sha256_16": recipient_fp,
            },
        )
        return

    await audit.log(
        user_id=user_id,
        event_type="APPROVAL_EMAIL_FAILED",
        description=draft_title,
        details={
            "draft_id": draft_id,
            "approval_token": approval_token,
            "error": result.error or "unknown",
            "body_fingerprint_sha256_16": result.fingerprint_sha256_16,
            "recipient_fingerprint_sha256_16": recipient_fp,
        },
    )
