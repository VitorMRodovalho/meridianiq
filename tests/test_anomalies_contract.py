# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""The /anomalies page reads a fixture that must be what the API returns.

``GET /api/v1/projects/{id}/anomalies`` returns ``asdict(detect_anomalies(...))``
with no model of its own, so nothing typed links it to the page that renders
it. The page shipped on 2026-04-05 written against fields the engine never
had (``summary``, ``total_activities``, ``activity_name``) and threw on every
analysis. ``web/src/lib/anomaliesPage.test.ts`` now renders the page from
``web/src/lib/__fixtures__/anomalies.sample_update.json``; this test keeps
that file equal to what the route returns for the same synthetic schedule.

The fixture is taken from the route itself, through ``TestClient``. A
``-> dict`` route is serialized by pydantic (datetimes end in ``Z``, NaN
becomes ``null``), not by ``jsonable_encoder``, so re-serializing the
engine's output by hand would describe a different payload.

Regenerate after a deliberate change with::

    python -m tests.test_anomalies_contract
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from src.api.app import app, get_store

ROOT = Path(__file__).resolve().parent.parent
SCHEDULE = ROOT / "tests" / "fixtures" / "sample_update.xer"
FIXTURE = ROOT / "web" / "src" / "lib" / "__fixtures__" / "anomalies.sample_update.json"


def _route_payload() -> Any:
    get_store().clear()
    client = TestClient(app)
    with SCHEDULE.open("rb") as f:
        upload = client.post("/api/v1/upload", files={"file": (SCHEDULE.name, f)})
    assert upload.status_code in (200, 201, 202), upload.text
    project_id = upload.json()["project_id"]

    resp = client.get(f"/api/v1/projects/{project_id}/anomalies")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _render(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def test_the_page_fixture_is_what_the_route_returns() -> None:
    assert FIXTURE.read_text(encoding="utf-8") == _render(_route_payload()), (
        "web/src/lib/__fixtures__/anomalies.sample_update.json no longer matches "
        "GET /api/v1/projects/{id}/anomalies. If the change is deliberate, "
        "regenerate it with `python -m tests.test_anomalies_contract` and update "
        "web/src/routes/anomalies/+page.svelte to the new shape in the same commit."
    )


def test_the_fixture_exercises_the_rows_the_page_renders() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert payload["total"] == len(payload["anomalies"]) > 0
    assert payload["activities_analyzed"] > 0


if __name__ == "__main__":
    FIXTURE.write_text(_render(_route_payload()), encoding="utf-8")
