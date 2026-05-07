# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Cycle 4 W2 PR-A — endpoint tests for src/api/routers/revisions.py.

Covers detect-revision-of, confirm-revision-of, and tombstone-revision
under the InMemoryStore-backed test harness. Uses TestClient + JWT mint.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_store
from src.database.store import InMemoryStore
from src.parser.models import ParsedSchedule, Project

_SECRET = "test-secret"
_ALGORITHM = "HS256"


def _make_token(user_id: str = "user-w2-test", email: str = "w2@test.com") -> str:
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "iat": int(time.time()) - 60,
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def _schedule(name: str, last_recalc: datetime | None) -> ParsedSchedule:
    sched = ParsedSchedule()
    sched.projects.append(Project(proj_id="1", proj_short_name=name, last_recalc_date=last_recalc))
    return sched


@pytest.fixture
def fresh_store() -> InMemoryStore:
    """Reset the global store between tests so revisions don't leak across cases."""
    store = get_store()
    if isinstance(store, InMemoryStore):
        # Wipe revision_history + project_meta state for a clean test run
        store._revision_history = []
        store._revision_history_counter = 0
        store._project_meta = {}
        store._programs = {}
        store._program_counter = 0
        store._upload_program = {}
        store._upload_revision = {}
        store._project_owners = {}
        store._audit_log = []
    return store  # type: ignore[return-value]


@pytest.fixture
def client(fresh_store: InMemoryStore) -> TestClient:
    return TestClient(app)


# ────────────────────────────────────────────────────────────
# detect-revision-of
# ────────────────────────────────────────────────────────────


def test_detect_unauth_returns_401(client: TestClient) -> None:
    resp = client.post("/api/v1/projects/p1/detect-revision-of")
    assert resp.status_code == 401


def test_detect_no_candidate_for_solo_project(
    client: TestClient, fresh_store: InMemoryStore
) -> None:
    pid = fresh_store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id="user-w2-test",
    )
    token = _make_token()
    resp = client.post(
        f"/api/v1/projects/{pid}/detect-revision-of",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate_project_id"] is None
    assert body["confidence"] == 0.0


def test_detect_returns_candidate_for_sibling(
    client: TestClient, fresh_store: InMemoryStore
) -> None:
    p1 = fresh_store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id="user-w2-test",
    )
    p2 = fresh_store.save_project(
        upload_id="u2",
        schedule=_schedule("PROJ-A", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        user_id="user-w2-test",
    )
    token = _make_token()
    resp = client.post(
        f"/api/v1/projects/{p2}/detect-revision-of",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate_project_id"] == p1
    assert body["confidence"] == 0.9
    assert body["candidate_project_name"] == "PROJ-A"


# ────────────────────────────────────────────────────────────
# confirm-revision-of
# ────────────────────────────────────────────────────────────


def test_confirm_unauth_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/projects/p1/confirm-revision-of",
        json={"parent_project_id": "p2"},
    )
    assert resp.status_code == 401


def test_confirm_404_when_current_missing(client: TestClient, fresh_store: InMemoryStore) -> None:
    token = _make_token()
    resp = client.post(
        "/api/v1/projects/nonexistent/confirm-revision-of",
        headers={"Authorization": f"Bearer {token}"},
        json={"parent_project_id": "also-nonexistent"},
    )
    assert resp.status_code == 404


def test_confirm_409_when_parent_in_different_program(
    client: TestClient, fresh_store: InMemoryStore
) -> None:
    """Confirm rejects cross-program parents — auto-grouping should already align them."""
    p1 = fresh_store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id="user-w2-test",
    )
    # Different proj_short_name → different program_id
    p2 = fresh_store.save_project(
        upload_id="u2",
        schedule=_schedule("PROJ-B", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        user_id="user-w2-test",
    )
    token = _make_token()
    resp = client.post(
        f"/api/v1/projects/{p2}/confirm-revision-of",
        headers={"Authorization": f"Bearer {token}"},
        json={"parent_project_id": p1},
    )
    assert resp.status_code == 409
    assert "not in the same program" in resp.json()["detail"]


def test_confirm_writes_revision_history_row(
    client: TestClient, fresh_store: InMemoryStore
) -> None:
    p1 = fresh_store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        xer_bytes=b"<<XER bytes for upload 1>>",
        user_id="user-w2-test",
    )
    p2 = fresh_store.save_project(
        upload_id="u2",
        schedule=_schedule("PROJ-A", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        xer_bytes=b"<<XER bytes for upload 2>>",
        user_id="user-w2-test",
    )
    token = _make_token()
    resp = client.post(
        f"/api/v1/projects/{p2}/confirm-revision-of",
        headers={"Authorization": f"Bearer {token}"},
        json={"parent_project_id": p1},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["project_id"] == p2
    assert body["revision_number"] == 1  # First confirmed revision in the program
    assert body["program_id"] is not None
    assert len(body["content_hash"]) == 64
    # Verify the row landed in the store
    rows = fresh_store.list_revision_history_by_program(body["program_id"], user_id="user-w2-test")
    assert len(rows) == 1
    assert rows[0]["project_id"] == p2


def test_confirm_409_on_cap_exceeded(client: TestClient, fresh_store: InMemoryStore) -> None:
    """12 active revisions per project is the migration 028 cap; the 13th must 409."""
    # Create one parent + 12 children, all in same program
    parent = fresh_store.save_project(
        upload_id="u-parent",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        xer_bytes=b"parent",
        user_id="user-w2-test",
    )
    children = []
    for i in range(13):
        child = fresh_store.save_project(
            upload_id=f"u-c{i}",
            schedule=_schedule("PROJ-A", datetime(2026, 2 + i, 1, tzinfo=timezone.utc))
            if i < 11
            else _schedule("PROJ-A", datetime(2027 + (i - 11), 1, 1, tzinfo=timezone.utc)),
            xer_bytes=f"child-{i}".encode(),
            user_id="user-w2-test",
        )
        children.append(child)

    token = _make_token()
    # Confirm first 12 — all should succeed
    for i in range(12):
        resp = client.post(
            f"/api/v1/projects/{children[i]}/confirm-revision-of",
            headers={"Authorization": f"Bearer {token}"},
            json={"parent_project_id": parent},
        )
        assert resp.status_code == 200, f"child {i} failed: {resp.text}"

    # 13th must hit the cap — 409
    resp = client.post(
        f"/api/v1/projects/{children[12]}/confirm-revision-of",
        headers={"Authorization": f"Bearer {token}"},
        json={"parent_project_id": parent},
    )
    assert resp.status_code == 409
    assert "cap" in resp.json()["detail"].lower()


# ────────────────────────────────────────────────────────────
# tombstone
# ────────────────────────────────────────────────────────────


def test_tombstone_unauth_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/revisions/r1/tombstone",
        json={"reason": "test"},
    )
    assert resp.status_code == 401


def test_tombstone_404_when_revision_missing(
    client: TestClient, fresh_store: InMemoryStore
) -> None:
    token = _make_token()
    resp = client.post(
        "/api/v1/revisions/nonexistent/tombstone",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "test"},
    )
    assert resp.status_code == 404


def test_tombstone_writes_audit_log_row(client: TestClient, fresh_store: InMemoryStore) -> None:
    """Tombstone must write paired audit_log row with action='revision_tombstoned'."""
    # Setup: parent + child + confirm
    parent = fresh_store.save_project(
        upload_id="u-parent",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        xer_bytes=b"parent",
        user_id="user-w2-test",
    )
    child = fresh_store.save_project(
        upload_id="u-child",
        schedule=_schedule("PROJ-A", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        xer_bytes=b"child",
        user_id="user-w2-test",
    )
    token = _make_token()
    confirm = client.post(
        f"/api/v1/projects/{child}/confirm-revision-of",
        headers={"Authorization": f"Bearer {token}"},
        json={"parent_project_id": parent},
    )
    assert confirm.status_code == 200, confirm.text
    revision_id = confirm.json()["revision_id"]

    # Tombstone
    resp = client.post(
        f"/api/v1/revisions/{revision_id}/tombstone",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "mis-grouped — not a revision of PROJ-A"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["revision_id"] == revision_id
    assert body["tombstoned_at"]
    assert body["audit_log_id"]

    # Verify audit_log entry
    audit_rows = [r for r in fresh_store._audit_log if r.get("action") == "revision_tombstoned"]
    assert len(audit_rows) == 1
    assert audit_rows[0]["entity_id"] == revision_id
    assert audit_rows[0]["details"]["reason"] == "mis-grouped — not a revision of PROJ-A"


def test_tombstone_idempotent(client: TestClient, fresh_store: InMemoryStore) -> None:
    """Re-tombstone returns existing tombstoned_at (no double audit row)."""
    parent = fresh_store.save_project(
        upload_id="u-parent",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        xer_bytes=b"parent",
        user_id="user-w2-test",
    )
    child = fresh_store.save_project(
        upload_id="u-child",
        schedule=_schedule("PROJ-A", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        xer_bytes=b"child",
        user_id="user-w2-test",
    )
    token = _make_token()
    confirm = client.post(
        f"/api/v1/projects/{child}/confirm-revision-of",
        headers={"Authorization": f"Bearer {token}"},
        json={"parent_project_id": parent},
    )
    revision_id = confirm.json()["revision_id"]

    first = client.post(
        f"/api/v1/revisions/{revision_id}/tombstone",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "reason 1"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/revisions/{revision_id}/tombstone",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "reason 2"},
    )
    assert second.status_code == 200
    # Idempotent: same tombstoned_at returned
    assert second.json()["tombstoned_at"] == first.json()["tombstoned_at"]
    # Only one audit row
    audit_rows = [r for r in fresh_store._audit_log if r.get("action") == "revision_tombstoned"]
    assert len(audit_rows) == 1


def test_tombstone_reason_too_long_rejected(client: TestClient, fresh_store: InMemoryStore) -> None:
    token = _make_token()
    resp = client.post(
        "/api/v1/revisions/some-id/tombstone",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "x" * 501},
    )
    # Pydantic validation triggers 422
    assert resp.status_code == 422


def test_tombstone_reason_empty_rejected(client: TestClient, fresh_store: InMemoryStore) -> None:
    token = _make_token()
    resp = client.post(
        "/api/v1/revisions/some-id/tombstone",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": ""},
    )
    assert resp.status_code == 422


def test_confirm_uses_max_plus_one_after_tombstone_gap(
    client: TestClient, fresh_store: InMemoryStore
) -> None:
    """DA exit-council fix-up #P1-3 regression.

    With ``count_active + 1``, after tombstoning revision 2 (active 1, 2, 3),
    a NEW confirm would compute ``next = 2 + 1 = 3`` and 409-collide with
    the still-active revision 3. The product would be unusable post-first-
    tombstone. With ``MAX + 1`` the next revision is correctly 4 — tombstones
    occupy revision_number space.
    """
    parent = fresh_store.save_project(
        upload_id="u-parent",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        xer_bytes=b"parent",
        user_id="user-w2-test",
    )
    children = []
    for i in range(3):
        child = fresh_store.save_project(
            upload_id=f"u-child-{i}",
            schedule=_schedule("PROJ-A", datetime(2026, 2 + i, 1, tzinfo=timezone.utc)),
            xer_bytes=f"child-{i}".encode(),
            user_id="user-w2-test",
        )
        children.append(child)

    token = _make_token()
    confirms = []
    for child in children:
        resp = client.post(
            f"/api/v1/projects/{child}/confirm-revision-of",
            headers={"Authorization": f"Bearer {token}"},
            json={"parent_project_id": parent},
        )
        assert resp.status_code == 200, resp.text
        confirms.append(resp.json())

    assert [c["revision_number"] for c in confirms] == [1, 2, 3]

    # Tombstone the middle one (revision 2)
    middle_revision_id = confirms[1]["revision_id"]
    tomb = client.post(
        f"/api/v1/revisions/{middle_revision_id}/tombstone",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "test gap-fill regression"},
    )
    assert tomb.status_code == 200, tomb.text

    # Now confirm a new child — must be revision 4 (MAX + 1), NOT 3 (count_active + 1)
    new_child = fresh_store.save_project(
        upload_id="u-child-new",
        schedule=_schedule("PROJ-A", datetime(2026, 6, 1, tzinfo=timezone.utc)),
        xer_bytes=b"child-new",
        user_id="user-w2-test",
    )
    new_confirm = client.post(
        f"/api/v1/projects/{new_child}/confirm-revision-of",
        headers={"Authorization": f"Bearer {token}"},
        json={"parent_project_id": parent},
    )
    assert new_confirm.status_code == 200, new_confirm.text
    assert new_confirm.json()["revision_number"] == 4, (
        f"Expected revision_number=4 (MAX over active+tombstoned + 1) but got "
        f"{new_confirm.json()['revision_number']} — gap-fill regression"
    )


def test_tombstone_does_not_leak_state_to_other_user(
    client: TestClient, fresh_store: InMemoryStore
) -> None:
    """DA exit-council fix-up #P2-4 regression: ownership check before idempotent return.

    User A creates + tombstones a revision. User B (any other authenticated user)
    calls tombstone on the same revision_id. The endpoint MUST 404 — NOT
    return User A's tombstoned_at + baseline_lock_at via the idempotent path.
    """
    token_a = _make_token(user_id="user-A")
    parent_a = fresh_store.save_project(
        upload_id="u-A1",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        xer_bytes=b"A1",
        user_id="user-A",
    )
    child_a = fresh_store.save_project(
        upload_id="u-A2",
        schedule=_schedule("PROJ-A", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        xer_bytes=b"A2",
        user_id="user-A",
    )
    confirm_a = client.post(
        f"/api/v1/projects/{child_a}/confirm-revision-of",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"parent_project_id": parent_a},
    )
    revision_a_id = confirm_a.json()["revision_id"]
    tomb_a = client.post(
        f"/api/v1/revisions/{revision_a_id}/tombstone",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"reason": "user A original tombstone"},
    )
    assert tomb_a.status_code == 200

    # User B attempts to tombstone — MUST 404
    token_b = _make_token(user_id="user-B-attacker", email="b@x.com")
    leak_attempt = client.post(
        f"/api/v1/revisions/{revision_a_id}/tombstone",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"reason": "B trying to read A's data"},
    )
    assert leak_attempt.status_code == 404, (
        f"Expected 404 (cross-tenant ownership reject) but got "
        f"{leak_attempt.status_code} — RLS bypass via idempotent tombstone return"
    )
