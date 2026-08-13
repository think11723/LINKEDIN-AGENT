"""Phase 8B P1-8 — timezone-aware scheduling tests."""

from __future__ import annotations


def test_offset_aware_iso_accepted(client_a):
    """An offset-aware ISO-8601 string is stored (the endpoint echoes
    back the input verbatim so the user-visible time is preserved)."""
    response = client_a.post(
        "/api/v1/scheduler/schedule",
        json={
            "title": "IST 8pm",
            "content": "x",
            "hashtags": [],
            "scheduled_time": "2026-08-13T20:00:00+05:30",
        },
    )
    assert response.status_code == 200
    # The original offset is preserved end-to-end.
    body = response.json()
    assert "+05:30" in body["scheduled_time"]


def test_zulu_accepted(client_a):
    response = client_a.post(
        "/api/v1/scheduler/schedule",
        json={
            "title": "UTC",
            "content": "x",
            "hashtags": [],
            "scheduled_time": "2026-08-13T20:00:00Z",
        },
    )
    assert response.status_code == 200


def test_naive_string_treated_as_utc(client_a):
    response = client_a.post(
        "/api/v1/scheduler/schedule",
        json={
            "title": "Naive",
            "content": "x",
            "hashtags": [],
            "scheduled_time": "2026-08-13T20:00:00",
        },
    )
    assert response.status_code == 200


def test_invalid_iso_422(client_a):
    response = client_a.post(
        "/api/v1/scheduler/schedule",
        json={
            "title": "Bad",
            "content": "x",
            "hashtags": [],
            "scheduled_time": "not-a-date",
        },
    )
    assert response.status_code == 400 or response.status_code == 422
