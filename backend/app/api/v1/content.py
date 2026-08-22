"""Content API endpoints for the web application.

Now requires Firebase authentication. Generated drafts are persisted in
MongoDB owned by the authenticated user, and ``draft_id`` +
``approval_token`` are surfaced at the top level of the response.

Phase 8D / URL-to-LinkedIn adds two async-job endpoints:

* ``POST /api/v1/content/generate-from-url`` — synchronous SSRF
  pre-check, then enqueue a background job and return 202.
* ``GET  /api/v1/content/generate-from-url/{job_id}`` — poll the job.
  Returns 404 for unknown / cross-user jobs (never 403).

Phase 3 / Source Generation adds:

* ``POST /api/v1/content/source/preview`` — synchronous analyze that
  fetches the URL through the SSRF guard + adapter layer, classifies
  the source, and returns a structured preview (title / summary /
  key facts / source type). NO draft is created. This is the "Analyze
  Source" button behind the Create Post page.
* ``POST /api/v1/content/generate`` — now also accepts
  ``source_url``. When set, the request runs the source pipeline
  synchronously and persists a draft with the source's metadata
  attached. Topic-mode drafts are unchanged.

The actual fetch + analysis + writer + reviewer pipeline runs in
``backend/app/services/source_job_runner.py`` (async job mode) and
inline for the synchronous preview / unified ``/generate`` path.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from pydantic import BaseModel, Field

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
    SourcePackage,
    resolve_adapter,
    validate_url,
)
from backend.app.services.sources.classification import (
    classify as classify_source,
    get_source_label as get_source_type_label,
)
from backend.app.services.workflow_service import WorkflowService
from shared.schemas import GenerateContentRequest, GenerateContentResponse

router = APIRouter(prefix="/api/v1/content", tags=["content"])


# ---------------------------------------------------------------------------
# Phase 3 / Source preview — request / response models
# ---------------------------------------------------------------------------


class SourcePreviewRequest(BaseModel):
    """Request body for ``POST /api/v1/content/source/preview``.

    The user supplies a URL; the server fetches it (SSRF-guarded),
    runs the appropriate adapter, classifies the source, and returns
    a structured preview. No draft is created. No LLM call is made.
    """

    url: str = Field(..., min_length=1, description="Public URL to analyze")


class SourcePreviewResponse(BaseModel):
    """Body of the source-preview endpoint.

    Carries the trimmed ``SourcePackage`` plus the classification
    label. The frontend renders this as a "source found" card with
    the appropriate framing. ``source_metadata`` is a conservative
    projection — credentials are filtered out, fields are bounded.
    """

    source: dict = Field(..., description="Trimmed source preview payload")
    source_type: str = Field(..., description="Canonical source-type label")
    source_label: str = Field(..., description="Human-readable source-type label")
    adapter: Optional[str] = Field(
        default=None, description="Adapter that produced the package"
    )
    request_id: str = Field(
        ..., description="Correlation id for support / audit"
    )


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

    Phase 3: when ``payload.source_url`` is supplied, the request
    routes to the source pipeline (SSRF-safe fetch → adapter →
    classification → writer → reviewer → normalize → persist). The
    legacy topic-mode path is unchanged.

    Phase 8A / P0-1: the global exception handler in
    ``backend.app.core.error_handlers`` produces a safe envelope for any
    uncaught exception — never ``str(exc)``.
    """
    # Source-mode takes precedence. The topic field is optional and
    # may be honored as a writer framing override.
    if payload.source_url:
        return await _generate_from_source(
            payload=payload,
            user=user,
            service=service,
            drafts=drafts,
            approvals=approvals,
            audit=audit,
            users=users,
        )

    # Topic-mode legacy path.
    if not (payload.topic and payload.topic.strip()):
        raise HTTPException(
            status_code=400,
            detail="Topic cannot be empty. Provide either `topic` or `source_url`.",
        )

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
# Phase 3 / Source preview endpoint (synchronous analyze, no draft)
# ---------------------------------------------------------------------------


@router.post(
    "/source/preview",
    response_model=SourcePreviewResponse,
    status_code=status.HTTP_200_OK,
)
async def source_preview(
    payload: SourcePreviewRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    audit: AuditRepository = Depends(get_audit_repository),
) -> SourcePreviewResponse:
    """Synchronously analyze a URL and return a source preview.

    Flow:
      1. SSRF pre-check (``validate_url``). 400 on any blocked URL.
      2. Resolve the appropriate adapter and call ``adapter.fetch``.
         400 / 502 with a safe user message on any failure.
      3. Run :func:`classify_source` to project the package into a
         single canonical ``source_type`` label.
      4. Build a trimmed preview (no raw HTML, no README text, no
         secrets) and return it.
      5. Audit row ``SOURCE_PREVIEW_SUCCEEDED`` / ``SOURCE_PREVIEW_FAILED``
         with safe metadata only.

    This endpoint does NOT create a draft and does NOT call the LLM.
    It is the backend for the "Analyze Source" button in the Create
    Post page.
    """
    request_id = f"req_{uuid.uuid4().hex}"

    # 1. SSRF pre-check.
    try:
        validate_url(payload.url, allow_hosts=None)
    except SourceBlockedError as exc:
        await audit.log(
            user_id=user.uid,
            event_type="SOURCE_PREVIEW_BLOCKED",
            description="URL rejected by SSRF pre-check",
            details={"url": payload.url, "reason": exc.code, "request_id": request_id},
        )
        raise HTTPException(status_code=400, detail=exc.message) from exc

    # 2. Adapter + fetch.
    try:
        adapter = resolve_adapter(payload.url)
        package: SourcePackage = await adapter.fetch(
            payload.url, request_id=request_id
        )
    except SourceBlockedError as exc:
        await audit.log(
            user_id=user.uid,
            event_type="SOURCE_PREVIEW_BLOCKED",
            description="URL rejected during fetch (SSRF)",
            details={
                "url": payload.url,
                "reason": exc.code,
                "request_id": request_id,
            },
        )
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except SourceFetchError as exc:
        await audit.log(
            user_id=user.uid,
            event_type="SOURCE_PREVIEW_FAILED",
            description="Source preview fetch failed",
            details={
                "url": payload.url,
                "error_code": exc.code,
                "request_id": request_id,
            },
        )
        raise HTTPException(
            status_code=502,
            detail=_user_safe_fetch_message(exc.code, exc.message),
        ) from exc
    except ValueError as exc:
        # No adapter matched (defensive — should not happen because
        # the SSRF guard accepts any http(s) URL).
        await audit.log(
            user_id=user.uid,
            event_type="SOURCE_PREVIEW_FAILED",
            description="No adapter matches URL",
            details={"url": payload.url, "request_id": request_id},
        )
        raise HTTPException(
            status_code=400,
            detail="Unsupported URL. Use http:// or https:// to a public page.",
        ) from exc

    # 3. Classify.
    adapter_name = getattr(adapter, "name", "unknown")
    source_type = classify_source(
        url=package.metadata.get("canonical_url") or payload.url,
        adapter=adapter_name,
        title=package.title or "",
        description=package.summary or "",
        metadata=package.metadata or {},
    )

    # 4. Build a safe preview. Strip known-credential keys; cap
    # any oversized string in metadata.
    preview = _build_source_preview(package, source_type)
    await audit.log(
        user_id=user.uid,
        event_type="SOURCE_PREVIEW_SUCCEEDED",
        description="Source preview ready",
        details={
            "url": payload.url,
            "adapter": adapter_name,
            "source_type": source_type,
            "request_id": request_id,
        },
    )

    return SourcePreviewResponse(
        source=preview,
        source_type=source_type,
        source_label=get_source_type_label(source_type),
        adapter=adapter_name,
        request_id=request_id,
    )


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
        # Compute the approval expiry in a human-friendly form so the
        # email can show it to the user without leaking the raw token.
        approval_expires_at = approval.get("expires_at")
        expires_at_iso: Optional[str] = None
        if approval_expires_at is not None:
            try:
                expires_at_iso = approval_expires_at.isoformat()
            except Exception:  # noqa: BLE001
                expires_at_iso = None
        # Source-type (Phase 5) — drive the "Source" block in the email
        # for URL-mode drafts. Topic-mode drafts pass source_url=None
        # and the email omits the source block.
        source_type_for_email: Optional[str] = None
        if isinstance(source_metadata, dict):
            st = source_metadata.get("source_type")
            if isinstance(st, str) and st:
                source_type_for_email = st
        await _maybe_send_approval_email(
            users=users,
            audit=audit,
            user_id=user.uid,
            draft_id=draft_id,
            draft_title=title,
            draft_topic=workflow_result.topic,
            draft_content=content,
            draft_hashtags=hashtags,
            approval_token=approval["_id"],
            source_url=source_url,
            source_type=source_type_for_email,
            expires_at_iso=expires_at_iso,
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
    draft_content: str,
    draft_hashtags: list,
    approval_token: str,
    source_url: Optional[str] = None,
    source_type: Optional[str] = None,
    expires_at_iso: Optional[str] = None,
) -> None:
    """Send an approval-email notification if the user has opted in.

    Behaviour (Phase 6):
      * If ``preferences.approval_mode != "email"`` → no email.
      * If no ``preferences.notification_email`` is set → no email.
      * If the notification address is malformed → no email
        (audit ``APPROVAL_EMAIL_SKIPPED`` with ``reason=invalid_recipient``).
      * If SMTP is not configured on the server → no email (audit
        event records the reason). The draft is still persisted.
      * If SMTP send fails → ``APPROVAL_EMAIL_FAILED`` audit event
        with the SMTP error category, code, and the body fingerprint.
      * If SMTP send succeeds → ``APPROVAL_EMAIL_SENT`` audit event
        with the body fingerprint and the recipient fingerprint.

    For URL-generated drafts (``source_url`` provided), the email
    body includes a "Source" block identifying the source type
    (e.g. "GitHub Repository") and a clickable link.

    The email body itself is NEVER logged — only its SHA-256[:16]
    fingerprint. The approval token is never echoed into any log.
    """
    import hashlib

    from backend.app.core.config import get_settings
    from backend.app.services.email import (
        build_approval_email,
        is_valid_recipient,
        send_email,
        source_label_for,
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

    if not is_valid_recipient(to_address):
        await audit.log(
            user_id=user_id,
            event_type="APPROVAL_EMAIL_SKIPPED",
            description=draft_title,
            details={
                "reason": "invalid_recipient",
                "recipient_domain": _safe_recipient_domain(to_address),
                "draft_id": draft_id,
            },
        )
        return

    settings = get_settings()
    frontend_base = settings.frontend_url.rstrip("/")
    # Approve link — the email approval lands on a dedicated
    # ``/approve?token=...`` page (Phase 6) which validates the
    # token, runs the existing /api/v1/approval/approve endpoint,
    # publishes, and shows a clear result. The token is single-use
    # and has the standard 24h expiry.
    approval_url = f"{frontend_base}/approve?token={approval_token}"
    # Review link — opens the Draft Viewer for the draft (no token
    # in URL, just the draft id).
    review_url = f"{frontend_base}/drafts/{draft_id}"

    subject = f"Approval needed: {draft_title[:80]}"

    # Source-aware rendering: URL-mode drafts include a "Source"
    # block; topic-mode drafts do not.
    text_body, html_body = build_approval_email(
        draft_title=draft_title,
        draft_content=draft_content,
        draft_hashtags=draft_hashtags,
        approval_url=approval_url,
        review_url=review_url,
        source_label=source_label_for(source_type),
        source_url=source_url,
        expires_at_display=expires_at_iso,
        frontend_brand="LinkedIn AI Studio",
    )

    recipient_fp = hashlib.sha256(
        to_address.encode("utf-8")
    ).hexdigest()[:16]

    result = await send_email(
        to=to_address,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )

    safe_details = {
        "draft_id": draft_id,
        "body_fingerprint_sha256_16": result.fingerprint_sha256_16,
        "recipient_fingerprint_sha256_16": recipient_fp,
        "recipient_domain": _safe_recipient_domain(to_address),
        "attempts": result.attempts,
        "approval_token": approval_token,
    }
    if source_type:
        safe_details["source_type"] = source_type

    if result.success:
        await audit.log(
            user_id=user_id,
            event_type="APPROVAL_EMAIL_SENT",
            description=draft_title,
            details=safe_details,
        )
        return

    safe_details["error"] = result.error or "unknown"
    if result.error_category:
        safe_details["error_category"] = result.error_category
    await audit.log(
        user_id=user_id,
        event_type="APPROVAL_EMAIL_FAILED",
        description=draft_title,
        details=safe_details,
    )


def _safe_recipient_domain(address: str) -> str:
    """Return the domain part of an email address, never the full
    recipient. Safe to log / audit."""
    if not address or "@" not in address:
        return ""
    try:
        return address.rsplit("@", 1)[-1].lower()
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# Phase 3 / Source generation helpers (synchronous /generate source mode)
# ---------------------------------------------------------------------------


#: Error codes the source pipeline may emit, mapped to user-safe
#: messages. NEVER include stack traces, raw URLs with credentials,
#: internal IP addresses, or MongoDB errors here.
_USER_SAFE_FETCH_MESSAGES: dict[str, str] = {
    "repository_not_found": "Repository not found on GitHub.",
    "github_unauthorized": "GitHub rejected the request. Check the token.",
    "github_forbidden": "Access to this repository is forbidden.",
    "github_rate_limited": "GitHub rate limit reached. Try again later.",
    "dmca": "This URL is not allowed for security reasons.",
    "not_html": "The URL did not return a readable article.",
    "thin_content": "No readable content found on the page.",
    "bad_response": "The source returned an unexpected response.",
    "not_allowlisted": "The host is not on the allowlist.",
    "http_5xx": "The source is temporarily unavailable.",
    "http_4xx_unexpected": "The source rejected the request.",
    "upstream_404": "The page was not found.",
    "upstream_rate_limited": "The source is rate-limiting requests.",
    "timeout": "The source took too long to respond.",
    "connect_error": "Could not reach the source.",
    "binary_content": "The source is not a readable document.",
    "binary_content_pdf": "PDF sources are not supported.",
    "paywall": "The source appears to be behind a paywall.",
    "content_unavailable_or_paywalled": (
        "The source appears to be behind a paywall or is unavailable."
    ),
    "unsupported_url_form": "This URL form is not supported.",
    "html_too_large": "The page is too large to analyze.",
    "response_too_large": "The response exceeded the size limit.",
    "github_cumulative_too_large": "The repository exceeded the size limit.",
    "private_ip": "The URL points to a private network.",
    "loopback": "The URL points to a local address.",
    "link_local": "The URL is not a public address.",
    "bad_scheme": "Only http:// and https:// are supported.",
    "userinfo": "URLs with credentials are not allowed.",
    "bad_port": "That port is not allowed.",
    "bad_host": "Invalid host.",
    "bad_ip": "Invalid IP address.",
    "dns_error": "Could not resolve the host.",
    "too_many_redirects": "The URL redirected too many times.",
    "redirect_to_private": "The URL redirected to a private address.",
    "bad_url": "Invalid URL.",
    "stream_error": "The connection was interrupted.",
    "http_error": "The source returned an error.",
}


def _user_safe_fetch_message(code: str, default: str) -> str:
    """Return a user-safe message for a source-fetch error code.

    The defaults map covers the full set of stable error codes the
    adapters may raise. New codes added in the future must update the
    map so the frontend can render a clean error.
    """
    if code in _USER_SAFE_FETCH_MESSAGES:
        return _USER_SAFE_FETCH_MESSAGES[code]
    return "Could not read this source. Please check the URL and try again."


#: Defense-in-depth — never echo these keys into a preview payload.
_PREVIEW_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "authorization",
        "bearer",
        "github_token",
        "cookie",
        "set-cookie",
        "access_token",
        "refresh_token",
        "client_secret",
        "api_key",
        "secret",
        "password",
        "private_key",
    }
)


def _sanitize_preview_value(value: Any) -> Any:
    """Cap nested strings, drop forbidden keys recursively.

    Mirrors the policy in :func:`_sanitize_source_metadata` from the
    draft repository — kept in sync to keep the persisted and the
    preview blobs shaped the same.
    """
    if isinstance(value, str):
        if len(value) > 1024:
            return value[:1024] + "…"
        return value
    if isinstance(value, (list, tuple)):
        return [_sanitize_preview_value(v) for v in value[:32]]
    if isinstance(value, dict):
        cleaned: dict = {}
        for k, v in list(value.items())[:24]:
            if k.lower() in _PREVIEW_FORBIDDEN_KEYS:
                continue
            cleaned[k] = _sanitize_preview_value(v)
        return cleaned
    return value


def _build_source_preview(
    package: SourcePackage,
    source_type: str,
) -> dict:
    """Project a :class:`SourcePackage` into the API's preview payload.

    No raw HTML, no README text bodies, no authorization-shaped keys.
    Every nested string is capped.
    """
    safe_meta = _sanitize_preview_value(dict(package.metadata or {}))
    return {
        "type": source_type,
        "url": str(safe_meta.get("url") or ""),
        "final_url": str(
            safe_meta.get("canonical_url") or safe_meta.get("url") or ""
        ),
        "title": str(package.title or ""),
        "summary": str(package.summary or ""),
        "description": str(
            safe_meta.get("description") or package.summary or ""
        ),
        "key_facts": list(package.key_facts or [])[:7],
        "source_metadata": {
            k: v
            for k, v in safe_meta.items()
            if k
            not in {
                "request_id",
                "important_file_contents",
                "readme_summary",
            }
        },
    }


def _build_source_context(
    *,
    package: SourcePackage,
    source_type: str,
    canonical_url: str,
    framing_hint: Optional[str] = None,
) -> dict:
    """Build the structured ``source`` dict for the Phase-5 Writer/Reviewer.

    The Writer uses these fields as ``SOURCE FACTS`` (grounding) and
    the Reviewer uses them to score the GROUNDING dimension. The
    shape mirrors the contract documented in
    ``agents/writer.py::_build_context`` and
    ``agents/reviewer.py::_augment_review_prompt_with_source``.

    Defense-in-depth: ``source_metadata`` is sanitized through the
    same credential-key denylist that ``DraftRepository`` uses on
    persistence, so a future regression in an adapter that produces
    an authorization-shaped key cannot leak it into a Writer/Reviewer
    prompt.
    """
    safe_meta = _sanitize_preview_value(dict(package.metadata or {}))
    author = (
        safe_meta.get("owner")
        or safe_meta.get("owner_login")
        or safe_meta.get("author")
    )
    dependencies = safe_meta.get("dependencies") or {}
    technical_details: list[str] = []
    if isinstance(dependencies, dict):
        for ecosystem, names in dependencies.items():
            if isinstance(names, list) and names:
                technical_details.append(
                    f"{ecosystem}: {', '.join(str(n) for n in names[:8])}"
                )
    if safe_meta.get("primary_language"):
        technical_details.append(
            f"Primary language: {safe_meta['primary_language']}"
        )
    if safe_meta.get("license") and safe_meta["license"] != "NOASSERTION":
        technical_details.append(f"License: {safe_meta['license']}")

    return {
        "source_type": source_type,
        "source_title": package.title or safe_meta.get("description") or "",
        "source_url": canonical_url or safe_meta.get("url") or "",
        "source_summary": (
            package.summary
            or safe_meta.get("description")
            or safe_meta.get("readme_summary")
            or ""
        ),
        "key_points": list(package.key_facts or [])[:8],
        "technical_details": technical_details[:6],
        "author": author or "",
        "framing_hint": framing_hint or "",
        "source_metadata": {
            k: v
            for k, v in safe_meta.items()
            if k not in {"request_id", "important_file_contents"}
        },
    }


async def _generate_from_source(
    *,
    payload: GenerateContentRequest,
    user: AuthenticatedUser,
    service: WorkflowService,
    drafts: DraftRepository,
    approvals: ApprovalRepository,
    audit: AuditRepository,
    users: UserRepository,
) -> GenerateContentResponse:
    """Run the source pipeline end-to-end and persist the result.

    Reuses the same :class:`SourceJobRunner` building blocks:

    1. SSRF pre-check.
    2. Adapter + fetch (deterministic GitHub API or web HTML extract).
    3. Source classification.
    4. Project to ``ResearchPackage`` so the existing writer
       contract is byte-identical to the topic path.
    5. Run the existing writer + reviewer via ``WorkflowService``.
    6. Persist the draft with the source URL + metadata attached.

    Failures are user-safe (never echo the raw error message).
    """
    request_id = f"req_{uuid.uuid4().hex}"

    # 1. SSRF pre-check.
    try:
        validate_url(payload.source_url, allow_hosts=None)
    except SourceBlockedError as exc:
        await audit.log(
            user_id=user.uid,
            event_type="SOURCE_FETCH_BLOCKED",
            description="URL rejected by SSRF pre-check",
            details={
                "url": payload.source_url,
                "reason": exc.code,
                "request_id": request_id,
            },
        )
        raise HTTPException(status_code=400, detail=exc.message) from exc

    # 2. Adapter + fetch.
    try:
        adapter = resolve_adapter(payload.source_url)
        package: SourcePackage = await adapter.fetch(
            payload.source_url, request_id=request_id
        )
    except SourceBlockedError as exc:
        await audit.log(
            user_id=user.uid,
            event_type="SOURCE_FETCH_BLOCKED",
            description="URL rejected during fetch (SSRF)",
            details={
                "url": payload.source_url,
                "reason": exc.code,
                "request_id": request_id,
            },
        )
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except SourceFetchError as exc:
        await audit.log(
            user_id=user.uid,
            event_type="SOURCE_FETCH_FAILED",
            description="Source fetch failed",
            details={
                "url": payload.source_url,
                "error_code": exc.code,
                "request_id": request_id,
            },
        )
        raise HTTPException(
            status_code=502,
            detail=_user_safe_fetch_message(exc.code, exc.message),
        ) from exc
    except ValueError as exc:
        await audit.log(
            user_id=user.uid,
            event_type="SOURCE_FETCH_FAILED",
            description="No adapter matches URL",
            details={"url": payload.source_url, "request_id": request_id},
        )
        raise HTTPException(
            status_code=400,
            detail="Unsupported URL. Use http:// or https:// to a public page.",
        ) from exc

    # 3. Classify.
    source_type = classify_source(
        url=package.metadata.get("canonical_url") or payload.source_url,
        adapter=getattr(adapter, "name", "unknown"),
        title=package.title or "",
        description=package.summary or "",
        metadata=package.metadata or {},
    )
    # Tag the package so the writer prompt can see the type.
    package.metadata["source_type"] = source_type
    package.metadata["request_id"] = request_id

    # 4. Project to ResearchPackage and run the workflow.
    research_package = adapter.to_research_package(package)
    # Build the structured source context the Phase-5 Writer and
    # Reviewer consume. The shape is documented in agents/writer.py
    # ``_build_context``. The framing hint, when supplied by the
    # user via ``payload.topic``, is forwarded as the user's
    # "desired angle".
    source_context = _build_source_context(
        package=package,
        source_type=source_type,
        canonical_url=package.metadata.get("canonical_url") or payload.source_url,
        framing_hint=(payload.topic or "").strip() or None,
    )
    workflow_request = GenerateContentRequest(
        topic=(
            (payload.topic or "").strip()
            or package.metadata.get("topic_hint")
            or package.title
        ),
        image_path=None,
    )
    try:
        workflow_result = await service.generate_content(
            workflow_request,
            research_package=research_package,
            source=source_context,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        await audit.log(
            user_id=user.uid,
            event_type="SOURCE_GENERATION_FAILED",
            description="Writer/reviewer pipeline failed",
            details={
                "url": payload.source_url,
                "request_id": request_id,
                "exception_type": exc.__class__.__name__,
            },
        )
        raise HTTPException(
            status_code=502,
            detail="We couldn't turn this source into a post. Please try again.",
        ) from exc

    # 5. Persist the draft with source metadata.
    try:
        response = await _persist_result(
            user=user,
            workflow_result=workflow_result,
            drafts=drafts,
            approvals=approvals,
            audit=audit,
            users=users,
            source_url=payload.source_url,
            source_metadata={
                **(package.metadata or {}),
                "source_type": source_type,
            },
        )
    except Exception:  # pragma: no cover - defensive
        import logging

        logging.getLogger(__name__).exception(
            "Persistence failed for source-mode draft; returning workflow result."
        )
        response = workflow_result

    await audit.log(
        user_id=user.uid,
        event_type="URL_DRAFT_SUCCEEDED",
        description="URL draft generated (synchronous)",
        details={
            "url": payload.source_url,
            "adapter": getattr(adapter, "name", "unknown"),
            "source_type": source_type,
            "request_id": request_id,
            "draft_id": getattr(response, "draft_id", None),
        },
    )
    return response
