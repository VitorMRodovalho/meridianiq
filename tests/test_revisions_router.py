# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Cycle 4 W2 PR-A — endpoint tests for src/api/routers/revisions.py.

Covers detect-revision-of, confirm-revision-of, and tombstone-revision
under the InMemoryStore-backed test harness. Uses TestClient + JWT mint.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
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
    detail = resp.json()["detail"]
    assert detail["error_code"] == "current_not_found"
    assert "nonexistent" in detail["message"]


def test_confirm_404_when_parent_missing(client: TestClient, fresh_store: InMemoryStore) -> None:
    """Issue #86: parent_not_found differentiated from current_not_found
    via structured error_code. Frontend auto-collapses on either, but
    distinguishing them lets the UI eventually surface different toast
    text + telemetry distinguishes "user's project moved" from "candidate
    stale".
    """
    p1 = fresh_store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id="user-w2-test",
    )
    token = _make_token()
    resp = client.post(
        f"/api/v1/projects/{p1}/confirm-revision-of",
        headers={"Authorization": f"Bearer {token}"},
        json={"parent_project_id": "missing-parent-id"},
    )
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["error_code"] == "parent_not_found"
    assert "missing-parent-id" in detail["message"]


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
    detail = resp.json()["detail"]
    assert detail["error_code"] == "cross_program"
    assert "not in the same program" in detail["message"]


def test_confirm_409_when_program_id_mutated_after_detect(
    client: TestClient, fresh_store: InMemoryStore
) -> None:
    """Contract probe on the ``get_project_meta.program_id`` read path
    used by ``confirm-revision-of`` (issue #82, DA P3-15 from PR #78).

    Distinct from ``test_confirm_409_when_parent_in_different_program``
    in setup shape: that test pre-creates two projects in DIFFERENT
    programs (PROJ-A vs PROJ-B), then asserts 409. This test pre-creates
    two projects in the SAME auto-grouped program (both PROJ-A), runs
    detect (stateless 200), MUTATES p2's ``program_id`` post-detect, and
    asserts confirm now 409s. Without the mutation the path would 200 —
    the mutation is the load-bearing step.

    What this pins:
        ``confirm-revision-of`` reads ``program_id`` from the live store
        at submission time (via ``get_project_meta``) — not from a value
        cached at detect time. A refactor introducing a detect-cached
        token would have to leave this path intact OR explicitly opt out
        of contract.

    What this does NOT pin (DA exit-council on PR #113 P1 #2):
        No production API re-groups projects today. The store-level
        mutation here is artificial; if a future re-grouping API ships,
        a real-coverage test should land alongside it (touching
        ``_upload_program`` + ``_programs`` per the actual API surface,
        not just ``_project_meta``).
    """
    user_id = "user-w2-test"
    p1 = fresh_store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id=user_id,
    )
    p2 = fresh_store.save_project(
        upload_id="u2",
        schedule=_schedule("PROJ-A", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        user_id=user_id,
    )
    token = _make_token()
    # Detect: stateless read; no state captured by the response.
    client.post(
        f"/api/v1/projects/{p2}/detect-revision-of",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Mutate: schema-shaped program_id (real prog-NNNN value created via
    # get_or_create_program) so the test's stand-in matches the actual
    # FK shape program_id has in production. DA exit-council PR #113 P2 #4.
    other_program_id = fresh_store.get_or_create_program(user_id, "OTHER-PROG")
    fresh_store._project_meta[p2]["program_id"] = other_program_id  # noqa: SLF001
    # Confirm: re-reads program_id from store, sees mismatch, 409s.
    resp = client.post(
        f"/api/v1/projects/{p2}/confirm-revision-of",
        headers={"Authorization": f"Bearer {token}"},
        json={"parent_project_id": p1},
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error_code"] == "cross_program"
    assert "not in the same program" in detail["message"]


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
    detail = resp.json()["detail"]
    assert detail["error_code"] == "cap_reached"
    assert "cap" in detail["message"].lower()


def test_confirm_409_on_no_xer_bytes(
    client: TestClient, fresh_store: InMemoryStore
) -> None:
    """When the upload's XER bytes are missing from storage, confirm cannot
    compute content_hash and must 409 with structured error_code
    ``no_xer_bytes`` (DA exit-council PR #116 P1 #1: pin the code so a
    typo at the dispatch site fails CI).
    """
    parent = fresh_store.save_project(
        upload_id="u-parent",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        xer_bytes=b"parent",
        user_id="user-w2-test",
    )
    # Child with NO xer_bytes — save_project default is empty bytes.
    child = fresh_store.save_project(
        upload_id="u-child-no-bytes",
        schedule=_schedule("PROJ-A", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        xer_bytes=b"",  # explicit empty
        user_id="user-w2-test",
    )
    token = _make_token()
    resp = client.post(
        f"/api/v1/projects/{child}/confirm-revision-of",
        headers={"Authorization": f"Bearer {token}"},
        json={"parent_project_id": parent},
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error_code"] == "no_xer_bytes"
    assert "content_hash" in detail["message"]


def test_confirm_409_on_unique_collision(
    client: TestClient, fresh_store: InMemoryStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the store helper raises a non-cap ValueError (e.g., the UNIQUE
    NULLS NOT DISTINCT collision under concurrent confirms), the router
    must dispatch to error_code ``unique_collision`` (NOT
    ``cap_reached``). Pin the LITERAL via monkeypatch so a typo at the
    dispatch site (revisions.py:215-217 ``"cap_reached" if "cap" in
    message.lower() else "unique_collision"``) fails CI (DA exit-council
    PR #116 P1 #1).

    Concurrent-confirm race is hard to simulate deterministically in a
    TestClient single-thread test — monkeypatch is the cheapest path to
    pin the dispatch literal.
    """
    parent = fresh_store.save_project(
        upload_id="u-parent",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        xer_bytes=b"parent",
        user_id="user-w2-test",
    )
    child = fresh_store.save_project(
        upload_id="u-c",
        schedule=_schedule("PROJ-A", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        xer_bytes=b"child",
        user_id="user-w2-test",
    )

    def _raise_unique_collision(**kwargs: object) -> dict[str, object]:
        # Real Postgres UNIQUE-violation message style; importantly does
        # NOT contain "cap" — the dispatch site routes to unique_collision.
        raise ValueError(
            "duplicate key value violates unique constraint "
            "revision_history_unique_active"
        )

    monkeypatch.setattr(fresh_store, "insert_revision_history", _raise_unique_collision)
    token = _make_token()
    resp = client.post(
        f"/api/v1/projects/{child}/confirm-revision-of",
        headers={"Authorization": f"Bearer {token}"},
        json={"parent_project_id": parent},
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["error_code"] == "unique_collision"
    assert "duplicate key" in detail["message"]


def test_confirm_403_on_permission_denied(
    client: TestClient, fresh_store: InMemoryStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the store helper raises PermissionError, the router must
    surface 403 with structured error_code ``permission_denied`` (DA
    exit-council PR #116 P1 #1: pin the code at the dispatch site).
    """
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

    def _raise_permission_error(**kwargs: object) -> dict[str, object]:
        raise PermissionError("RLS rejected the insert for user user-w2-test")

    monkeypatch.setattr(fresh_store, "insert_revision_history", _raise_permission_error)
    token = _make_token()
    resp = client.post(
        f"/api/v1/projects/{child}/confirm-revision-of",
        headers={"Authorization": f"Bearer {token}"},
        json={"parent_project_id": parent},
    )
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["error_code"] == "permission_denied"
    assert "RLS" in detail["message"]


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


# ────────────────────────────────────────────────────────────
# revision-trends endpoint (Cycle 5 W1 batch 1 — issues #89, #90, #91, #92)
# ────────────────────────────────────────────────────────────


def test_revision_trends_unauth_returns_401(client: TestClient) -> None:
    """Issue #92 / DA P3-6: endpoint integration test — 401 path."""
    resp = client.get("/api/v1/projects/p1/revision-trends")
    assert resp.status_code == 401


def test_revision_trends_404_when_project_missing(
    client: TestClient, fresh_store: InMemoryStore
) -> None:
    """Issue #92 / DA P3-6: endpoint integration test — 404 path."""
    token = _make_token()
    resp = client.get(
        "/api/v1/projects/nonexistent/revision-trends",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_revision_trends_200_owner_happy_path_single_revision(
    client: TestClient, fresh_store: InMemoryStore
) -> None:
    """Issue #92 / DA P3-6: 200 owner path with single revision (no program siblings).

    Assigns a project to a fresh program; no other siblings in the program.
    Endpoint returns curve-only response (single-revision view).
    """
    p1 = fresh_store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-A", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id="user-w2-test",
    )
    token = _make_token()
    resp = client.get(
        f"/api/v1/projects/{p1}/revision-trends",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["project_id"] == p1
    assert "curves" in body
    assert "change_points" in body
    assert "notes" in body
    # methodology citation surfaced
    assert "29R-03" in body["methodology"] or "AACE" in body["methodology"]


def test_revision_trends_200_with_sibling_revisions(
    client: TestClient, fresh_store: InMemoryStore
) -> None:
    """Issue #92 / DA P3-6: 200 owner path with multi-revision (sibling) program."""
    # Two siblings under same proj_short_name → same auto-grouped program.
    p1 = fresh_store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-MR", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id="user-w2-test",
    )
    p2 = fresh_store.save_project(
        upload_id="u2",
        schedule=_schedule("PROJ-MR", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        user_id="user-w2-test",
    )
    token = _make_token()
    resp = client.get(
        f"/api/v1/projects/{p2}/revision-trends",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["project_id"] == p2
    assert len(body["curves"]) >= 1
    # Both siblings should be reachable; no skipped-sibling note for happy path.
    skipped_notes = [n for n in body["notes"] if "skipped" in n.lower()]
    assert not skipped_notes, f"unexpected skipped-sibling note: {skipped_notes}"
    _ = p1  # referenced by sibling lookup


def test_revision_trends_skipped_sibling_in_notes(
    client: TestClient, fresh_store: InMemoryStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #91 / DA P3-3: silent skip masks 'missing' vs 'RLS-denied'.

    Two siblings; monkeypatch `get_project` to return None for sibling p1
    (simulates RLS-denied OR missing). Endpoint surfaces a skipped-sibling
    note + populates the typed `skipped_revisions` list. DA exit-council
    P2 #8 + P2 #11 fix on PR #104: monkeypatch is less brittle than reaching
    into ProjectStore inner dict; the response also exposes the typed field.
    """
    p1 = fresh_store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-SKIP", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id="user-w2-test",
    )
    p2 = fresh_store.save_project(
        upload_id="u2",
        schedule=_schedule("PROJ-SKIP", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        user_id="user-w2-test",
    )
    # Public-API simulation: monkeypatch get_project to return None for p1.
    real_get = fresh_store.get_project

    def _patched_get(pid: str, user_id: str | None = None) -> Any:
        if pid == p1:
            return None
        return real_get(pid, user_id=user_id)

    monkeypatch.setattr(fresh_store, "get_project", _patched_get)
    token = _make_token()
    resp = client.get(
        f"/api/v1/projects/{p2}/revision-trends",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Note-based surfacing (count + reference to typed field).
    skipped_notes = [n for n in body["notes"] if "skipped" in n.lower()]
    assert skipped_notes, (
        f"expected skipped-sibling note when schedule unavailable; got notes={body['notes']}"
    )
    assert "1 sibling" in skipped_notes[0] or "1 sibling revision" in skipped_notes[0]
    # Typed-field surfacing (DA exit-council P2 #8 fix): actual project_ids exposed.
    assert p1 in body["skipped_revisions"], (
        f"expected p1={p1} in skipped_revisions; got {body['skipped_revisions']}"
    )
    assert p2 not in body["skipped_revisions"], (
        f"p2={p2} should NOT be in skipped_revisions (its schedule was returned)"
    )


def test_revision_trends_error_fallback_on_analytics_failure(
    client: TestClient,
    fresh_store: InMemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #90 / DA P3-2: analyze_revision_trends raising MUST NOT 500.

    Patches the analytics function to raise; endpoint should return 200 with
    a partial response carrying ``notes: ['analysis failed: <ExceptionClass>...']``.
    Per ADR-0022 §"W3 — C-visualization": viz ships value even when downstream
    computation fails.
    """
    p1_id = fresh_store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-ERR", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id="user-w2-test",
    )

    def _raise(*args: Any, **kwargs: Any) -> Any:
        # ValueError simulates a data-edge case the fallback IS expected to
        # catch per DA exit-council P1 #7 narrowing on PR #104. RuntimeError
        # would propagate as 500 (programming-bug class), which is the
        # correct behavior — see test_revision_trends_programming_bug_propagates.
        raise ValueError("synthetic numpy edge-case for issue #90 test")

    monkeypatch.setattr("src.api.routers.revisions.analyze_revision_trends", _raise)
    token = _make_token()
    resp = client.get(
        f"/api/v1/projects/{p1_id}/revision-trends",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    failure_notes = [n for n in body["notes"] if "analysis failed" in n.lower()]
    assert failure_notes, (
        f"expected 'analysis failed' note on synthetic exception; got notes={body['notes']}"
    )
    assert "ValueError" in failure_notes[0]
    # P1 #5 fix: methodology MUST be cleared on fallback path so the response
    # does NOT carry the AACE 29R-03 citation as if the analysis ran.
    assert body["methodology"] == "", (
        f"expected empty methodology on fallback (P1 #5 fix); got {body['methodology']!r}"
    )


def test_revision_trends_programming_bug_propagates_as_500(
    client: TestClient,
    fresh_store: InMemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DA exit-council P1 #7 fix on PR #104: programming bugs (TypeError,
    AttributeError, KeyError, RuntimeError) MUST propagate as 500, NOT be
    swallowed by the fallback. The narrow exception catch in
    `_analyze_with_fallback` only catches data-edge errors (ValueError,
    ArithmeticError, FloatingPointError, np.linalg.LinAlgError).

    A wider catch would silently degrade programming bugs to "analysis
    failed: TypeError" with no Sentry trip, hiding regressions indefinitely.
    """
    p1_id = fresh_store.save_project(
        upload_id="u1",
        schedule=_schedule("PROJ-BUG", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        user_id="user-w2-test",
    )

    def _raise_typeerror(*args: Any, **kwargs: Any) -> Any:
        raise TypeError("synthetic programming-bug — should propagate, not degrade")

    monkeypatch.setattr("src.api.routers.revisions.analyze_revision_trends", _raise_typeerror)
    token = _make_token()
    # FastAPI/TestClient surfaces uncaught exceptions as 500.
    # Use raise_server_exceptions=False to capture the 500 response.
    test_client = TestClient(app, raise_server_exceptions=False)
    resp = test_client.get(
        f"/api/v1/projects/{p1_id}/revision-trends",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 500, (
        f"TypeError MUST propagate as 500 (programming bug class); got {resp.status_code}"
    )


def test_revision_trends_change_point_carries_direction_field(
    client: TestClient, fresh_store: InMemoryStore
) -> None:
    """Issue #89 / DA P3-1 + DA exit-council P0 #3 fix on PR #104.

    Earlier draft used a single-revision construction that NEVER produces
    change_points (CUSUM requires N≥5 revisions); the for-loop iterated
    zero times and the test was VACUOUSLY passing. Fixed by constructing
    9 sibling revisions with the same shifts that the analytic-level test
    `test_change_point_marker_direction_slip_when_local_delta_positive`
    uses, so the endpoint actually emits change_points + the API surface
    contract on `direction` is non-vacuously verified.
    """
    # Same finish-offset construction as the analytic-level slip test:
    # shifts [200, 200, 40×6] → fires at idx=1 with direction='slip'.
    finish_offsets = [10, 180, 350, 360, 370, 380, 390, 400, 410]
    project_ids: list[str] = []
    base_dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i, fd in enumerate(finish_offsets):
        # Schedule with single activity whose duration_hr = fd*8 (8hr/day) →
        # planned_finish_day = fd days. Same convention as test_revision_trends.py.
        from src.parser.models import Task

        sched = ParsedSchedule()
        sched.projects.append(
            Project(
                proj_id="1",
                proj_short_name="PROJ-DIR-MR",
                last_recalc_date=base_dt + timedelta(days=30 * i),
            )
        )
        sched.activities = [
            Task(
                task_id="t1",
                target_drtn_hr_cnt=float(fd) * 8.0,
                remain_drtn_hr_cnt=float(fd) * 8.0,
                target_end_date=base_dt + timedelta(days=30 * i),
            )
        ]
        pid = fresh_store.save_project(upload_id=f"u{i}", schedule=sched, user_id="user-w2-test")
        project_ids.append(pid)

    # Query against the LATEST revision (last project_id); endpoint resolves
    # siblings via auto-grouped program_id and analyzes all 9 revisions.
    token = _make_token()
    resp = client.get(
        f"/api/v1/projects/{project_ids[-1]}/revision-trends",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The 9-revision construction MUST produce ≥1 change_point per analytic-
    # level test guarantees; the API surface contract on `direction` is now
    # actually verified.
    assert body["change_points"], (
        f"expected ≥1 change_point on 9-revision construction (API surface "
        f"contract for direction field); got notes={body['notes']}"
    )
    for cp in body["change_points"]:
        assert "direction" in cp, "API surface MUST include direction field"
        assert cp["direction"] in ("slip", "improvement", "flat"), cp["direction"]
        # Sign-consistency contract per DA exit-council P0 #1 fix: direction
        # follows sign(delta_days), NOT sign(cusum_value).
        if cp["delta_days"] > 0:
            assert cp["direction"] == "slip"
        elif cp["delta_days"] < 0:
            assert cp["direction"] == "improvement"
        else:
            assert cp["direction"] == "flat"
