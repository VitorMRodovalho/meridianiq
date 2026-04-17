# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Smoke tests for the submission-deliverables user guide page.

These assertions guard against silent deletion or broken anchors on
the walkthrough that ties together the four submission artefacts
(SCL Protocol / AACE §5.3 / AIA G703 / AIA G702).
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_GUIDE = _ROOT / "docs" / "user-guide" / "submission-deliverables.md"
_INDEX = _ROOT / "docs" / "user-guide" / "README.md"


def _read(path: Path) -> str:
    assert path.exists(), f"missing doc: {path}"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "anchor",
    [
        "SCL Protocol Delay Analysis PDF",
        "AACE RP 29R-03 §5.3 Forensic Report PDF",
        "AIA G703 Continuation Sheet",
        "AIA G702 Application and Certificate for Payment",
    ],
)
def test_guide_covers_each_deliverable(anchor: str) -> None:
    text = _read(_GUIDE)
    assert anchor in text, f"guide missing section for {anchor!r}"


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v1/reports/generate",
        "/api/v1/projects/$PROJECT_ID/export/aia-g703",
    ],
)
def test_guide_references_endpoint(endpoint: str) -> None:
    text = _read(_GUIDE)
    assert endpoint in text, f"guide missing endpoint example {endpoint!r}"


@pytest.mark.parametrize(
    "report_type",
    ["scl_protocol", "aace_29r03", "aia_g702"],
)
def test_guide_references_report_types(report_type: str) -> None:
    text = _read(_GUIDE)
    assert report_type in text, f"guide missing report_type {report_type!r}"


def test_index_links_new_guide() -> None:
    text = _read(_INDEX)
    assert "submission-deliverables.md" in text
    assert "Submission Deliverables" in text


def test_persona_table_mentions_deliverables() -> None:
    """Forensic Analyst and Cost Engineer personas should point to the new guide."""
    text = _read(_INDEX)
    # The table rows list workflow names — "Submission Deliverables" appears in both
    assert text.count("Submission Deliverables") >= 3  # 1 link + 2 persona cells
