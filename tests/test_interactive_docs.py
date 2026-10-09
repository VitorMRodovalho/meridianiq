# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Production serves /openapi.json but not Swagger UI or ReDoc (ADR-0031).

Both UIs load scripts from a CDN, at a floating major version, onto the API's
origin. The document itself stays public: the repository already carries it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_PROBE = """
import json
from fastapi.testclient import TestClient
from src.api.app import app
c = TestClient(app)
print(json.dumps({p: c.get(p).status_code for p in ("/openapi.json", "/docs", "/redoc")}))
"""


def _status_codes(environment: str) -> dict[str, int]:
    env = {
        **os.environ,
        "ENVIRONMENT": environment,
        "SUPABASE_URL": "",
        "SUPABASE_ANON_KEY": "",
        "SUPABASE_SERVICE_ROLE_KEY": "",
        "ALLOW_REMOTE_SUPABASE": "",
    }
    out = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    result: dict[str, int] = json.loads(out.stdout.strip().splitlines()[-1])
    return result


def test_production_serves_the_document_and_no_interactive_ui() -> None:
    assert _status_codes("production") == {"/openapi.json": 200, "/docs": 404, "/redoc": 404}


def test_development_keeps_the_interactive_ui() -> None:
    assert _status_codes("development") == {"/openapi.json": 200, "/docs": 200, "/redoc": 200}
