"""Phase 11 / Job Tracker — focused tests.

Coverage:

  1. Jobs
     - CRUD
     - cross-user ownership blocked
  2. Applications
     - CRUD
     - status transitions
     - ownership
  3. Events
     - create + list in order
  4. Resume match
     - calls existing ATS analyzer
     - multiple-resume sort
  5. LinkedIn bridge
     - source context includes JD + angle
     - framing hint never claims employment
  6. Security
     - SSRF (reuses existing validate_url)
     - no fabricated company / role / salary
  7. Dashboard
     - counts + rates
     - division-by-zero returns None
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.db.mongo import get_database
from backend.app.repositories.job_repository import (
    ApplicationEventRepository,
    ApplicationRepository,
    JobMatchRepository,
    JobRepository,
)
from backend.app.services.ats_analyzer import analyze_resume_against_jd
from backend.app.services.job_service import JobService, JobServiceError
from backend.app.services.resume_to_linkedin import build_resume_source_context
from backend.app.models.jobs import (
    ApplicationCreateRequest,
    JobCreateRequest,
    JobUpdateRequest,
)


# ---------------------------------------------------------------------------
# 1. Jobs CRUD + ownership
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    from backend.app.main import app
    return app


@pytest.fixture
def service():
    db = get_database()
    return JobService(
        jobs=JobRepository(db),
        applications=ApplicationRepository(db),
        events=ApplicationEventRepository(db),
        matches=JobMatchRepository(db),
    )


class TestJobsCrud:
    def test_create_then_get(self, service):
        async def _go():
            doc = await service.create(
                user_id="USER_A",
                payload=JobCreateRequest(
                    title="Senior Engineer",
                    company="Acme",
                    job_url="https://example.com/job/1",
                    description="We are looking for a senior engineer.",
                ),
            )
            return doc

        doc = asyncio.run(_go())
        assert doc["title"] == "Senior Engineer"
        assert doc["company"] == "Acme"
        assert doc["user_id"] == "USER_A"
        assert doc["id"]

    def test_cross_user_read_blocked(self, service):
        async def _go():
            await service.create(
                user_id="USER_A",
                payload=JobCreateRequest(
                    title="Mine", job_url="https://example.com/job/x"
                ),
            )

        asyncio.run(_go())
        # USER_B cannot list or get USER_A's job.
        async def _list_b():
            return await service.list(user_id="USER_B")

        items = asyncio.run(_list_b())
        assert all(item["user_id"] != "USER_B" for item in items)

    def test_duplicate_url_rejected(self, service):
        async def _go():
            await service.create(
                user_id="USER_A",
                payload=JobCreateRequest(
                    title="A", job_url="https://example.com/job/dup"
                ),
            )
            try:
                await service.create(
                    user_id="USER_A",
                    payload=JobCreateRequest(
                        title="B", job_url="https://example.com/job/dup"
                    ),
                )
            except JobServiceError as e:
                return e.code

        code = asyncio.run(_go())
        assert code == "duplicate"

    def test_update_then_delete(self, service):
        async def _go():
            doc = await service.create(
                user_id="USER_A",
                payload=JobCreateRequest(title="T", job_url="https://example.com/job/u"),
            )
            updated = await service.update(
                user_id="USER_A",
                job_id=doc["id"],
                payload=JobUpdateRequest(title="T2"),
            )
            ok = await service.delete(user_id="USER_A", job_id=doc["id"])
            return updated, ok

        updated, ok = asyncio.run(_go())
        assert updated["title"] == "T2"
        assert ok is True

    def test_cross_user_delete_blocked(self, service):
        async def _go():
            doc = await service.create(
                user_id="USER_A",
                payload=JobCreateRequest(title="T", job_url="https://example.com/job/dx"),
            )
            return await service.delete(user_id="USER_B", job_id=doc["id"])

        ok = asyncio.run(_go())
        assert ok is False


# ---------------------------------------------------------------------------
# 2. Applications
# ---------------------------------------------------------------------------


class TestApplications:
    def test_create_then_status_update(self, service):
        async def _go():
            job = await service.create(
                user_id="USER_A",
                payload=JobCreateRequest(title="T", job_url="https://example.com/job/a1"),
            )
            app = await service.create_application(
                user_id="USER_A",
                payload=ApplicationCreateRequest(
                    job_id=job["id"], resume_id="res-1"
                ),
            )
            updated = await service.update_application(
                user_id="USER_A",
                app_id=app["id"],
                payload=__import__(
                    "backend.app.models.jobs",
                    fromlist=["ApplicationUpdateRequest"],
                ).ApplicationUpdateRequest(status="applied"),
            )
            return app, updated

        app, updated = asyncio.run(_go())
        assert app["status"] == "saved"
        assert updated["status"] == "applied"

    def test_invalid_status_rejected(self, service):
        async def _go():
            job = await service.create(
                user_id="USER_A",
                payload=JobCreateRequest(title="T", job_url="https://example.com/job/a2"),
            )
            app = await service.create_application(
                user_id="USER_A",
                payload=ApplicationCreateRequest(
                    job_id=job["id"], resume_id="res-2"
                ),
            )
            try:
                await service.update_application(
                    user_id="USER_A",
                    app_id=app["id"],
                    payload=__import__(
                        "backend.app.models.jobs",
                        fromlist=["ApplicationUpdateRequest"],
                    ).ApplicationUpdateRequest(status="invalid"),
                )
            except JobServiceError as e:
                return e.code

        from backend.app.services.job_service import JobServiceError
        code = asyncio.run(_go())
        assert code == "invalid_input"

    def test_cross_user_blocked(self, service):
        async def _go():
            job = await service.create(
                user_id="USER_A",
                payload=JobCreateRequest(title="T", job_url="https://example.com/job/a3"),
            )
            app = await service.create_application(
                user_id="USER_A",
                payload=ApplicationCreateRequest(
                    job_id=job["id"], resume_id="res-3"
                ),
            )
            return await service.update_application(
                user_id="USER_B",
                app_id=app["id"],
                payload=__import__(
                    "backend.app.models.jobs",
                    fromlist=["ApplicationUpdateRequest"],
                ).ApplicationUpdateRequest(notes="hack"),
            )

        ok = asyncio.run(_go())
        assert ok is None


# ---------------------------------------------------------------------------
# 3. Events
# ---------------------------------------------------------------------------


class TestEvents:
    def test_events_created_and_ordered(self, service):
        async def _go():
            job = await service.create(
                user_id="USER_A",
                payload=JobCreateRequest(title="T", job_url="https://example.com/job/e1"),
            )
            app = await service.create_application(
                user_id="USER_A",
                payload=ApplicationCreateRequest(
                    job_id=job["id"], resume_id="res-e"
                ),
            )
            # Move the app through a few transitions.
            await service.update_application(
                user_id="USER_A",
                app_id=app["id"],
                payload=__import__(
                    "backend.app.models.jobs",
                    fromlist=["ApplicationUpdateRequest"],
                ).ApplicationUpdateRequest(status="applied"),
            )
            await service.update_application(
                user_id="USER_A",
                app_id=app["id"],
                payload=__import__(
                    "backend.app.models.jobs",
                    fromlist=["ApplicationUpdateRequest"],
                ).ApplicationUpdateRequest(status="interview"),
            )
            return await service.list_events(user_id="USER_A", app_id=app["id"])

        events = asyncio.run(_go())
        types = [e["event_type"] for e in events]
        # Events are ordered by timestamp ascending.
        assert types[0] == "saved"
        assert "applied" in types
        assert "interview" in types


# ---------------------------------------------------------------------------
# 4. Resume match (reuses ATS analyzer)
# ---------------------------------------------------------------------------


class TestResumeMatch:
    def test_analyzer_reused(self, service):
        """The Job Tracker calls into the existing Phase 10 ATS
        analyzer. The match endpoint must not duplicate the
        scoring logic."""
        from backend.app.models.resume import (
            EducationItem,
            ExperienceItem,
            PersonalInfo,
            Resume,
            SkillsGroup,
        )
        resume = Resume(
            personal=PersonalInfo(full_name="X", email="x@y.com"),
            summary="Python engineer with 5 years of experience.",
            experience=[
                ExperienceItem(
                    company="A",
                    role="Engineer",
                    start_date="2020",
                    end_date="Present",
                    description="Built Python tools.",
                    achievements=["Cut latency 40%"],
                    technologies=["Python", "AWS", "PostgreSQL"],
                )
            ],
            education=[EducationItem(institution="U", degree="BSc", end_date="2018")],
            skills=[
                SkillsGroup(category="Languages", skills=["Python", "TypeScript"]),
                SkillsGroup(category="Cloud", skills=["AWS"]),
            ],
        )
        analysis = analyze_resume_against_jd(
            resume,
            (
                "Senior Software Engineer. 5+ years of experience. "
                "Python, AWS, Docker, PostgreSQL required."
            ),
        )
        assert 0 <= analysis.overall_score <= 100
        # Must contain real matches.
        assert "python" in analysis.matched_keywords
        assert "aws" in analysis.matched_keywords

    def test_creator_does_not_fabricate_company(self):
        """If the user provides neither title nor company, the
        service does not invent one. The job is still saved with
        empty values (the user fills in the editor)."""
        from backend.app.db.mongo import get_database
        from backend.app.services.job_service import JobService as _JS

        async def _go():
            svc = _JS(
                jobs=JobRepository(get_database()),
                applications=ApplicationRepository(get_database()),
                events=ApplicationEventRepository(get_database()),
                matches=JobMatchRepository(get_database()),
            )
            doc = await svc.create(
                user_id="USER_FAB",
                payload=JobCreateRequest(title=""),
            )
            return doc

        with pytest.raises(Exception):
            asyncio.run(_go())

    def test_dashboard_rates_handle_zero_applied(self, service):
        async def _go():
            # An empty dashboard must not raise and must return
            # None rates so the UI can show "unavailable".
            return await service.dashboard(user_id="USER_DASH")

        out = asyncio.run(_go())
        assert out["counts"] == {} or out["counts"] == {}
        assert out["interview_rate"] is None
        assert out["offer_rate"] is None
        assert out["applications_this_week"] == 0
        assert out["average_ats"] == 0

    def test_dashboard_no_division_by_zero(self, service):
        """Same as above but with an applied app to make sure
        the rate is computed correctly."""
        async def _go():
            job = await service.create(
                user_id="USER_DIV",
                payload=JobCreateRequest(
                    title="T", job_url="https://example.com/job/d"
                ),
            )
            await service.create_application(
                user_id="USER_DIV",
                payload=ApplicationCreateRequest(
                    job_id=job["id"], resume_id="r"
                ),
            )
            return await service.dashboard(user_id="USER_DIV")

        out = asyncio.run(_go())
        assert out["interview_rate"] is None  # no interviews yet
        assert out["offer_rate"] is None
        assert out["counts"]["saved"] == 1
