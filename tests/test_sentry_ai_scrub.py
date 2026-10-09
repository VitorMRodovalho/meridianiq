# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Error reports from the AI path carry neither the API key nor the question.

End to end through the app's own ``sentry_sdk.init`` (src/api/app.py), with
a transport that only captures, in a subprocess so the global Sentry client
of the test session is untouched. The control arm runs the same failures
without the ``before_send`` hook and must find the question, so a pass here
means the hook removed it, not that the instrument could not see it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.api.sentry_scrub import scrub_ai_event

ROOT = Path(__file__).resolve().parent.parent
KEY = "sk-ant-PROBE-0123456789abcdef"
QUESTION = "PROBE-QUESTION which activities slip the handover milestone"

_SCRIPT = r"""
import json, logging, os, sys
import sentry_sdk
from sentry_sdk.transport import Transport

events = []

class Capture(Transport):
    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.headers.get("type") == "event":
                events.append(item.payload.get_bytes().decode())

_init = sentry_sdk.init

def init(*args, **kwargs):
    kwargs["transport"] = Capture
    if os.environ.get("PROBE_NO_SCRUB") == "1":
        kwargs.pop("before_send", None)
        # The control removes both layers: the hooks and the app's
        # minimal-data options, so it must find what they keep out.
        for option in ("send_default_pii", "include_local_variables", "max_request_body_size"):
            kwargs.pop(option, None)
    return _init(*args, **kwargs)

sentry_sdk.init = init
import src.api.app  # noqa: F401  (runs the app's sentry_sdk.init)
from src.api import ai_gate
from src.api.access import Principal
from src.database.store import AIQuota
from decimal import Decimal

ai_gate.sdk_available = lambda: True
ai_gate.ledger_is_durable = lambda store: True
ai_gate.make_client = lambda config: object()
user = Principal("00000000-0000-4000-8000-0000000a1a01", "user")

class QuotaDown:
    def ai_quota(self, *a, **k):
        raise RuntimeError("PGRST202 function missing")

class ReserveDown:
    def ai_quota(self, *a, **k):
        return AIQuota(True, 20, 0, Decimal(5), Decimal(0), Decimal(0))
    def ai_reserve(self, **k):
        raise RuntimeError("ledger down")

class Schedule:
    projects, activities, relationships, wbs_nodes, calendars = [], [], [], [], []

ai_gate.status_for(user, QuotaDown())
try:
    ai_gate.answer_question(principal=user, project_id="p", question=os.environ["PROBE_Q"],
                            store=ReserveDown(), load_schedule=Schedule)
except Exception:
    pass
sentry_sdk.flush()
blob = "\n".join(events)
ai_events = [e for e in events
             if ((json.loads(e).get("logentry") or {}).get("message") or "").startswith("ai_")]
print(json.dumps({"events": len(ai_events), "key": os.environ["PROBE_KEY"] in blob,
                  "question": os.environ["PROBE_Q"] in blob}))
"""


def _run(no_scrub: bool) -> dict[str, object]:
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "SENTRY_DSN": "https://public@example.invalid/1",
        "ENVIRONMENT": "production",
        "SUPABASE_URL": "",
        "SUPABASE_SERVICE_ROLE_KEY": "",
        "SUPABASE_ANON_KEY": "",
        "ALLOW_REMOTE_SUPABASE": "",
        "AI_ENABLED": "1",
        "ANTHROPIC_API_KEY": KEY,
        "AI_MODEL": "m",
        "AI_PRICED_MODEL": "m",
        "AI_PRICE_INPUT_USD_PER_MTOK": "3",
        "AI_PRICE_OUTPUT_USD_PER_MTOK": "15",
        "AI_GLOBAL_MONTHLY_BUDGET_USD": "50",
        "PROBE_KEY": KEY,
        "PROBE_Q": QUESTION,
        "PROBE_NO_SCRUB": "1" if no_scrub else "",
    }
    out = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return dict(json.loads(out.stdout.strip().splitlines()[-1]))


def test_ai_errors_reach_sentry_without_key_or_question() -> None:
    scrubbed = _run(no_scrub=False)
    assert scrubbed["events"] == 2  # one per failure: the path does report errors
    assert scrubbed["key"] is False
    assert scrubbed["question"] is False


def test_control_without_the_hook_the_question_is_captured() -> None:
    unscrubbed = _run(no_scrub=True)
    assert unscrubbed["events"] == 2
    assert unscrubbed["question"] is True
    # The key is absent even here: AIConfig holds only whether it is set.
    assert unscrubbed["key"] is False


def _frames_event(url: str) -> dict[str, object]:
    return {
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {"module": "src.api.ai_gate", "function": "f", "vars": {"q": 1}},
                            {"module": "fastapi.routing", "function": "app", "vars": {"body": 1}},
                            {
                                "module": "src.api.routers.intelligence",
                                "function": "get_project_health",
                                "vars": {"x": 1},
                            },
                        ]
                    }
                }
            ]
        },
        "request": {"url": url, "data": {"payload": 1}},
    }


def _has_vars(event: dict[str, object]) -> list[bool]:
    frames = event["exception"]["values"][0]["stacktrace"]["frames"]  # type: ignore[index]
    return [("vars" in f) for f in frames]


def test_ai_request_events_lose_every_frame_local_and_the_body() -> None:
    for url in (
        "https://api.example/api/v1/projects/p/ask",
        "https://api.example/api/v1/ai/access-request",
        "https://api.example/api/v1/superadmin/ai/entitlements",
    ):
        out = scrub_ai_event(_frames_event(url), {})
        assert _has_vars(out) == [False, False, False], url
        assert "data" not in out["request"]  # type: ignore[operator]


def test_other_events_lose_ai_module_locals_and_keep_only_method_and_path() -> None:
    event = _frames_event("https://api.example/api/v1/projects/p/tasks?email=a@example.com")
    event["request"].update(  # type: ignore[union-attr]
        {
            "method": "GET",
            "headers": {"Fly-Client-IP": "203.0.113.9", "User-Agent": "probe"},
            "cookies": {"sb": "x"},
            "env": {"REMOTE_ADDR": "203.0.113.9"},
            "query_string": "email=a@example.com",
        }
    )

    out = scrub_ai_event(event, {})

    assert _has_vars(out) == [False, True, True]
    assert out["request"] == {  # Fly-Client-IP is not on the SDK's own sensitive list
        "method": "GET",
        "url": "https://api.example/api/v1/projects/p/tasks",
    }


# ------------------------------------------------------------------ #
# A real request through the app: error events and transactions      #
# ------------------------------------------------------------------ #

NOTE = "PROBE-NOTE-private reason for access"

_ROUTE_SCRIPT = r"""
import json, os, time
import jwt
import sentry_sdk
from sentry_sdk.transport import Transport

events = []

class Capture(Transport):
    def capture_envelope(self, envelope):
        for item in envelope.items:
            kind = item.headers.get("type")
            if kind in ("event", "transaction"):
                events.append((kind, item.payload.get_bytes().decode()))

_init = sentry_sdk.init

def init(*args, **kwargs):
    kwargs["transport"] = Capture
    kwargs["traces_sample_rate"] = 1.0
    if os.environ.get("PROBE_NO_SCRUB") == "1":
        kwargs.pop("before_send", None)
        kwargs.pop("before_send_transaction", None)
        # The control removes both layers: the hooks and the app's
        # minimal-data options, so it must find what they keep out.
        for option in ("send_default_pii", "include_local_variables", "max_request_body_size"):
            kwargs.pop(option, None)
    return _init(*args, **kwargs)

sentry_sdk.init = init
from fastapi.testclient import TestClient
from src.api.app import app
from src.api import deps
from src.database.store import InMemoryStore

store = InMemoryStore()
def broken(*a, **k):
    raise RuntimeError("function ai_request_access does not exist")
store.ai_request_access = broken
deps._store = store
now = int(time.time())
token = jwt.encode({"sub": "00000000-0000-4000-8000-0000000b1b02", "aud": "authenticated",
                    "role": "authenticated", "iat": now, "exp": now + 3600},
                   "test-secret", algorithm="HS256")
client = TestClient(app, raise_server_exceptions=False)
resp = client.post("/api/v1/ai/access-request", json={"note": os.environ["PROBE_NOTE"]},
                   headers={"Authorization": f"Bearer {token}"})
sentry_sdk.flush()
kinds = [k for k, _ in events]
print(json.dumps({"status": resp.status_code,
                  "errors": kinds.count("event"),
                  "transactions": kinds.count("transaction"),
                  "note": any(os.environ["PROBE_NOTE"] in e for _, e in events)}))
"""


def _run_route(no_scrub: bool) -> dict[str, object]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONPATH": str(ROOT),
        "SENTRY_DSN": "https://public@example.invalid/1",
        "ENVIRONMENT": "development",
        "SUPABASE_JWT_SECRET": "test-secret",
        "RATE_LIMIT_ENABLED": "false",
        "SUPABASE_URL": "",
        "SUPABASE_SERVICE_ROLE_KEY": "",
        "SUPABASE_ANON_KEY": "",
        "DATABASE_URL": "",
        "ALLOW_REMOTE_SUPABASE": "",
        "ANTHROPIC_API_KEY": "",
        "RESEND_API_KEY": "",
        "SIGNUP_ALERT_TO": "",
        "PROBE_NOTE": NOTE,
        "PROBE_NO_SCRUB": "1" if no_scrub else "",
    }
    out = subprocess.run(
        [sys.executable, "-c", _ROUTE_SCRIPT],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return dict(json.loads(out.stdout.strip().splitlines()[-1]))


def test_a_failed_access_request_reaches_sentry_without_its_note() -> None:
    result = _run_route(no_scrub=False)
    assert result["status"] == 500
    assert result["errors"] >= 1 and result["transactions"] >= 1  # both kinds are sent
    assert result["note"] is False


def test_control_without_the_hooks_the_note_is_in_the_events() -> None:
    result = _run_route(no_scrub=True)
    assert result["errors"] >= 1 and result["transactions"] >= 1
    assert result["note"] is True


def test_outgoing_call_queries_are_dropped_from_spans_trace_and_breadcrumbs() -> None:
    """PostgREST filters ride on the SDK's http.client spans and breadcrumbs.

    Measured in production on 2026-10-09: 6 http.client spans to Supabase
    carried ``http.query`` with ``=eq.`` filters; a lookup by email puts the
    address there.
    """
    query = "email=eq.person%40example.com&select=id"
    event: dict[str, object] = {
        "type": "transaction",
        "request": {"method": "GET", "url": "https://api.example/api/v1/orgs/x/invites"},
        "contexts": {"trace": {"data": {"http.query": "a=1", "url": "https://api.example/p?a=1"}}},
        "spans": [
            {
                "op": "http.client",
                "data": {"url": "https://ref.supabase.co/rest/v1/users", "http.query": query},
            },
            {"op": "db", "data": {"db.system": "postgresql"}},
        ],
        "breadcrumbs": {
            "values": [
                {
                    "type": "http",
                    "data": {
                        "url": f"https://ref.supabase.co/rest/v1/users?{query}",
                        "http.query": query,
                    },
                }
            ]
        },
    }

    out = json.dumps(scrub_ai_event(event, {}))

    assert "person" not in out and "eq." not in out and "a=1" not in out
    assert "https://ref.supabase.co/rest/v1/users" in out  # the path stays
    assert '"db.system": "postgresql"' in out
