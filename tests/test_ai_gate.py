# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""The AI access gate (src/api/ai_gate.py, migration 035).

Owner rule: the AI feature is not available to free or non-approved
accounts, and when it is, it is limited and controlled. These tests run
with ``ENVIRONMENT=production`` and real HS256 tokens, so the whole
auth -> principal -> access -> gate path is exercised. The provider client
is always a fake (tests/ai_fakes.py); conftest makes the real one raise.

The ledger rules have two implementations: InMemoryStore (here) and the
SQL functions of migration 035 (scripts/rls_replica/035/scenarios.sql runs
the same scenarios against Postgres).
"""

from __future__ import annotations

import ast
import copy
import functools
import threading
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

import src.api.deps as deps
from src.analytics import nlp_query
from src.api import ai_gate
from src.api.access import Principal
from src.api.app import app
from src.database import config
from src.database.store import InMemoryStore, SupabaseStore
from src.parser.models import ParsedSchedule
from src.parser.xer_reader import XERReader
from tests import ai_fakes

FIXTURES = Path(__file__).parent / "fixtures"
SRC = Path(__file__).resolve().parent.parent / "src"
TEST_JWT_SECRET = "test-secret"  # tests/conftest.py sets SUPABASE_JWT_SECRET to this

USER_A = "00000000-0000-4000-8000-0000000a1a01"  # entitled
USER_B = "00000000-0000-4000-8000-0000000b1b02"  # not entitled
ADMIN = "00000000-0000-4000-8000-00000000ad01"

QUESTION = "Which path drives completion?"
# Cost of one call answered with the fake's default usage (1200 in, 300 out)
# at the test prices (3 and 15 USD per million tokens).
FAKE_CALL_COST = Decimal("0.0081")


def _token(sub: str, email: str | None = None) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {"sub": sub, "aud": "authenticated", "role": "authenticated"}
    claims.update(iat=now, exp=now + 3600)
    if email:
        claims["email"] = email
    return jwt.encode(claims, TEST_JWT_SECRET, algorithm="HS256")


def _auth(sub: str, email: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(sub, email)}"}


@functools.cache
def _parsed() -> ParsedSchedule:
    return XERReader(FIXTURES / "sample.xer").parse()


class Gate:
    """A production-mode app with an in-memory store and a fake provider."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
        self.store = InMemoryStore()
        monkeypatch.setattr(deps, "_store", self.store)
        assert deps.get_store() is self.store
        self.fake = ai_fakes.enable_ai(monkeypatch)
        monkeypatch.setenv("SUPERADMIN_USER_IDS", ADMIN)
        self.monkeypatch = monkeypatch
        self.client = TestClient(app)
        self.pa = str(self.store.add(copy.deepcopy(_parsed()), b"x", user_id=USER_A))
        self.pb = str(self.store.add(copy.deepcopy(_parsed()), b"x", user_id=USER_B))
        self.store.register_account(USER_A, "a@example.test")
        self.store.register_account(USER_B, "b@example.test")
        self.grant(USER_A)
        self.reads: list[str] = []
        original = self.store.get

        def spy(project_id: str, *args: Any, **kwargs: Any) -> Any:
            self.reads.append(project_id)
            return original(project_id, *args, **kwargs)

        monkeypatch.setattr(self.store, "get", spy)

    def grant(self, user: str, daily: int | None = None, budget: Decimal | None = None) -> None:
        self.store.ai_grant(
            user_id=user,
            email=f"{user}@example.test",
            granted_by=ADMIN,
            daily_questions=daily,
            monthly_budget_usd=budget,
            note=None,
        )

    def ask(self, user: str = USER_A, project: str | None = None, **body: Any) -> Any:
        payload = {"question": QUESTION, **body}
        return self.client.post(
            f"/api/v1/projects/{project or self.pa}/ask", json=payload, headers=_auth(user)
        )

    def status(self, user: str = USER_A) -> dict[str, Any]:
        resp = self.client.get("/api/v1/ai/status", headers=_auth(user))
        assert resp.status_code == 200, resp.text
        return dict(resp.json())

    def rows(self) -> list[dict[str, Any]]:
        return list(self.store._ai_usage)

    def reserve_of_one_question(self) -> Decimal:
        system, message = nlp_query.build_prompt(_parsed(), QUESTION)
        size = len(system.encode()) + len(message.encode())
        return ai_gate.worst_case_cost(size, ai_gate.load_config(self.store))


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Gate:
    return Gate(monkeypatch)


def _code(resp: Any) -> str:
    return str(resp.json()["detail"]["error_code"])


# ------------------------------------------------------------------ #
# Positive control                                                   #
# ------------------------------------------------------------------ #


def test_entitled_owner_gets_one_call_settled_with_its_real_cost(gate: Gate) -> None:
    resp = gate.ask()
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["answer"] == "stub answer"
    assert body["model"] == ai_fakes.MODEL
    assert body["tokens_used"] == 1500
    assert body["remaining_today"] == ai_gate.DEFAULT_DAILY_QUESTIONS - 1
    assert len(gate.fake.calls) == 1
    call = gate.fake.calls[0]
    assert call["model"] == ai_fakes.MODEL
    assert call["max_tokens"] == ai_gate.MAX_OUTPUT_TOKENS
    assert call["messages"][0]["content"].endswith(f"Question: {QUESTION}")
    (row,) = gate.rows()
    assert row["status"] == "completed"
    assert row["cost_usd"] == FAKE_CALL_COST
    assert row["input_tokens"] == 1200 and row["output_tokens"] == 300
    assert row["reserved_usd"] == gate.reserve_of_one_question()
    assert row["cost_usd"] < row["reserved_usd"]
    assert row["model"] == ai_fakes.MODEL
    assert row["price_input_usd_per_mtok"] == Decimal("3")


def test_status_of_an_entitled_account(gate: Gate) -> None:
    gate.ask()
    status = gate.status()
    assert status["available"] is True and status["reason"] is None
    assert status["daily_limit"] == ai_gate.DEFAULT_DAILY_QUESTIONS
    assert status["used_today"] == 1
    assert status["remaining_today"] == ai_gate.DEFAULT_DAILY_QUESTIONS - 1
    resets = datetime.fromisoformat(status["resets_at"])
    now = datetime.now(UTC)
    assert resets.tzinfo is not None and now < resets <= now + timedelta(days=1)
    assert (resets.hour, resets.minute, resets.second) == (0, 0, 0)


# ------------------------------------------------------------------ #
# Layer 1: configuration fails closed                                #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize("key", sorted(ai_fakes.AI_ENV))
def test_each_missing_setting_disables_ai(
    gate: Gate, monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    monkeypatch.setenv(key, "")
    assert gate.status()["reason"] == "ai_disabled"
    resp = gate.ask()
    assert (resp.status_code, _code(resp)) == (403, "ai_disabled")
    assert gate.fake.calls == [] and gate.rows() == [] and gate.reads == []


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("AI_ENABLED", "true"),
        ("AI_ENABLED", "yes"),
        ("AI_PRICE_INPUT_USD_PER_MTOK", "0"),
        ("AI_PRICE_OUTPUT_USD_PER_MTOK", "-1"),
        ("AI_PRICE_INPUT_USD_PER_MTOK", "abc"),
        ("AI_GLOBAL_MONTHLY_BUDGET_USD", "NaN"),
        ("AI_GLOBAL_MONTHLY_BUDGET_USD", "Infinity"),
    ],
)
def test_invalid_settings_disable_ai(
    gate: Gate, monkeypatch: pytest.MonkeyPatch, key: str, value: str
) -> None:
    monkeypatch.setenv(key, value)
    resp = gate.ask()
    assert (resp.status_code, _code(resp)) == (403, "ai_disabled")
    assert gate.fake.calls == []


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("AI_PRICED_MODEL", "another-model"),  # the model changed, the prices did not
        ("AI_PRICE_INPUT_USD_PER_MTOK", "0.003"),  # typed per thousand tokens
        ("AI_PRICE_OUTPUT_USD_PER_MTOK", "0.000015"),  # typed per token
        ("AI_PRICE_OUTPUT_USD_PER_MTOK", "15000"),  # a thousand times too high
        ("AI_PRICE_OUTPUT_USD_PER_MTOK", "1"),  # output cheaper than input
    ],
)
def test_prices_must_match_the_model_and_be_plausible(
    gate: Gate, monkeypatch: pytest.MonkeyPatch, key: str, value: str
) -> None:
    monkeypatch.setenv(key, value)
    config = ai_gate.load_config(gate.store)
    assert config.flags()["prices_set"] is False
    resp = gate.ask()
    assert (resp.status_code, _code(resp)) == (403, "ai_disabled")
    assert gate.fake.calls == []


def test_config_never_holds_the_key(gate: Gate) -> None:
    config = ai_gate.load_config(gate.store)
    assert config.api_key_set is True
    assert ai_fakes.AI_ENV["ANTHROPIC_API_KEY"] not in repr(config)
    assert ai_fakes.AI_ENV["ANTHROPIC_API_KEY"] not in str(vars(config))


def test_missing_sdk_disables_ai(gate: Gate, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_gate, "sdk_available", lambda: False)
    assert (gate.ask().status_code, gate.status()["reason"]) == (403, "ai_disabled")
    assert gate.fake.calls == []


def test_non_durable_ledger_disables_ai(gate: Gate, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_gate, "ledger_is_durable", lambda store: False)
    assert (gate.ask().status_code, gate.status()["reason"]) == (403, "ai_disabled")
    assert gate.fake.calls == []


def test_ledger_durability_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    supabase_like = object.__new__(SupabaseStore)
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    assert ai_gate.ledger_is_durable(InMemoryStore()) is False
    assert ai_gate.ledger_is_durable(supabase_like) is True
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "development")
    assert ai_gate.ledger_is_durable(InMemoryStore()) is True


def test_invalid_default_limit_denies(gate: Gate, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_DEFAULT_DAILY_QUESTIONS", "twenty")
    resp = gate.ask()
    assert (resp.status_code, _code(resp)) == (429, "ai_daily_quota")
    assert gate.fake.calls == []


def test_the_real_client_is_built_with_no_retries_and_a_bounded_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import anthropic

    seen: dict[str, Any] = {}

    def record(**kwargs: Any) -> str:
        seen.update(kwargs)
        return "client"

    monkeypatch.setattr(anthropic, "Anthropic", record)
    for key, value in ai_fakes.AI_ENV.items():
        monkeypatch.setenv(key, value)
    assert ai_gate.make_client(ai_gate.load_config(InMemoryStore())) == "client"
    assert seen["api_key"] == ai_fakes.AI_ENV["ANTHROPIC_API_KEY"]
    assert seen["max_retries"] == 0
    assert seen["timeout"].read == ai_gate.REQUEST_TIMEOUT_S
    assert seen["timeout"].connect == ai_gate.CONNECT_TIMEOUT_S


# ------------------------------------------------------------------ #
# Layer 2: entitlement                                               #
# ------------------------------------------------------------------ #


def test_owner_without_entitlement_is_refused_before_the_schedule_loads(gate: Gate) -> None:
    resp = gate.ask(USER_B, gate.pb)
    assert (resp.status_code, _code(resp)) == (403, "ai_not_entitled")
    assert gate.fake.calls == [] and gate.rows() == [] and gate.reads == []
    status = gate.status(USER_B)
    assert status == {
        "available": False,
        "reason": "ai_not_entitled",
        "daily_limit": None,
        "used_today": None,
        "remaining_today": None,
        "resets_at": None,
    }


def test_reserve_checks_the_entitlement_itself(gate: Gate) -> None:
    """Revocation between the status check and the reservation still refuses."""

    def reserve(user: str) -> tuple[int | None, str | None]:
        return gate.store.ai_reserve(
            user_id=user,
            project_id=None,
            reserve_usd=Decimal("0.01"),
            default_daily=20,
            default_account_usd=Decimal("5"),
            global_budget_usd=Decimal("50"),
            model="m",
            price_input=Decimal("3"),
            price_output=Decimal("15"),
        )

    assert reserve(USER_B) == (None, "ai_not_entitled")
    assert reserve(USER_A)[0] is not None
    gate.store.ai_revoke(user_id=USER_A, revoked_by=ADMIN)
    assert reserve(USER_A) == (None, "ai_not_entitled")


def test_revoked_entitlement_is_refused(gate: Gate) -> None:
    assert gate.ask().status_code == 200
    assert gate.store.ai_revoke(user_id=USER_A, revoked_by=ADMIN) is True
    resp = gate.ask()
    assert (resp.status_code, _code(resp)) == (403, "ai_not_entitled")
    assert len(gate.fake.calls) == 1


def test_entitlement_does_not_open_another_tenants_project(gate: Gate) -> None:
    resp = gate.ask(USER_A, gate.pb)
    assert resp.status_code == 404
    assert gate.fake.calls == [] and gate.rows() == []


def test_api_key_and_development_principals_need_a_session(gate: Gate) -> None:
    for kind in ("api_key", "dev"):
        status = ai_gate.status_for(Principal(USER_A, kind), gate.store)  # type: ignore[arg-type]
        assert status.reason == "ai_session_required"
    assert ai_gate.status_for(Principal(USER_A, "user"), gate.store).available is True


def test_signed_out_status_is_401(gate: Gate) -> None:
    assert gate.client.get("/api/v1/ai/status").status_code == 401


def test_a_key_in_the_body_is_ignored_and_never_echoed(gate: Gate) -> None:
    resp = gate.ask(api_key="sk-client-supplied-key")
    assert resp.status_code == 200
    assert "sk-client-supplied-key" not in resp.text
    assert len(gate.fake.calls) == 1


# ------------------------------------------------------------------ #
# Layer 3: limits                                                    #
# ------------------------------------------------------------------ #


def test_daily_question_limit(gate: Gate) -> None:
    gate.grant(USER_A, daily=2)
    assert [gate.ask().status_code for _ in range(2)] == [200, 200]
    resp = gate.ask()
    assert (resp.status_code, _code(resp)) == (429, "ai_daily_quota")
    assert 0 < int(resp.headers["Retry-After"]) <= 86_401
    assert len(gate.fake.calls) == 2
    assert gate.status()["reason"] == "ai_daily_quota"


def test_account_monthly_budget_counts_the_reservation(gate: Gate) -> None:
    reserve = gate.reserve_of_one_question()
    gate.grant(USER_A, budget=reserve)
    assert gate.ask().status_code == 200
    # Spent FAKE_CALL_COST; another worst case no longer fits.
    resp = gate.ask()
    assert (resp.status_code, _code(resp)) == (429, "ai_account_budget")
    assert "Retry-After" in resp.headers
    assert len(gate.fake.calls) == 1


def test_global_monthly_budget_stops_every_account(
    gate: Gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate.grant(USER_B)
    monkeypatch.setenv("AI_GLOBAL_MONTHLY_BUDGET_USD", str(gate.reserve_of_one_question()))
    assert gate.ask().status_code == 200
    resp = gate.ask(USER_B, gate.pb)
    assert (resp.status_code, _code(resp)) == (429, "ai_global_budget")
    assert len(gate.fake.calls) == 1


def test_zero_limit_override_denies(gate: Gate) -> None:
    gate.grant(USER_A, daily=0)
    resp = gate.ask()
    assert (resp.status_code, _code(resp)) == (429, "ai_daily_quota")
    assert gate.fake.calls == []


def test_prompt_over_the_cap_is_refused_before_reserving(
    gate: Gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai_gate, "MAX_PROMPT_BYTES", 100)
    resp = gate.ask()
    assert (resp.status_code, _code(resp)) == (400, "ai_prompt_too_large")
    assert gate.fake.calls == [] and gate.rows() == []


def test_reservations_do_not_overrun_a_limit_under_concurrency() -> None:
    store = InMemoryStore()
    store.ai_grant(
        user_id=USER_A,
        email="a@example.test",
        granted_by=ADMIN,
        daily_questions=5,
        monthly_budget_usd=None,
        note=None,
    )
    results: list[tuple[int | None, str | None]] = []
    lock = threading.Lock()
    start = threading.Barrier(20)

    def reserve() -> None:
        start.wait()
        r = store.ai_reserve(
            user_id=USER_A,
            project_id=None,
            reserve_usd=Decimal("0.01"),
            default_daily=20,
            default_account_usd=Decimal("5"),
            global_budget_usd=Decimal("50"),
            model="m",
            price_input=Decimal("3"),
            price_output=Decimal("15"),
        )
        with lock:
            results.append(r)

    threads = [threading.Thread(target=reserve) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    granted = [r for r in results if r[0] is not None]
    assert len(granted) == 5
    assert {r[1] for r in results if r[0] is None} == {"ai_daily_quota"}


# ------------------------------------------------------------------ #
# Layer 4: one call, always settled                                  #
# ------------------------------------------------------------------ #


def test_provider_refusal_settles_failed_and_costs_nothing(
    gate: Gate, caplog: pytest.LogCaptureFixture
) -> None:
    gate.fake.raise_exc = ai_fakes.FakeProviderError(400)
    with caplog.at_level("ERROR", logger="src.api.ai_gate"):
        resp = gate.ask()
    # An ERROR record reaches the error tracker; it carries no stack (the
    # frames hold the prompt) and never the question.
    (record,) = [r for r in caplog.records if r.levelname == "ERROR"]
    assert "outcome=failed" in record.getMessage() and record.exc_info is None
    assert QUESTION not in record.getMessage()
    assert (resp.status_code, _code(resp)) == (502, "ai_upstream_failed")
    (row,) = gate.rows()
    assert row["status"] == "failed" and row["cost_usd"] is None
    assert gate.status()["used_today"] == 0
    assert gate.store.ai_quota(USER_A, 20, Decimal("5")).account_spent_usd == 0


@pytest.mark.parametrize(
    "exc", [ai_fakes.FakeProviderError(529), TimeoutError("read timed out"), OSError("reset")]
)
def test_uncertain_failure_keeps_the_reservation_counting(gate: Gate, exc: BaseException) -> None:
    gate.fake.raise_exc = exc
    resp = gate.ask()
    assert (resp.status_code, _code(resp)) == (502, "ai_upstream_failed")
    assert "read timed out" not in resp.text
    (row,) = gate.rows()
    assert row["status"] == "unknown"
    assert gate.status()["used_today"] == 1
    quota = gate.store.ai_quota(USER_A, 20, Decimal("5"))
    assert quota.account_spent_usd == row["reserved_usd"]


def test_real_sdk_errors_are_classified() -> None:
    """The classification read against the SDK's own exception classes."""
    import anthropic
    import httpx

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")

    def status_error(code: int) -> anthropic.APIStatusError:
        cls = {400: anthropic.BadRequestError, 401: anthropic.AuthenticationError}.get(
            code, anthropic.APIStatusError
        )
        response = httpx.Response(code, request=request, json={"error": {"message": "x"}})
        return cls(message="x", response=response, body=None)

    assert ai_gate._outcome_of(status_error(400)) == "failed"
    assert ai_gate._outcome_of(status_error(401)) == "failed"
    assert ai_gate._outcome_of(status_error(429)) == "failed"
    assert ai_gate._outcome_of(status_error(529)) == "unknown"
    assert ai_gate._outcome_of(status_error(500)) == "unknown"
    assert ai_gate._outcome_of(anthropic.APITimeoutError(request=request)) == "unknown"
    assert ai_gate._outcome_of(anthropic.APIConnectionError(request=request)) == "unknown"


def test_whitespace_only_question_is_a_validation_error(gate: Gate) -> None:
    resp = gate.client.post(
        f"/api/v1/projects/{gate.pa}/ask", json={"question": "   "}, headers=_auth(USER_A)
    )
    assert resp.status_code == 422
    assert gate.fake.calls == []


def test_answer_without_usage_keeps_the_reservation_counting(gate: Gate) -> None:
    gate.fake.usage = None
    resp = gate.ask()
    assert resp.status_code == 200
    (row,) = gate.rows()
    assert row["status"] == "unknown"


def test_settle_failure_still_returns_the_billed_answer(
    gate: Gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: Any, **kwargs: Any) -> bool:
        raise RuntimeError("ledger down")

    monkeypatch.setattr(gate.store, "ai_settle", broken)
    resp = gate.ask()
    assert resp.status_code == 200
    (row,) = gate.rows()
    assert row["status"] == "reserved"  # counts at its worst case


def test_reserve_failure_never_calls_the_model(gate: Gate, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(**kwargs: Any) -> Any:
        raise RuntimeError("ledger down")

    monkeypatch.setattr(gate.store, "ai_reserve", broken)
    resp = gate.ask()
    assert (resp.status_code, _code(resp)) == (500, "ai_ledger_unavailable")
    assert gate.fake.calls == []


def test_quota_read_failure_reports_disabled(gate: Gate, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("function missing")

    monkeypatch.setattr(gate.store, "ai_quota", broken)
    assert gate.status()["reason"] == "ai_disabled"
    assert gate.ask().status_code == 403
    assert gate.fake.calls == []


def test_settle_happens_once(gate: Gate) -> None:
    gate.ask()
    (row,) = gate.rows()
    assert gate.store.ai_settle(row["id"], "unknown", None, None, None) is False
    assert gate.rows()[0]["status"] == "completed"


# ------------------------------------------------------------------ #
# Ledger windows (UTC day and month)                                 #
# ------------------------------------------------------------------ #


def test_windows_are_utc_day_and_month(gate: Gate) -> None:
    gate.ask()
    gate.ask()
    rows = gate.store._ai_usage
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = day_start.replace(day=1)
    rows[0]["created_at"] = month_start - timedelta(seconds=1)  # last month
    rows[1]["created_at"] = day_start - timedelta(seconds=1)  # yesterday or last month
    quota = gate.store.ai_quota(USER_A, 20, Decimal("5"))
    assert quota.used_today == 0
    expected_month = FAKE_CALL_COST if rows[1]["created_at"] >= month_start else Decimal(0)
    assert quota.account_spent_usd == expected_month


def test_stale_reservations_are_reported(gate: Gate) -> None:
    gate.store.ai_reserve(
        user_id=USER_A,
        project_id=None,
        reserve_usd=Decimal("0.01"),
        default_daily=20,
        default_account_usd=Decimal("5"),
        global_budget_usd=Decimal("50"),
        model="m",
        price_input=Decimal("3"),
        price_output=Decimal("15"),
    )
    gate.store._ai_usage[0]["created_at"] = datetime.now(UTC) - timedelta(minutes=11)
    report = gate.store.ai_admin_report(20, Decimal("5"))
    assert report["stale_reservations"] == 1


# ------------------------------------------------------------------ #
# Operator routes                                                    #
# ------------------------------------------------------------------ #


def test_operator_routes_require_a_listed_session(
    gate: Gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "/api/v1/superadmin/ai"
    assert gate.client.get(url).status_code == 401
    refused = gate.client.get(url, headers=_auth(USER_A))
    assert (refused.status_code, _code(refused)) == (403, "superadmin_required")
    # An email claim is not enough: only SUPERADMIN_USER_IDS counts here.
    monkeypatch.setenv("SUPERADMIN_EMAILS", "a@example.test")
    assert gate.client.get(url, headers=_auth(USER_A, "a@example.test")).status_code == 403
    assert gate.client.get(url, headers=_auth(ADMIN)).status_code == 200


def test_operator_overview_reports_flags_never_secrets(gate: Gate) -> None:
    gate.ask()
    resp = gate.client.get("/api/v1/superadmin/ai", headers=_auth(ADMIN))
    assert resp.status_code == 200
    body = resp.json()
    assert ai_fakes.AI_ENV["ANTHROPIC_API_KEY"] not in resp.text
    assert body["available"] is True
    assert all(body["config"].values())
    assert body["model"] == ai_fakes.MODEL
    assert body["global_budget_usd"] == "50"
    assert Decimal(body["global_spent_month_usd"]) == FAKE_CALL_COST
    assert body["defaults"] == {"daily_questions": 20, "account_monthly_budget_usd": "5"}
    assert body["month_calls"] == {"reserved": 0, "completed": 1, "failed": 0, "unknown": 0}
    assert body["last_failure_at"] is None
    assert Decimal(body["reserve_per_question_usd"]) == ai_gate.worst_case_cost(
        ai_gate.TYPICAL_PROMPT_BYTES, ai_gate.load_config(gate.store)
    )
    (ent,) = body["entitlements"]
    assert ent["user_id"] == USER_A and ent["active"] is True and ent["used_today"] == 1
    assert Decimal(ent["spent_month_usd"]) == FAKE_CALL_COST


def test_operator_overview_survives_a_broken_ledger(
    gate: Gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("function ai_admin_report does not exist")

    monkeypatch.setattr(gate.store, "ai_admin_report", broken)
    resp = gate.client.get("/api/v1/superadmin/ai", headers=_auth(ADMIN))
    assert resp.status_code == 200
    body = resp.json()
    assert (body["available"], body["reason"]) == (False, "ai_ledger_unavailable")
    assert all(body["config"].values())
    assert body["entitlements"] == []


def test_failures_show_in_the_operator_overview(gate: Gate) -> None:
    gate.fake.raise_exc = ai_fakes.FakeProviderError(404)  # e.g. a retired model
    gate.ask()
    body = gate.client.get("/api/v1/superadmin/ai", headers=_auth(ADMIN)).json()
    assert body["month_calls"]["failed"] == 1
    assert body["last_failure_at"] is not None


def test_grant_and_revoke_round_trip_with_audit(gate: Gate) -> None:
    headers = _auth(ADMIN)
    resp = gate.client.post(
        "/api/v1/superadmin/ai/entitlements",
        json={"email": " B@Example.test ", "daily_questions": 3, "monthly_budget_usd": "1.5"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    ent = resp.json()
    assert ent["user_id"] == USER_B and ent["email"] == "b@example.test"
    assert ent["daily_questions"] == 3 and ent["monthly_budget_usd"] == "1.5"
    assert gate.ask(USER_B, gate.pb).status_code == 200

    url = f"/api/v1/superadmin/ai/entitlements/{USER_B}"
    assert gate.client.delete(url, headers=headers).json() == {"revoked": True}
    again = gate.client.delete(url, headers=headers)
    assert (again.status_code, _code(again)) == (404, "ai_entitlement_not_found")
    assert gate.ask(USER_B, gate.pb).status_code == 403

    actions = [(r["action"], r["entity_id"], r["user_id"]) for r in gate.store._audit_log]
    assert ("ai_access_granted", USER_B, ADMIN) in actions
    assert ("ai_access_revoked", USER_B, ADMIN) in actions
    assert all("email" not in str(r["details"]) for r in gate.store._audit_log)


@pytest.mark.parametrize(
    ("body", "daily", "budget"),
    [
        # The two shapes web/src/routes/admin/ai sends: a number, and explicit nulls.
        ({"daily_questions": 5, "monthly_budget_usd": 2.5, "note": None}, 5, "2.5"),
        ({"daily_questions": None, "monthly_budget_usd": None, "note": None}, None, None),
    ],
)
def test_grant_accepts_the_admin_page_shapes(
    gate: Gate, body: dict[str, Any], daily: int | None, budget: str | None
) -> None:
    resp = gate.client.post(
        "/api/v1/superadmin/ai/entitlements",
        json={"email": "b@example.test", **body},
        headers=_auth(ADMIN),
    )
    assert resp.status_code == 200, resp.text
    ent = resp.json()
    assert (ent["daily_questions"], ent["monthly_budget_usd"]) == (daily, budget)


def test_grant_errors(gate: Gate) -> None:
    headers = _auth(ADMIN)
    url = "/api/v1/superadmin/ai/entitlements"
    unknown = gate.client.post(url, json={"email": "nobody@example.test"}, headers=headers)
    assert (unknown.status_code, _code(unknown)) == (404, "ai_account_not_found")
    assert (
        gate.client.post(url, json={"email": "not-an-address"}, headers=headers).status_code == 422
    )
    negative = {"email": "b@example.test", "daily_questions": -1}
    assert gate.client.post(url, json=negative, headers=headers).status_code == 422
    malformed = gate.client.delete(f"{url}/not-a-uuid", headers=headers)
    assert (malformed.status_code, _code(malformed)) == (404, "ai_entitlement_not_found")


# ------------------------------------------------------------------ #
# Structure: the gate is the only way to the provider                #
# ------------------------------------------------------------------ #

_ALLOWED_IMPORTERS = {"api/ai_gate.py"}


def _provider_imports(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            a.name.split(".")[0] == "anthropic" for a in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "anthropic":
            return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and str(node.args[0].value).split(".")[0] == "anthropic"
        ):
            return True
    return False


def _calls_make_client(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "make_client")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "make_client")
        )
        for node in ast.walk(tree)
    )


def _modules() -> dict[str, ast.AST]:
    return {
        p.relative_to(SRC).as_posix(): ast.parse(p.read_text(encoding="utf-8"))
        for p in SRC.rglob("*.py")
    }


def test_only_the_gate_imports_the_provider_sdk() -> None:
    offenders = [name for name, tree in _modules().items() if _provider_imports(tree)]
    assert sorted(offenders) == sorted(_ALLOWED_IMPORTERS)


def test_only_the_gate_builds_a_client() -> None:
    offenders = [name for name, tree in _modules().items() if _calls_make_client(tree)]
    assert offenders == ["api/ai_gate.py"]


def test_structure_detectors_negative_control() -> None:
    assert _provider_imports(ast.parse("import anthropic"))
    assert _provider_imports(ast.parse("from anthropic import Anthropic"))
    assert _provider_imports(ast.parse("import anthropic.types as t"))
    assert _provider_imports(ast.parse("m = __import__('anthropic')"))
    assert not _provider_imports(ast.parse("import anthropics_notes"))
    assert _calls_make_client(ast.parse("ai_gate.make_client(cfg)"))
    assert _calls_make_client(ast.parse("make_client(cfg)"))
    assert not _calls_make_client(ast.parse("make_clients(cfg)"))
