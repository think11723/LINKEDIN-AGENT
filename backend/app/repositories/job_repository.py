"""Job tracker repositories — Phase 11.

Four collections, each user-scoped:

* ``jobs``                  — one document per saved job
* ``applications``          — one document per application record
* ``application_events``    — append-only event log per application
* ``job_resume_matches``    — cached ATS match between a job and
                               a resume, computed by the existing
                               ATS analyzer

Every read is scoped by ``user_id``. Cross-user access returns
``None`` and the API layer responds with 404 (never 403, to
avoid leaking existence).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.app.db.mongo import (
    COLLECTION_APP_EVENTS,
    COLLECTION_APPLICATIONS,
    COLLECTION_JOB_MATCHES,
    COLLECTION_JOBS,
)
from backend.app.models.jobs import (
    ApplicationEventResponse,
    ApplicationResponse,
    JobResponse,
    ResumeMatchResponse,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _strip_id_out(doc: dict) -> dict:
    if not doc:
        return doc
    out = dict(doc)
    out["id"] = doc["_id"]
    out["created_at"] = _to_iso(doc.get("created_at"))
    out["updated_at"] = _to_iso(doc.get("updated_at"))
    return out


# ----------------------------------------------------------------
# Jobs
# ----------------------------------------------------------------


class JobRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION_JOBS]

    async def create(self, *, user_id: str, payload: dict) -> dict:
        jid = f"job_{uuid.uuid4().hex}"
        now = _utcnow()
        doc = {
            "_id": jid,
            "user_id": user_id,
            **payload,
            "created_at": now,
            "updated_at": now,
            "saved_at": now,
        }
        await self.col.insert_one(doc)
        return doc

    async def get(self, *, user_id: str, job_id: str) -> Optional[dict]:
        return await self.col.find_one({"_id": job_id, "user_id": user_id})

    async def get_by_url(
        self, *, user_id: str, job_url: str
    ) -> Optional[dict]:
        if not job_url:
            return None
        return await self.col.find_one({"user_id": user_id, "job_url": job_url})

    async def list(
        self,
        *,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        query: dict = {"user_id": user_id}
        cursor = (
            self.col.find(query)
            .sort("created_at", -1)
            .limit(max(1, min(200, limit)))
        )
        return [doc async for doc in cursor]

    async def update(
        self, *, user_id: str, job_id: str, updates: dict
    ) -> Optional[dict]:
        updates = dict(updates)
        updates["updated_at"] = _utcnow()
        return await self.col.find_one_and_update(
            {"_id": job_id, "user_id": user_id},
            {"$set": updates},
            return_document=True,
        )

    async def delete(self, *, user_id: str, job_id: str) -> bool:
        res = await self.col.delete_one(
            {"_id": job_id, "user_id": user_id}
        )
        return res.deleted_count == 1

    async def set_jd_analysis(
        self,
        *,
        user_id: str,
        job_id: str,
        jd_analysis: dict,
    ) -> Optional[dict]:
        return await self.col.find_one_and_update(
            {"_id": job_id, "user_id": user_id},
            {
                "$set": {
                    "jd_analysis": jd_analysis,
                    "updated_at": _utcnow(),
                }
            },
            return_document=True,
        )


# ----------------------------------------------------------------
# Applications
# ----------------------------------------------------------------


class ApplicationRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION_APPLICATIONS]

    async def create(self, *, user_id: str, payload: dict) -> dict:
        aid = f"app_{uuid.uuid4().hex}"
        now = _utcnow()
        doc = {
            "_id": aid,
            "user_id": user_id,
            "applied_at": None,
            "created_at": now,
            "updated_at": now,
            **payload,
        }
        await self.col.insert_one(doc)
        return doc

    async def get(self, *, user_id: str, app_id: str) -> Optional[dict]:
        return await self.col.find_one({"_id": app_id, "user_id": user_id})

    async def get_by_job(
        self, *, user_id: str, job_id: str
    ) -> Optional[dict]:
        return await self.col.find_one(
            {"user_id": user_id, "job_id": job_id}
        )

    async def list(
        self,
        *,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        query: dict = {"user_id": user_id}
        if status:
            query["status"] = status
        cursor = (
            self.col.find(query)
            .sort("updated_at", -1)
            .limit(max(1, min(500, limit)))
        )
        return [doc async for doc in cursor]

    async def update(
        self, *, user_id: str, app_id: str, updates: dict
    ) -> Optional[dict]:
        updates = dict(updates)
        updates["updated_at"] = _utcnow()
        return await self.col.find_one_and_update(
            {"_id": app_id, "user_id": user_id},
            {"$set": updates},
            return_document=True,
        )

    async def delete(self, *, user_id: str, app_id: str) -> bool:
        res = await self.col.delete_one(
            {"_id": app_id, "user_id": user_id}
        )
        return res.deleted_count == 1

    async def counts_by_status(
        self, *, user_id: str
    ) -> Dict[str, int]:
        """Return a dict of {status: count} for the user's apps."""
        out: dict = {}
        async for doc in self.col.find({"user_id": user_id}, {"status": 1}):
            status = doc.get("status", "saved")
            out[status] = out.get(status, 0) + 1
        return out


# ----------------------------------------------------------------
# Application events
# ----------------------------------------------------------------


class ApplicationEventRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION_APP_EVENTS]

    async def add(
        self,
        *,
        user_id: str,
        application_id: str,
        event_type: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        eid = f"evt_{uuid.uuid4().hex}"
        now = _utcnow()
        doc = {
            "_id": eid,
            "user_id": user_id,
            "application_id": application_id,
            "event_type": event_type,
            "metadata": dict(metadata or {}),
            "timestamp": now,
        }
        await self.col.insert_one(doc)
        return doc

    async def list_for_application(
        self, *, user_id: str, application_id: str
    ) -> List[dict]:
        cursor = (
            self.col.find(
                {"user_id": user_id, "application_id": application_id}
            )
            .sort("timestamp", 1)
        )
        return [doc async for doc in cursor]

    async def list_recent(
        self, *, user_id: str, limit: int = 10
    ) -> List[dict]:
        cursor = (
            self.col.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(max(1, min(200, limit)))
        )
        return [doc async for doc in cursor]

    async def delete_for_application(
        self, *, user_id: str, application_id: str
    ) -> int:
        res = await self.col.delete_many(
            {"user_id": user_id, "application_id": application_id}
        )
        return res.deleted_count


# ----------------------------------------------------------------
# Job / resume matches
# ----------------------------------------------------------------


class JobMatchRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION_JOB_MATCHES]

    async def upsert(
        self,
        *,
        user_id: str,
        job_id: str,
        resume_id: str,
        match: dict,
    ) -> dict:
        mid = f"match_{uuid.uuid4().hex}"
        now = _utcnow()
        doc = {
            "_id": mid,
            "user_id": user_id,
            "job_id": job_id,
            "resume_id": resume_id,
            "overall_score": match.get("overall_score", 0),
            "breakdown": match.get("breakdown", {}),
            "matched_keywords": match.get("matched_keywords", []),
            "missing_keywords": match.get("missing_keywords", []),
            "jd_analysis": match.get("jd_analysis"),
            "resume_title": match.get("resume_title", ""),
            "resume_target_role": match.get("resume_target_role", ""),
            "created_at": now,
        }
        await self.col.replace_one(
            {"user_id": user_id, "job_id": job_id, "resume_id": resume_id},
            doc,
            upsert=True,
        )
        return doc

    async def list_for_job(
        self, *, user_id: str, job_id: str
    ) -> List[dict]:
        cursor = (
            self.col.find({"user_id": user_id, "job_id": job_id})
            .sort("overall_score", -1)
        )
        return [doc async for doc in cursor]

    async def get(
        self, *, user_id: str, match_id: str
    ) -> Optional[dict]:
        return await self.col.find_one(
            {"_id": match_id, "user_id": user_id}
        )

    async def best_match(
        self, *, user_id: str, job_id: str
    ) -> Optional[dict]:
        cursor = (
            self.col.find({"user_id": user_id, "job_id": job_id})
            .sort("overall_score", -1)
            .limit(1)
        )
        async for doc in cursor:
            return doc
        return None


# ----------------------------------------------------------------
# Response projections
# ----------------------------------------------------------------


def job_to_response(doc: dict) -> dict:
    if not doc:
        return doc
    out = _strip_id_out(doc)
    out["saved_at"] = _to_iso(doc.get("saved_at"))
    return out


def application_to_response(doc: dict) -> dict:
    if not doc:
        return doc
    out = _strip_id_out(doc)
    out["applied_at"] = _to_iso(doc.get("applied_at"))
    return out


def event_to_response(doc: dict) -> dict:
    if not doc:
        return doc
    out = {
        "id": doc["_id"],
        "application_id": doc.get("application_id", ""),
        "event_type": doc.get("event_type", ""),
        "metadata": doc.get("metadata", {}),
        "timestamp": _to_iso(doc.get("timestamp")),
    }
    return out


def match_to_response(doc: dict) -> dict:
    if not doc:
        return doc
    return {
        "id": doc["_id"],
        "job_id": doc.get("job_id", ""),
        "resume_id": doc.get("resume_id", ""),
        "overall_score": doc.get("overall_score", 0),
        "breakdown": doc.get("breakdown", {}),
        "matched_keywords": doc.get("matched_keywords", []),
        "missing_keywords": doc.get("missing_keywords", []),
        "jd_analysis": doc.get("jd_analysis"),
        "resume_title": doc.get("resume_title", ""),
        "resume_target_role": doc.get("resume_target_role", ""),
        "created_at": _to_iso(doc.get("created_at")),
    }


__all__ = [
    "ApplicationEventRepository",
    "ApplicationRepository",
    "JobMatchRepository",
    "JobRepository",
    "application_to_response",
    "event_to_response",
    "job_to_response",
    "match_to_response",
]
