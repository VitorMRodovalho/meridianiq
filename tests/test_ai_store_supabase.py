# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""SupabaseStore's AI ledger methods, through the real postgrest client.

The requests go through postgrest-py over an httpx MockTransport, so the
URL, the JSON body and the parsing of each answer shape are the library's
own. Every RPC's parameter names are checked against the function's
signature in migration 035, so renaming one side fails here instead of
failing closed in production. PostgREST's own server-side conversion of a
JSON string to ``numeric`` is not exercised.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from postgrest import SyncPostgrestClient

from src.database.store import SupabaseStore

MIGRATIONS = Path(__file__).resolve().parent.parent / "supabase" / "migrations"
U = "00000000-0000-4000-8000-0000000a1a01"


def _signature(function: str) -> set[str]:
    """Parameter names of ``public.<function>`` as its LAST migration defines it."""
    found: set[str] | None = None
    for path in sorted(MIGRATIONS.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(
            rf"create or replace function public\.{function}\((.*?)\)\s*returns", text, re.I | re.S
        ):
            found = {line.split()[0] for line in m.group(1).split(",") if line.strip()}
    if found is None:
        raise AssertionError(f"no function public.{function} in the migrations")
    return found


class Recorder:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, str, dict[str, Any] | list[Any] | None]] = []
        self.answers: dict[str, tuple[int, str]] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        name = request.url.path.rsplit("/", 1)[-1]
        self.requests.append((request.method, name, str(request.url.query, "ascii"), body))
        status, payload = self.answers[name]
        return httpx.Response(
            status, content=payload.encode(), headers={"content-type": "application/json"}
        )

    def body(self, name: str) -> dict[str, Any]:
        for _, n, _, body in reversed(self.requests):
            if n == name:
                assert isinstance(body, dict)
                return body
        raise AssertionError(f"no request to {name}")


@pytest.fixture
def wire() -> tuple[SupabaseStore, Recorder]:
    recorder = Recorder()
    http = httpx.Client(
        base_url="http://pgrst.test/rest/v1", transport=httpx.MockTransport(recorder)
    )
    store = object.__new__(SupabaseStore)
    store._client = SyncPostgrestClient("http://pgrst.test/rest/v1", http_client=http)
    return store, recorder


def _reserve(store: SupabaseStore, reserve: str = "0.064") -> tuple[int | None, str | None]:
    return store.ai_reserve(
        user_id=U,
        project_id=None,
        reserve_usd=Decimal(reserve),
        default_daily=20,
        default_account_usd=Decimal("5"),
        global_budget_usd=Decimal("50"),
        model="m",
        price_input=Decimal("3"),
        price_output=Decimal("15"),
    )


def test_quota_parses_the_table_row(wire: tuple[SupabaseStore, Recorder]) -> None:
    store, rec = wire
    rec.answers["ai_quota"] = (
        200,
        json.dumps(
            [
                {
                    "entitled": True,
                    "daily_limit": 20,
                    "used_today": 1,
                    "account_budget_usd": "5.000000",
                    "account_spent_usd": "0.012000",
                    "global_spent_usd": "0.012000",
                }
            ]
        ),
    )
    q = store.ai_quota(U, 20, Decimal("5"))
    assert (q.entitled, q.daily_limit, q.used_today) == (True, 20, 1)
    assert q.account_spent_usd == Decimal("0.012")
    assert set(rec.body("ai_quota")) == _signature("ai_quota")
    assert rec.body("ai_quota")["p_default_account_usd"] == "5"


def test_reserve_sends_money_as_text_and_parses_both_answers(
    wire: tuple[SupabaseStore, Recorder],
) -> None:
    store, rec = wire
    rec.answers["ai_reserve"] = (200, json.dumps([{"reservation_id": 7, "reason": None}]))
    assert _reserve(store) == (7, None)
    body = rec.body("ai_reserve")
    assert set(body) == _signature("ai_reserve")
    assert body["p_reserve_usd"] == "0.064" and body["p_price_output"] == "15"
    rec.answers["ai_reserve"] = (
        200,
        json.dumps([{"reservation_id": None, "reason": "ai_daily_quota"}]),
    )
    assert _reserve(store, "1E-6") == (None, "ai_daily_quota")
    assert rec.body("ai_reserve")["p_reserve_usd"] == "0.000001"


def test_reserve_fails_closed_on_errors_and_empty_answers(
    wire: tuple[SupabaseStore, Recorder],
) -> None:
    store, rec = wire
    rec.answers["ai_reserve"] = (404, json.dumps({"code": "PGRST202", "message": "not found"}))
    with pytest.raises(Exception):
        _reserve(store)
    rec.answers["ai_reserve"] = (200, "[]")
    with pytest.raises(RuntimeError):
        _reserve(store)


def test_settle_reads_the_boolean(wire: tuple[SupabaseStore, Recorder]) -> None:
    store, rec = wire
    for payload, expected in (("true", True), ("false", False)):
        rec.answers["ai_settle"] = (200, payload)
        assert store.ai_settle(7, "completed", 1200, 300, Decimal("0.0081")) is expected
    body = rec.body("ai_settle")
    assert set(body) == _signature("ai_settle")
    assert body["p_cost_usd"] == "0.0081"


def test_grant_and_revoke_are_single_rpcs(wire: tuple[SupabaseStore, Recorder]) -> None:
    store, rec = wire
    rec.answers["ai_grant"] = (200, "null")
    store.ai_grant(
        user_id=U,
        email="a@example.test",
        granted_by=U,
        daily_questions=3,
        monthly_budget_usd=Decimal("1.5"),
        note=None,
        ip_address="1.2.3.4",
        user_agent="ua",
    )
    body = rec.body("ai_grant")
    assert set(body) == _signature("ai_grant")
    assert body["p_monthly_budget_usd"] == "1.5"
    rec.answers["ai_revoke"] = (200, "true")
    assert store.ai_revoke(user_id=U, revoked_by=U) is True
    assert set(rec.body("ai_revoke")) == _signature("ai_revoke")
    rec.answers["ai_revoke"] = (200, "false")
    assert store.ai_revoke(user_id=U, revoked_by=U) is False
    # Nothing else was written: the audit row is inside the functions.
    assert {name for _, name, _, _ in rec.requests} == {"ai_grant", "ai_revoke"}


def test_admin_report_parses_the_json_object(wire: tuple[SupabaseStore, Recorder]) -> None:
    store, rec = wire
    rec.answers["ai_admin_report"] = (
        200,
        json.dumps(
            {
                "global_spent_month_usd": "0.020000",
                "month_calls": {"reserved": 0, "completed": 3, "failed": 1, "unknown": 0},
                "last_failure_at": "2026-09-27T12:00:00+00:00",
                "stale_reservations": 1,
                "entitlements": [
                    {
                        "user_id": U,
                        "email": "a@example.test",
                        "active": True,
                        "granted_at": "2026-09-27T12:00:00.123+00:00",
                        "revoked_at": None,
                        "daily_questions": None,
                        "monthly_budget_usd": "1.500000",
                        "note": None,
                        "used_today": 1,
                        "spent_month_usd": "0.020000",
                    }
                ],
            }
        ),
    )
    r = store.ai_admin_report(20, Decimal("5"))
    assert r["global_spent_month_usd"] == Decimal("0.02")
    assert r["month_calls"] == {"reserved": 0, "completed": 3, "failed": 1, "unknown": 0}
    assert r["stale_reservations"] == 1
    (ent,) = r["entitlements"]
    assert ent["monthly_budget_usd"] == Decimal("1.5") and ent["spent_month_usd"] == Decimal("0.02")
    assert set(rec.body("ai_admin_report")) == _signature("ai_admin_report")


def test_email_lookup_canonicalises_or_answers_none(wire: tuple[SupabaseStore, Recorder]) -> None:
    store, rec = wire
    rec.answers["auth_user_id_for_email"] = (200, json.dumps(U.upper()))
    assert store.user_id_for_email("a@example.test") == U
    rec.answers["auth_user_id_for_email"] = (200, "null")
    assert store.user_id_for_email("x@example.test") is None
    assert set(rec.body("auth_user_id_for_email")) == _signature("auth_user_id_for_email")


def test_signature_reader_negative_control() -> None:
    with pytest.raises(AssertionError):
        _signature("no_such_function")
    assert _signature("ai_revoke") == {"p_user_id", "p_revoked_by", "p_ip_address", "p_user_agent"}


def test_access_state_and_request_parse_their_rows(wire: tuple[SupabaseStore, Recorder]) -> None:
    store, rec = wire
    rec.answers["ai_access_state"] = (
        200,
        json.dumps(
            [{"state": "pending", "requested_at": "2026-09-27T12:00:00+00:00", "retry_after": None}]
        ),
    )
    st = store.ai_access_state(U)
    assert (st.state, st.requested_at, st.retry_after) == (
        "pending",
        "2026-09-27T12:00:00+00:00",
        None,
    )
    assert set(rec.body("ai_access_state")) == _signature("ai_access_state")
    rec.answers["ai_request_access"] = (
        200,
        json.dumps(
            [
                {
                    "outcome": "created",
                    "requested_at": "2026-09-27T12:00:00+00:00",
                    "retry_after": None,
                }
            ]
        ),
    )
    assert store.ai_request_access(U, "why").state == "created"
    body = rec.body("ai_request_access")
    assert set(body) == _signature("ai_request_access") and body["p_note"] == "why"
    rec.answers["ai_request_access"] = (200, "[]")
    with pytest.raises(RuntimeError):
        store.ai_request_access(U, None)


def test_pending_requests_parse_the_json_object(wire: tuple[SupabaseStore, Recorder]) -> None:
    store, rec = wire
    rec.answers["ai_pending_requests"] = (
        200,
        json.dumps(
            {"total": 3, "items": [{"user_id": U, "email": None, "note": "n", "requested_at": "t"}]}
        ),
    )
    out = store.ai_pending_requests(None, 200)
    assert out["total"] == 3 and out["items"][0]["email"] is None
    assert set(rec.body("ai_pending_requests")) == _signature("ai_pending_requests")


def test_approve_and_dismiss_read_the_boolean(wire: tuple[SupabaseStore, Recorder]) -> None:
    store, rec = wire
    for name, call in (
        ("ai_approve_request", lambda: store.ai_approve_request(user_id=U, approved_by=U)),
        ("ai_dismiss_request", lambda: store.ai_dismiss_request(user_id=U, dismissed_by=U)),
    ):
        rec.answers[name] = (200, "true")
        assert call() is True
        rec.answers[name] = (200, "false")
        assert call() is False
        assert set(rec.body(name)) == _signature(name)


def test_signature_reader_takes_the_last_definition() -> None:
    # ai_grant is defined in 035 and replaced in 036 with the same parameters.
    assert _signature("ai_grant") == {
        "p_user_id",
        "p_email",
        "p_granted_by",
        "p_daily_questions",
        "p_monthly_budget_usd",
        "p_note",
        "p_ip_address",
        "p_user_agent",
    }


def test_forget_user_calls_its_rpc(wire: tuple[SupabaseStore, Recorder]) -> None:
    store, rec = wire
    rec.answers["ai_forget_user"] = (200, "null")
    store.ai_forget_user(U)
    assert set(rec.body("ai_forget_user")) == _signature("ai_forget_user")


def test_requests_since_counts_through_the_table() -> None:
    seen: list[httpx.Request] = []

    def counted(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            content=b"[]",
            headers={"content-type": "application/json", "content-range": "*/7"},
        )

    http = httpx.Client(
        base_url="http://pgrst.test/rest/v1", transport=httpx.MockTransport(counted)
    )
    store = object.__new__(SupabaseStore)
    store._client = SyncPostgrestClient("http://pgrst.test/rest/v1", http_client=http)
    assert store.ai_requests_since(datetime(2026, 10, 8, 12, 0, tzinfo=UTC)) == 7
    (req,) = seen
    assert req.url.path.endswith("/ai_access_requests")
    assert "count=exact" in req.headers.get("prefer", "")
    assert "requested_at=gte." in str(req.url.query, "ascii")
