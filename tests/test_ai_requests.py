# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Requests for AI access (migration 036, src/api/ai_gate.py).

A signed-in user asks from the closed /ask panel; the operator is emailed
once per new request, without the requester's details, and approves or
dismisses it on /admin/ai. Runs in production mode with real tokens and the
in-memory store; scripts/rls_replica/036/scenarios.sql runs the same rules
against the SQL functions.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import jwt
import pytest
from fastapi import BackgroundTasks

from src.api import ai_gate
from src.api.access import Principal
from src.api.sentry_scrub import scrub_ai_event
from src.database.store import AI_REQUEST_COOLDOWN, InMemoryStore
from tests.test_ai_gate import ADMIN, USER_A, USER_B, Gate, _auth

URL = "/api/v1/ai/access-request"
USER_C = "00000000-0000-4000-8000-0000000c0c03"  # not entitled, no address


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Gate:
    return Gate(monkeypatch)


@pytest.fixture
def alerts(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Every operator alert the request path queues."""
    sent: list[dict[str, Any]] = []

    def record(alert: dict[str, str], *, label: str) -> None:
        sent.append({"alert": alert, "label": label})

    monkeypatch.setattr(ai_gate, "notify_operator", record)
    return sent


def _request(gate: Gate, user: str = USER_B, note: str | None = None) -> Any:
    return gate.client.post(URL, json={"note": note}, headers=_auth(user))


def _code(resp: Any) -> str:
    return str(resp.json()["detail"]["error_code"])


# ------------------------------------------------------------------ #
# The user's side                                                    #
# ------------------------------------------------------------------ #


def test_request_is_offered_while_ai_is_off_for_everyone(
    gate: Gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_ENABLED", "")
    body = gate.status(USER_B)
    assert (body["reason"], body["access"]) == ("ai_disabled", "none")
    assert body["access_requested_at"] is None and body["access_retry_after"] is None


def test_request_fields_stay_empty_outside_the_requestable_states(gate: Gate) -> None:
    empty = (None, None, None)

    def fields(body: dict[str, Any]) -> tuple[Any, Any, Any]:
        return (body["access"], body["access_requested_at"], body["access_retry_after"])

    assert fields(gate.status(USER_A)) == empty  # available
    gate.grant(USER_A, daily=0)
    exhausted = gate.status(USER_A)
    assert exhausted["reason"] == "ai_daily_quota" and fields(exhausted) == empty


def test_first_request_is_created_and_the_operator_is_emailed_once(
    gate: Gate, alerts: list[dict[str, Any]]
) -> None:
    first = _request(gate, note="Weekly look-ahead questions")
    assert first.status_code == 200, first.text
    assert first.json()["state"] == "created" and first.json()["requested_at"]
    again = _request(gate, note="Updated reason")
    assert again.json()["state"] == "pending"
    assert again.json()["requested_at"] == first.json()["requested_at"]  # place kept
    assert len(alerts) == 1
    status = gate.status(USER_B)
    assert (status["access"], status["access_requested_at"]) == (
        "pending",
        first.json()["requested_at"],
    )
    assert gate.store._ai_requests[USER_B]["note"] == "Updated reason"


def test_the_alert_carries_nothing_about_the_requester(
    gate: Gate, alerts: list[dict[str, Any]]
) -> None:
    _request(gate, note="PRIVATE-NOTE-TEXT")
    (sent,) = alerts
    text = sent["alert"]["subject"] + sent["alert"]["text"]
    for private in (USER_B, "b@example.test", "PRIVATE-NOTE-TEXT"):
        assert private not in text
    assert "/admin/ai" in text


def test_entitled_account_is_told_so_and_nothing_is_sent(
    gate: Gate, alerts: list[dict[str, Any]]
) -> None:
    resp = _request(gate, user=USER_A)
    assert resp.json() == {"state": "entitled", "requested_at": None, "retry_after": None}
    assert alerts == []
    assert USER_A not in gate.store._ai_requests


def test_only_a_signed_in_person_may_ask(gate: Gate) -> None:
    assert gate.client.post(URL, json={}).status_code == 401
    for kind in ("api_key", "dev"):
        with pytest.raises(Exception) as err:
            ai_gate.request_access(
                Principal(USER_B, kind),  # type: ignore[arg-type]
                gate.store,
                None,
                BackgroundTasks(),
            )
        assert getattr(err.value, "status_code", None) == 403


def test_non_durable_store_refuses_rather_than_email_about_a_lost_row(
    gate: Gate, monkeypatch: pytest.MonkeyPatch, alerts: list[dict[str, Any]]
) -> None:
    monkeypatch.setattr(ai_gate, "ledger_is_durable", lambda store: False)
    resp = _request(gate)
    assert (resp.status_code, _code(resp)) == (500, "ai_request_unavailable")
    assert alerts == []


def test_store_failures_fail_safe(
    gate: Gate, monkeypatch: pytest.MonkeyPatch, alerts: list[dict[str, Any]]
) -> None:
    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("function ai_request_access does not exist")

    monkeypatch.setattr(gate.store, "ai_request_access", broken)
    monkeypatch.setattr(gate.store, "ai_access_state", broken)
    resp = _request(gate)
    assert (resp.status_code, _code(resp)) == (500, "ai_request_unavailable")
    assert "does not exist" not in resp.text
    status = gate.status(USER_B)  # the plain panel, not an error
    assert (status["reason"], status["access"]) == ("ai_not_entitled", None)
    assert alerts == []


@pytest.mark.parametrize(
    ("note", "expected"),
    [
        ("x" * 501, 422),
        ("line\x00break", 422),
        ("bell\x07", 422),
        ("c1\x85x", 422),
        ("sep\u2028x", 422),
        ("  ", 200),
        ("a\nb\tc", 200),
    ],
)
def test_note_validation(gate: Gate, note: str, expected: int) -> None:
    assert _request(gate, note=note).status_code == expected


def test_blank_note_is_stored_as_none(gate: Gate) -> None:
    _request(gate, note="   ")
    assert gate.store._ai_requests[USER_B]["note"] is None


def test_concurrent_requests_create_one(alerts: list[dict[str, Any]]) -> None:
    store = InMemoryStore()
    results: list[str] = []
    lock = threading.Lock()
    start = threading.Barrier(20)

    def ask() -> None:
        start.wait()
        state = store.ai_request_access(USER_B, None)
        with lock:
            results.append(state.state)

    threads = [threading.Thread(target=ask) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["created"] + ["pending"] * 19


# ------------------------------------------------------------------ #
# The operator's side                                                #
# ------------------------------------------------------------------ #


def test_operator_sees_pending_requests_with_address_and_note(gate: Gate) -> None:
    _request(gate, note="Weekly look-ahead questions")
    body = gate.client.get("/api/v1/superadmin/ai", headers=_auth(ADMIN)).json()
    assert body["requests_total"] == 1
    (item,) = body["requests"]
    assert item["user_id"] == USER_B and item["email"] == "b@example.test"
    assert item["note"] == "Weekly look-ahead questions" and item["requested_at"]


def test_approve_grants_defaults_closes_the_request_and_clears_the_note(gate: Gate) -> None:
    _request(gate, note="reason")
    url = f"/api/v1/superadmin/ai/requests/{USER_B}/approve"
    resp = gate.client.post(url, headers=_auth(ADMIN))
    assert resp.status_code == 200, resp.text
    ent = resp.json()
    assert ent["user_id"] == USER_B and ent["active"] is True
    assert ent["daily_questions"] is None and ent["monthly_budget_usd"] is None
    req = gate.store._ai_requests[USER_B]
    assert (req["status"], req["note"], req["decided_by"]) == ("approved", None, ADMIN)
    assert gate.status(USER_B)["available"] is True
    again = gate.client.post(url, headers=_auth(ADMIN))
    assert (again.status_code, _code(again)) == (404, "ai_request_not_found")
    actions = [r["action"] for r in gate.store._audit_log]
    assert actions.count("ai_access_granted") == 2  # the fixture's grant of A, then B's


def test_dismiss_blocks_a_new_request_for_30_days(gate: Gate, alerts: list[dict[str, Any]]) -> None:
    _request(gate, note="reason")
    url = f"/api/v1/superadmin/ai/requests/{USER_B}"
    assert gate.client.delete(url, headers=_auth(ADMIN)).json() == {"dismissed": True}
    req = gate.store._ai_requests[USER_B]
    assert (req["status"], req["note"]) == ("dismissed", None)
    status = gate.status(USER_B)
    assert status["access"] == "dismissed"
    retry = datetime.fromisoformat(status["access_retry_after"])
    assert abs(retry - (req["decided_at"] + AI_REQUEST_COOLDOWN)) < timedelta(seconds=1)
    blocked = _request(gate)
    assert blocked.json()["state"] == "dismissed" and blocked.json()["retry_after"]
    assert len(alerts) == 1
    # After the cooldown the account may ask again, and the operator hears of it.
    req["decided_at"] = datetime.now(UTC) - AI_REQUEST_COOLDOWN - timedelta(minutes=1)
    assert _request(gate).json()["state"] == "created"
    assert len(alerts) == 2
    again = gate.client.delete(f"/api/v1/superadmin/ai/requests/{ADMIN}", headers=_auth(ADMIN))
    assert (again.status_code, _code(again)) == (404, "ai_request_not_found")
    assert any(r["action"] == "ai_access_request_dismissed" for r in gate.store._audit_log)


def test_a_grant_from_the_form_closes_the_pending_request(gate: Gate) -> None:
    _request(gate)
    gate.client.post(
        "/api/v1/superadmin/ai/entitlements",
        json={"email": "b@example.test", "daily_questions": 3},
        headers=_auth(ADMIN),
    )
    assert gate.store._ai_requests[USER_B]["status"] == "approved"
    body = gate.client.get("/api/v1/superadmin/ai", headers=_auth(ADMIN)).json()
    assert body["requests"] == [] and body["requests_total"] == 0


def test_a_revoked_account_waits_30_days_to_ask_again(gate: Gate) -> None:
    _request(gate)
    gate.client.post(f"/api/v1/superadmin/ai/requests/{USER_B}/approve", headers=_auth(ADMIN))
    gate.store.ai_revoke(user_id=USER_B, revoked_by=ADMIN)
    assert _request(gate).json()["state"] == "dismissed"
    # Both moments in the past, in their real order: approved, then revoked.
    gate.store._ai_requests[USER_B]["decided_at"] = datetime.now(UTC) - timedelta(days=40)
    ent = gate.store._ai_entitlements[USER_B]
    ent["revoked_at"] = datetime.now(UTC) - AI_REQUEST_COOLDOWN - timedelta(minutes=1)
    assert _request(gate).json()["state"] == "created"


def test_a_recent_decision_is_not_reopened_even_without_a_cooldown_mark(gate: Gate) -> None:
    """Mirror of the SQL conflict condition (the race case, in the fake)."""
    _request(gate)
    gate.client.post(f"/api/v1/superadmin/ai/requests/{USER_B}/approve", headers=_auth(ADMIN))
    # Remove the entitlement entirely: no active access and no revocation mark,
    # only a decision made just now.
    del gate.store._ai_entitlements[USER_B]
    assert _request(gate).json()["state"] == "dismissed"


def test_unreadable_requests_are_null_not_empty(
    gate: Gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("function ai_pending_requests does not exist")

    monkeypatch.setattr(gate.store, "ai_pending_requests", broken)
    body = gate.client.get("/api/v1/superadmin/ai", headers=_auth(ADMIN)).json()
    assert body["requests"] is None and body["requests_total"] is None
    assert body["entitlements"] and body["available"] is True  # the rest stands


def test_operator_routes_are_guarded(gate: Gate) -> None:
    approve = f"/api/v1/superadmin/ai/requests/{USER_B}/approve"
    assert gate.client.post(approve).status_code == 401
    assert gate.client.post(approve, headers=_auth(USER_A)).status_code == 403
    malformed = gate.client.post(
        "/api/v1/superadmin/ai/requests/not-a-uuid/approve", headers=_auth(ADMIN)
    )
    assert (malformed.status_code, _code(malformed)) == (404, "ai_request_not_found")


def test_anonymous_sign_ins_cannot_ask(gate: Gate, alerts: list[dict[str, Any]]) -> None:
    now = int(time.time())
    claims = {"sub": USER_B, "aud": "authenticated", "role": "authenticated", "iat": now}
    claims.update(exp=now + 3600, is_anonymous=True)
    token = jwt.encode(claims, "test-secret", algorithm="HS256")
    resp = gate.client.post(URL, json={}, headers={"Authorization": f"Bearer {token}"})
    assert (resp.status_code, _code(resp)) == (403, "ai_session_required")
    assert alerts == [] and USER_B not in gate.store._ai_requests


def test_invisible_reordering_characters_are_removed_from_the_note(gate: Gate) -> None:
    assert _request(gate, note="x\u202egnp.exe\u200b").status_code == 200
    assert gate.store._ai_requests[USER_B]["note"] == "xgnp.exe"


def test_dismiss_route_is_guarded(gate: Gate) -> None:
    url = f"/api/v1/superadmin/ai/requests/{USER_B}"
    assert gate.client.delete(url).status_code == 401
    refused = gate.client.delete(url, headers=_auth(USER_A))
    assert (refused.status_code, _code(refused)) == (403, "superadmin_required")
    malformed = gate.client.delete(
        "/api/v1/superadmin/ai/requests/not-a-uuid", headers=_auth(ADMIN)
    )
    assert (malformed.status_code, _code(malformed)) == (404, "ai_request_not_found")


def test_approving_an_account_with_active_access_keeps_its_limits(gate: Gate) -> None:
    _request(gate)
    # A grant from the form that raced the request: the request stays pending.
    gate.store._ai_entitlements[USER_B] = {
        "user_id": USER_B,
        "email": "b@example.test",
        "granted_by": ADMIN,
        "granted_at": datetime.now(UTC),
        "revoked_at": None,
        "revoked_by": None,
        "daily_questions": 200,
        "monthly_budget_usd": Decimal("40"),
        "note": "custom",
    }
    resp = gate.client.post(
        f"/api/v1/superadmin/ai/requests/{USER_B}/approve", headers=_auth(ADMIN)
    )
    assert resp.status_code == 200
    ent = gate.store._ai_entitlements[USER_B]
    assert (ent["daily_questions"], ent["monthly_budget_usd"], ent["note"]) == (
        200,
        Decimal("40"),
        "custom",
    )
    assert gate.store._ai_requests[USER_B]["status"] == "approved"


def test_approval_without_a_confirmed_address_stores_none(gate: Gate) -> None:
    stranger = "00000000-0000-4000-8000-0000000c0c03"  # no registered address
    gate.store.ai_request_access(stranger, None)
    assert gate.store.ai_approve_request(user_id=stranger, approved_by=ADMIN) is True
    assert gate.store._ai_entitlements[stranger]["email"] is None


def test_any_revocation_blocks_a_new_request_for_30_days(gate: Gate) -> None:
    # Access granted from the form (no request), then revoked.
    gate.grant(USER_B)
    gate.store.ai_revoke(user_id=USER_B, revoked_by=ADMIN)
    blocked = _request(gate)
    assert blocked.json()["state"] == "dismissed" and blocked.json()["retry_after"]


def test_store_failures_on_operator_actions_keep_the_error_contract(
    gate: Gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    _request(gate)

    def broken(**kwargs: Any) -> Any:
        raise RuntimeError("connection reset")

    for name, method, url, code in (
        (
            "ai_approve_request",
            "post",
            f"/api/v1/superadmin/ai/requests/{USER_B}/approve",
            "ai_request_unavailable",
        ),
        (
            "ai_dismiss_request",
            "delete",
            f"/api/v1/superadmin/ai/requests/{USER_B}",
            "ai_request_unavailable",
        ),
        (
            "ai_revoke",
            "delete",
            f"/api/v1/superadmin/ai/entitlements/{USER_A}",
            "ai_ledger_unavailable",
        ),
    ):
        monkeypatch.setattr(gate.store, name, broken)
        resp = getattr(gate.client, method)(url, headers=_auth(ADMIN))
        assert (resp.status_code, _code(resp)) == (500, code), name
        assert "connection reset" not in resp.text


def test_data_erasure_clears_the_note_and_the_address_copy(gate: Gate) -> None:
    _request(gate, note="a private note")
    gate.client.post(f"/api/v1/superadmin/ai/requests/{USER_B}/approve", headers=_auth(ADMIN))
    _request(gate, user=USER_A)  # entitled: no row, nothing to remove
    assert gate.store._ai_entitlements[USER_B]["email"] == "b@example.test"
    resp = gate.client.delete("/api/v1/user/data", headers=_auth(USER_B))
    assert resp.status_code == 200, resp.text
    row = gate.store._ai_requests[USER_B]
    assert (row["status"], row["note"]) == ("approved", None)  # the record stays
    assert gate.store._ai_entitlements[USER_B]["email"] is None
    assert gate.store._ai_entitlements[USER_B]["revoked_at"] is None  # access itself stays


def test_data_erasure_withdraws_a_pending_request_and_its_note(gate: Gate) -> None:
    _request(gate, note="a private note")
    resp = gate.client.delete("/api/v1/user/data", headers=_auth(USER_B))
    assert resp.status_code == 200, resp.text
    row = gate.store._ai_requests[USER_B]
    assert (row["status"], row["note"], row["decided_by"]) == ("dismissed", None, None)
    listing = gate.client.get("/api/v1/superadmin/ai", headers=_auth(ADMIN)).json()
    assert listing["requests"] == []  # the operator no longer sees it


def test_erasure_does_not_reopen_requests_or_alerts(
    gate: Gate, alerts: list[dict[str, Any]]
) -> None:
    """request -> erase -> request used to create a new request and a new email each time."""
    assert _request(gate).json()["state"] == "created"
    gate.client.post(f"/api/v1/superadmin/ai/requests/{USER_B}/dismiss", headers=_auth(ADMIN))
    for _ in range(3):
        assert gate.client.delete("/api/v1/user/data", headers=_auth(USER_B)).status_code == 200
        assert _request(gate).json()["state"] == "dismissed"
    assert len(alerts) == 1


def test_erasing_a_pending_request_blocks_a_new_one(
    gate: Gate, alerts: list[dict[str, Any]]
) -> None:
    assert _request(gate).json()["state"] == "created"
    gate.client.delete("/api/v1/user/data", headers=_auth(USER_B))
    body = _request(gate).json()
    assert body["state"] == "dismissed" and body["retry_after"] is not None
    assert len(alerts) == 1


def test_operator_alerts_stop_at_the_hourly_cap(
    gate: Gate, monkeypatch: pytest.MonkeyPatch, alerts: list[dict[str, Any]]
) -> None:
    monkeypatch.setenv("AI_REQUEST_ALERTS_PER_HOUR", "1")
    assert _request(gate, user=USER_B).json()["state"] == "created"
    assert _request(gate, user=USER_C).json()["state"] == "created"
    assert len(alerts) == 1  # the second request is recorded but not emailed
    listing = gate.client.get("/api/v1/superadmin/ai", headers=_auth(ADMIN)).json()
    assert {r["user_id"] for r in listing["requests"]} == {USER_C, USER_B}


def test_old_requests_do_not_count_toward_the_cap(
    gate: Gate, monkeypatch: pytest.MonkeyPatch, alerts: list[dict[str, Any]]
) -> None:
    monkeypatch.setenv("AI_REQUEST_ALERTS_PER_HOUR", "1")
    _request(gate, user=USER_C)
    gate.store._ai_requests[USER_C]["requested_at"] -= timedelta(hours=2)
    _request(gate, user=USER_B)
    assert len(alerts) == 2


@pytest.mark.parametrize(("value", "sent"), [("0", 0), ("junk", 1), ("", 1)])
def test_alert_cap_setting(
    gate: Gate,
    monkeypatch: pytest.MonkeyPatch,
    alerts: list[dict[str, Any]],
    value: str,
    sent: int,
) -> None:
    monkeypatch.setenv("AI_REQUEST_ALERTS_PER_HOUR", value)
    _request(gate)
    assert len(alerts) == sent


def test_no_alert_when_the_count_cannot_be_read(
    gate: Gate, monkeypatch: pytest.MonkeyPatch, alerts: list[dict[str, Any]]
) -> None:
    def broken(since: datetime) -> int:
        raise RuntimeError("connection reset")

    monkeypatch.setattr(gate.store, "ai_requests_since", broken)
    assert _request(gate).json()["state"] == "created"
    assert alerts == []


def test_approving_an_already_entitled_account_is_audited(gate: Gate) -> None:
    _request(gate)
    gate.grant(USER_B)  # the form grant closes the request ...
    gate.store._ai_requests[USER_B].update(status="pending", decided_at=None, decided_by=None)
    resp = gate.client.post(
        f"/api/v1/superadmin/ai/requests/{USER_B}/approve", headers=_auth(ADMIN)
    )
    assert resp.status_code == 200, resp.text
    actions = [r["action"] for r in gate.store._audit_log if r["entity_id"] == USER_B]
    assert actions[-1] == "ai_access_request_approved"


def test_error_reports_drop_request_notes() -> None:
    """Unit view; tests/test_sentry_ai_scrub.py runs a real request end to end."""

    def event(url: str | None) -> dict[str, Any]:
        frames = [
            {
                "module": "src.database.store",
                "function": "ai_request_access",
                "vars": {"note": "s"},
            },
            {"module": "src.database.store", "function": "_rpc_bool", "vars": {"params": "s"}},
            {"module": "src.database.store", "function": "get", "vars": {"x": 1}},
        ]
        out: dict[str, Any] = {"exception": {"values": [{"stacktrace": {"frames": frames}}]}}
        if url:
            out["request"] = {"url": url, "data": {"note": "s"}}
        return out

    def kept(e: dict[str, Any]) -> list[bool]:
        return [("vars" in f) for f in e["exception"]["values"][0]["stacktrace"]["frames"]]

    on_route = scrub_ai_event(event("https://api.example/api/v1/ai/access-request"), {})
    assert kept(on_route) == [False, False, False] and "data" not in on_route["request"]
    # No request (a background task): the store's AI frames still lose their locals.
    assert kept(scrub_ai_event(event(None), {})) == [False, False, True]


def test_error_reports_hide_the_requester_id_and_breadcrumbs() -> None:
    uid = "00000000-0000-4000-8000-0000000b1b02"
    event: dict[str, Any] = {
        "request": {"url": f"https://api.example/api/v1/superadmin/ai/requests/{uid}/approve"},
        "breadcrumbs": {"values": [{"message": "anything logged meanwhile"}]},
    }
    out = scrub_ai_event(event, {})
    assert uid not in str(out)
    assert out["request"]["url"].endswith("/requests/{id}/approve")
    assert "breadcrumbs" not in out


def test_other_routes_keep_ids_and_breadcrumbs() -> None:
    uid = "00000000-0000-4000-8000-0000000b1b02"
    event: dict[str, Any] = {
        "request": {"url": f"https://api.example/api/v1/projects/{uid}"},
        "breadcrumbs": {"values": [{"message": "m"}]},
    }
    out = scrub_ai_event(event, {})
    assert uid in out["request"]["url"] and "breadcrumbs" in out


def test_a_failed_ai_erasure_is_reported_as_partial(
    gate: Gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(user_id: str) -> None:
        raise RuntimeError("connection reset")

    monkeypatch.setattr(gate.store, "ai_forget_user", broken)
    resp = gate.client.delete("/api/v1/user/data", headers=_auth(USER_B))
    assert (resp.status_code, resp.json()["status"]) == (200, "partial")
