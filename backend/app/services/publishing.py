"""LinkedIn publishing — shared between the scheduler runner and the
on-demand ``POST /api/v1/drafts/{id}/publish`` endpoint.

Phase 8B P1-9.

The text-only UGC publish is implemented here. Image upload is out of
scope for P1 (deferred to P5). All log calls preserve P0-8 hygiene —
status code only, no response body.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from backend.app.db.mongo import get_database
from backend.app.repositories.draft_repository import DraftRepository
from backend.app.repositories.linkedin_repository import LinkedInRepository

logger = logging.getLogger(__name__)


@dataclass
class PublishResult:
    success: bool
    linkedin_post_id: Optional[str] = None
    already_published: bool = False
    error_message: Optional[str] = None


async def resolve_person_urn(access_token: str) -> Optional[str]:
    """Best-effort lookup of the LinkedIn member URN for the given token.

    Returns ``urn:li:person:<sub>`` on success, ``None`` on any failure
    (caller may retry). Never logs the response body (P0-8).
    """
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            response = await http.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
        if response.status_code != 200:
            return None
        data = response.json()
        sub = data.get("sub")
        return f"urn:li:person:{sub}" if sub else None
    except Exception:  # noqa: BLE001
        return None


async def _publish_ugc_post(
    *,
    access_token: str,
    person_urn: str,
    title: str,
    content: str,
    hashtags: list[str],
) -> tuple[bool, Optional[str], Optional[str]]:
    """POST a text-only ``ugcPost`` to LinkedIn.

    Returns ``(success, linkedin_post_id, error_message)``.

    P0-8: never logs response body. Logs status only.
    """
    text = f"{title}\n\n{content}\n\n{' '.join(hashtags or [])}".strip()
    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.post(
                "https://api.linkedin.com/v2/ugcPosts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("LinkedIn publish request failed: %s", exc.__class__.__name__)
        return False, None, "LinkedIn request failed"

    if response.status_code not in (200, 201):
        # P0-8: log status only.
        logger.warning("LinkedIn publish failed: status=%s", response.status_code)
        return False, None, f"LinkedIn returned status {response.status_code}"

    data = response.json()
    return True, data.get("id") or "unknown", None


async def publish_now(
    user_id: str,
    draft_id: str,
    *,
    image_path_override: Optional[str] = None,  # P5 placeholder
) -> PublishResult:
    """Phase 8B P1-9 — publish a draft immediately.

    Idempotent: if the draft is already published, returns
    ``PublishResult(success=True, already_published=True)`` without
    contacting LinkedIn.

    The runner uses the same underlying UGC POST so behaviour is
    identical between scheduled and on-demand paths.
    """
    drafts = DraftRepository(get_database())
    draft = await drafts.get(user_id, draft_id)
    if not draft:
        return PublishResult(success=False, error_message="draft not found")
    if draft.get("published_at"):
        return PublishResult(
            success=True,
            already_published=True,
            linkedin_post_id=draft.get("linkedin_post_id"),
        )

    linkedin = LinkedInRepository(get_database())
    tokens = await linkedin.get_decrypted_tokens(user_id)
    if not tokens or not tokens.get("access_token"):
        return PublishResult(
            success=False,
            error_message="LinkedIn account not connected",
        )

    person_urn = (
        draft.get("person_urn")
        or tokens.get("person_urn")
    ) or (await resolve_person_urn(tokens["access_token"]))
    if not person_urn:
        return PublishResult(
            success=False,
            error_message="Could not resolve LinkedIn member URN",
        )

    success, linkedin_post_id, err = await _publish_ugc_post(
        access_token=tokens["access_token"],
        person_urn=person_urn,
        title=draft.get("title", ""),
        content=draft.get("content", ""),
        hashtags=draft.get("hashtags", []) or [],
    )
    if not success:
        return PublishResult(success=False, error_message=err)

    # Persist the new publish marker (idempotent on the data layer).
    marked = await drafts.mark_published(
        user_id, draft_id, linkedin_post_id=linkedin_post_id
    )
    if not marked:
        # Another process won the CAS — the draft is already published.
        return PublishResult(
            success=True,
            already_published=True,
            linkedin_post_id=linkedin_post_id,
        )
    return PublishResult(
        success=True,
        linkedin_post_id=linkedin_post_id,
    )