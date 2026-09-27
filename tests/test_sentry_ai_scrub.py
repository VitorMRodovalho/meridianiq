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


def test_hook_keeps_other_frames_and_other_bodies() -> None:
    event = {
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {"module": "src.api.ai_gate", "function": "f", "vars": {"q": 1}},
                            {
                                "module": "src.api.routers.intelligence",
                                "function": "ask_schedule",
                                "vars": {"body": 1},
                            },
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
        "request": {"url": "https://api.example/api/v1/projects/p/ask", "data": {"question": 1}},
    }
    out = scrub_ai_event(event, {})
    frames = out["exception"]["values"][0]["stacktrace"]["frames"]
    assert [("vars" in f) for f in frames] == [False, False, True]
    assert "data" not in out["request"]
    other = {"request": {"url": "https://api.example/api/v1/projects/p/tasks", "data": {"a": 1}}}
    assert scrub_ai_event(other, {})["request"]["data"] == {"a": 1}
