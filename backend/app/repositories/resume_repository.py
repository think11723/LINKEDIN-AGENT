"""Resume repository — Phase 10.

Two collections:

* ``resumes``       — one document per resume; user-scoped.
* ``ats_analyses``   — one document per ATS analysis; user-scoped
                       and resume-scoped.

Every read is scoped by ``user_id`` so cross-user access returns
``None`` and the API layer responds with 404 (never 403, to avoid
leaking existence). The repository is plain MongoDB; the API layer
sanitizes every input that crosses the trust boundary.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.app.db.mongo import (
    COLLECTION_ATS_ANALYSES,
    COLLECTION_RESUMES,
)
from backend.app.models.resume import (
    ATSAnalysis,
    JDAnalysis,
    Resume,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ResumeRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION_RESUMES]
        self.analyses = db[COLLECTION_ATS_ANALYSES]

    # ----------------------------------------------------------------
    # Resume CRUD
    # ----------------------------------------------------------------

    async def create(
        self,
        *,
        user_id: str,
        title: str,
        target_role: str = "",
        source_type: str = "manual",
        resume: Optional[Resume] = None,
    ) -> dict:
        rid = f"rsm_{uuid.uuid4().hex}"
        now = _utcnow()
        doc: dict = {
            "_id": rid,
            "user_id": user_id,
            "title": title,
            "target_role": target_role,
            "source_type": source_type,
            "resume": (resume.model_dump() if resume else Resume().model_dump()),
            "created_at": now,
            "updated_at": now,
        }
        await self.col.insert_one(doc)
        return doc

    async def get(self, *, user_id: str, resume_id: str) -> Optional[dict]:
        return await self.col.find_one(
            {"_id": resume_id, "user_id": user_id}
        )

    async def list(self, *, user_id: str, limit: int = 50) -> List[dict]:
        cursor = (
            self.col.find({"user_id": user_id})
            .sort("updated_at", -1)
            .limit(max(1, min(200, limit)))
        )
        return [doc async for doc in cursor]

    async def update(
        self,
        *,
        user_id: str,
        resume_id: str,
        updates: dict,
    ) -> Optional[dict]:
        updates = dict(updates)
        updates["updated_at"] = _utcnow()
        return await self.col.find_one_and_update(
            {"_id": resume_id, "user_id": user_id},
            {"$set": updates},
            return_document=True,
        )

    async def delete(self, *, user_id: str, resume_id: str) -> bool:
        res = await self.col.delete_one(
            {"_id": resume_id, "user_id": user_id}
        )
        # Also drop the resume's ATS analyses.
        await self.analyses.delete_many(
            {"user_id": user_id, "resume_id": resume_id}
        )
        return res.deleted_count == 1

    async def create_version(
        self,
        *,
        user_id: str,
        source_resume_id: str,
        title: str,
    ) -> Optional[dict]:
        """Duplicate a resume under a new id with the supplied
        title. The original is never modified. Returns ``None`` if
        the source resume is not found / not owned by the user.
        """
        source = await self.get(user_id=user_id, resume_id=source_resume_id)
        if not source:
            return None
        new_resume = Resume(**source.get("resume") or {})
        return await self.create(
            user_id=user_id,
            title=title,
            target_role=source.get("target_role", ""),
            source_type=source.get("source_type", "manual"),
            resume=new_resume,
        )

    # ----------------------------------------------------------------
    # ATS analyses
    # ----------------------------------------------------------------

    async def save_analysis(
        self,
        *,
        user_id: str,
        resume_id: str,
        analysis: ATSAnalysis,
    ) -> dict:
        aid = f"ats_{uuid.uuid4().hex}"
        now = _utcnow()
        doc: dict = {
            "_id": aid,
            "user_id": user_id,
            "resume_id": resume_id,
            "job_title": analysis.job_title,
            "company": analysis.company,
            "overall_score": analysis.overall_score,
            "breakdown": analysis.breakdown.model_dump(),
            "matched_keywords": list(analysis.matched_keywords),
            "missing_keywords": list(analysis.missing_keywords),
            "related_keywords": list(analysis.related_keywords),
            "jd_analysis": analysis.jd_analysis.model_dump(),
            "improvements": [i.model_dump() for i in analysis.improvements],
            "created_at": now,
        }
        await self.analyses.insert_one(doc)
        return doc

    async def get_analysis(
        self, *, user_id: str, analysis_id: str
    ) -> Optional[dict]:
        return await self.analyses.find_one(
            {"_id": analysis_id, "user_id": user_id}
        )

    async def list_analyses_for_resume(
        self, *, user_id: str, resume_id: str, limit: int = 20
    ) -> List[dict]:
        cursor = (
            self.analyses.find(
                {"user_id": user_id, "resume_id": resume_id}
            )
            .sort("created_at", -1)
            .limit(max(1, min(200, limit)))
        )
        return [doc async for doc in cursor]

    async def list_recent_analyses(
        self, *, user_id: str, limit: int = 10
    ) -> List[dict]:
        cursor = (
            self.analyses.find({"user_id": user_id})
            .sort("created_at", -1)
            .limit(max(1, min(200, limit)))
        )
        return [doc async for doc in cursor]


def resume_doc_to_response(doc: dict) -> dict:
    """Project a stored resume document to the API response shape."""
    if not doc:
        return doc
    out = dict(doc)
    out["id"] = doc["_id"]
    out["created_at"] = doc.get("created_at").isoformat() if doc.get("created_at") else None
    out["updated_at"] = doc.get("updated_at").isoformat() if doc.get("updated_at") else None
    return out


def analysis_doc_to_response(doc: dict) -> dict:
    """Project a stored ATS analysis to the API response shape."""
    if not doc:
        return doc
    out = dict(doc)
    out["id"] = doc["_id"]
    out["created_at"] = doc.get("created_at").isoformat() if doc.get("created_at") else None
    return out


__all__ = [
    "ResumeRepository",
    "resume_doc_to_response",
    "analysis_doc_to_response",
]
