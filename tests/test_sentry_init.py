# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""The app initialises Sentry with the minimal-data options PRIVACY.md describes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_SCRIPT = r"""
import json
import sentry_sdk

seen = {}

def init(*args, **kwargs):
    seen.update(kwargs)

sentry_sdk.init = init
import src.api.app  # noqa: F401  (runs the app's sentry_sdk.init)
print(json.dumps({k: seen.get(k) for k in (
    "send_default_pii", "include_local_variables", "max_request_body_size", "traces_sample_rate"
)} | {"hooks": [k for k in ("before_send", "before_send_transaction") if k in seen]}))
"""


def test_sentry_is_initialised_with_minimal_data() -> None:
    env = {
        **os.environ,
        "SENTRY_DSN": "https://public@o0.ingest.de.sentry.io/0",
        "SUPABASE_URL": "",
        "SUPABASE_ANON_KEY": "",
        "SUPABASE_SERVICE_ROLE_KEY": "",
        "ALLOW_REMOTE_SUPABASE": "",
    }
    out = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )

    assert json.loads(out.stdout.strip().splitlines()[-1]) == {
        "send_default_pii": False,
        "include_local_variables": False,
        "max_request_body_size": "never",
        "traces_sample_rate": 0.1,
        "hooks": ["before_send", "before_send_transaction"],
    }
