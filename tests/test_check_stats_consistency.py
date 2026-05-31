# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for scripts/check_stats_consistency.py — the stats drift validator."""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "check_stats_consistency.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("_check_stats", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["_check_stats"] = module
    spec.loader.exec_module(module)
    return module


_m = _load_module()


class TestExtractArchitectureBlock:
    def test_pulls_architecture_section(self) -> None:
        doc = (
            "# Title\n\n"
            "## Build\nfoo\n\n"
            "## Architecture\n"
            "- **43 analysis engines** in blah\n"
            "- API with 109 endpoints across 20 routers\n\n"
            "## Next\nbar\n"
        )
        block = _m.extract_architecture_block(doc)
        assert "43 analysis engines" in block
        assert "109 endpoints" in block
        # Sections after the Architecture heading must not leak in
        assert "bar" not in block

    def test_missing_section_raises(self) -> None:
        with pytest.raises(SystemExit):
            _m.extract_architecture_block("# Title\n\nNo architecture here.")

    def test_section_at_end_of_file(self) -> None:
        doc = "# Title\n\n## Architecture\n- 5 engines\n"
        block = _m.extract_architecture_block(doc)
        assert "5 engines" in block


class TestFindMismatches:
    @pytest.fixture
    def stats(self):
        return _m.Stats(
            endpoints=109,
            routers=20,
            engines=43,
            export_modules=1,
            mcp_tools=22,
            pages=54,
            migrations=23,
            charts=10,
        )

    def test_all_match_returns_empty(self, stats) -> None:
        block = (
            "- **43 analysis engines** in src/analytics/\n"
            "- **API**: FastAPI with 109 endpoints under /api/v1/ across 20 routers\n"
            "- **Frontend**: SvelteKit + Tailwind v4, 54 pages, Svelte 5 runes\n"
        )
        assert _m.find_mismatches(stats, block) == []

    def test_engine_drift_reported(self, stats) -> None:
        block = (
            "- **40 analysis engines** in src/analytics/\n"
            "- **API**: FastAPI with 109 endpoints under /api/v1/ across 20 routers\n"
            "- **Frontend**: SvelteKit + Tailwind v4, 54 pages\n"
        )
        result = _m.find_mismatches(stats, block)
        assert len(result) == 1
        assert "engines claims 40" in result[0]
        assert "canonical is 43" in result[0]

    def test_endpoint_and_router_drift(self, stats) -> None:
        block = (
            "- **43 analysis engines** in src/analytics/\n"
            "- **API**: FastAPI with 98 endpoints under /api/v1/ across 18 routers\n"
            "- **Frontend**: SvelteKit + Tailwind v4, 54 pages\n"
        )
        result = _m.find_mismatches(stats, block)
        labels = " / ".join(result)
        assert "endpoints claims 98" in labels
        assert "routers claims 18" in labels

    def test_page_drift(self, stats) -> None:
        block = (
            "- **43 analysis engines** foo\n"
            "- API with 109 endpoints across 20 routers\n"
            "- **Frontend**: SvelteKit + Tailwind v4, 52 pages, Svelte 5 runes\n"
        )
        result = _m.find_mismatches(stats, block)
        assert len(result) == 1
        assert "pages claims 52" in result[0]

    def test_absent_claim_is_not_an_error(self, stats) -> None:
        """If a doc doesn't mention a particular count, we don't synthesise one."""
        block = "- Project uses a microservice architecture.\n"
        assert _m.find_mismatches(stats, block) == []


class TestCanonicalStatsFromRepo:
    """Integration check — must pass on a clean repo."""

    def test_canonical_stats_loads(self) -> None:
        stats = _m.canonical_stats()
        assert stats.engines > 0
        assert stats.endpoints > 0
        assert stats.routers > 0
        assert stats.mcp_tools > 0
        assert stats.pages > 0
        assert stats.charts > 0


class TestI18nLandingMismatches:
    """The landing engine count lives in the i18n dicts (rendered via $t),
    out of reach of the +page.svelte hero scan and the key-set parity test."""

    def test_clean_repo_is_consistent(self) -> None:
        # On a clean repo the i18n landing.capabilities.title must match the
        # canonical engine count across every locale.
        assert _m.find_i18n_landing_mismatches(_m.canonical_stats()) == []

    def test_drift_is_reported_per_locale(self) -> None:
        stats = dataclasses.replace(_m.canonical_stats(), engines=9999)
        mismatches = _m.find_i18n_landing_mismatches(stats)
        # en + pt-BR + es each carry the count, so drift flags all three.
        assert len(mismatches) == 3
        assert all("9999" in m for m in mismatches)
