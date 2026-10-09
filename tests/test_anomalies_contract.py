# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""The /anomalies page reads a fixture that must be what the API returns.

``GET /api/v1/projects/{id}/anomalies`` returns ``asdict(detect_anomalies(...))``
with no response model, so nothing typed links it to the page that renders
it. The page shipped on 2026-04-05 written against fields the engine never
had (``summary``, ``total_activities``, ``activity_name``) and threw on every
analysis. ``web/src/lib/anomaliesPage.test.ts`` now renders the page from
``web/src/lib/__fixtures__/anomalies.sample_update.json``; this test keeps
that file equal to what the engine produces for the same synthetic schedule,
serialized the way FastAPI serializes a ``dict`` return.

Regenerate after a deliberate engine change with::

    python -m tests.test_anomalies_contract
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder

from src.analytics.anomaly_detection import detect_anomalies
from src.parser.xer_reader import XERReader

ROOT = Path(__file__).resolve().parent.parent
SCHEDULE = ROOT / "tests" / "fixtures" / "sample_update.xer"
FIXTURE = ROOT / "web" / "src" / "lib" / "__fixtures__" / "anomalies.sample_update.json"


def _api_payload() -> Any:
    return jsonable_encoder(asdict(detect_anomalies(XERReader(str(SCHEDULE)).parse())))


def _render(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def test_the_page_fixture_is_what_the_api_returns() -> None:
    assert FIXTURE.read_text(encoding="utf-8") == _render(_api_payload()), (
        "web/src/lib/__fixtures__/anomalies.sample_update.json no longer matches "
        "the anomalies endpoint. If the engine change is deliberate, regenerate it "
        "with `python -m tests.test_anomalies_contract` and update "
        "web/src/routes/anomalies/+page.svelte to the new shape in the same commit."
    )


def test_the_fixture_exercises_the_rows_the_page_renders() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert payload["total"] == len(payload["anomalies"]) > 0
    assert payload["activities_analyzed"] > 0


if __name__ == "__main__":
    FIXTURE.write_text(_render(_api_payload()), encoding="utf-8")
