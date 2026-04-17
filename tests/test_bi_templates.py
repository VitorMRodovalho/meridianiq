# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Smoke tests for samples/bi-templates.

These guards protect the v3.8 BI template deliverables from silent
regression (accidental deletion, renamed endpoints leaking into docs).
They are *structural* only — nothing here loads Power BI, Tableau, or
Looker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_BI = _ROOT / "samples" / "bi-templates"


def _read(path: Path) -> str:
    assert path.exists(), f"template file missing: {path}"
    return path.read_text(encoding="utf-8")


class TestTemplatesPresent:
    def test_parent_readme(self) -> None:
        text = _read(_BI / "README.md")
        assert "/api/v1/bi/projects" in text
        assert "/api/v1/bi/dcma-metrics" in text
        assert "/api/v1/bi/activities" in text

    def test_powerbi_files(self) -> None:
        pq = _read(_BI / "powerbi" / "meridianiq.pq")
        assert "Projects" in pq
        assert "DCMAMetrics" in pq
        assert "ActivitiesFn" in pq
        assert "/api/v1/bi/projects" in pq
        assert "/api/v1/bi/dcma-metrics" in pq
        assert "/api/v1/bi/activities" in pq

        dax = _read(_BI / "powerbi" / "measures.dax")
        assert "Avg DCMA Score" in dax
        assert "Critical Activity Ratio" in dax

        _read(_BI / "powerbi" / "README.md")

    def test_tableau_files(self) -> None:
        tds = _read(_BI / "tableau" / "meridianiq.tds")
        assert tds.lstrip().startswith("<?xml")
        assert "datasource" in tds
        assert "dcma_score" in tds

        _read(_BI / "tableau" / "README.md")

    def test_looker_files(self) -> None:
        model = _read(_BI / "looker" / "meridianiq.model.lkml")
        assert "explore: projects" in model
        assert "explore: dcma_metrics" in model
        assert "explore: activities" in model

        view = _read(_BI / "looker" / "meridianiq.view.lkml")
        assert "view: projects" in view
        assert "view: dcma_metrics" in view
        assert "view: activities" in view

        _read(_BI / "looker" / "README.md")

    def test_user_guide_link(self) -> None:
        guide = _read(_ROOT / "docs" / "user-guide" / "bi-dashboards.md")
        assert "/api/v1/bi/" in guide
        assert "samples/bi-templates" in guide

        index = _read(_ROOT / "docs" / "user-guide" / "README.md")
        assert "bi-dashboards.md" in index


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v1/bi/projects",
        "/api/v1/bi/dcma-metrics",
        "/api/v1/bi/activities",
    ],
)
def test_all_three_endpoints_referenced_in_parent_readme(endpoint: str) -> None:
    text = _read(_BI / "README.md")
    assert endpoint in text, f"parent README must document {endpoint}"
