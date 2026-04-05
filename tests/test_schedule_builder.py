# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the conversational schedule builder (fallback mode)."""

from __future__ import annotations


from src.analytics.schedule_builder import BuilderResult, _fallback_build


class TestFallbackBuilder:
    """Test keyword-based fallback (no Claude API needed)."""

    def test_returns_result(self) -> None:
        result = _fallback_build("Build a 10-story office building")
        assert isinstance(result, BuilderResult)

    def test_detects_commercial(self) -> None:
        result = _fallback_build("Office building with parking garage")
        assert result.extracted_params["project_type"] == "commercial"

    def test_detects_industrial(self) -> None:
        result = _fallback_build("Gas refinery plant with pipeline connections")
        assert result.extracted_params["project_type"] == "industrial"

    def test_detects_infrastructure(self) -> None:
        result = _fallback_build("Highway bridge construction 2km span")
        assert result.extracted_params["project_type"] == "infrastructure"

    def test_detects_residential(self) -> None:
        result = _fallback_build("50-unit apartment housing complex")
        assert result.extracted_params["project_type"] == "residential"

    def test_detects_small(self) -> None:
        result = _fallback_build("Small warehouse renovation")
        assert result.extracted_params["size_category"] == "small"

    def test_detects_large(self) -> None:
        result = _fallback_build("Large complex data center facility")
        assert result.extracted_params["size_category"] == "large"

    def test_detects_mega(self) -> None:
        result = _fallback_build("Mega project international airport terminal")
        assert result.extracted_params["size_category"] == "mega"

    def test_generates_schedule(self) -> None:
        result = _fallback_build("3-story medical clinic")
        assert result.generated is not None
        assert result.generated.activity_count > 0
        assert result.generated.predicted_duration_days > 0

    def test_has_interpretation(self) -> None:
        result = _fallback_build("Solar farm 50MW in desert")
        assert len(result.interpretation) > 0

    def test_generated_compatible_with_engines(self) -> None:
        """Generated schedule should work with all analysis engines."""
        from src.analytics.cpm import CPMCalculator

        result = _fallback_build("Commercial office tower")
        cpm = CPMCalculator(result.generated.parsed_schedule).calculate()
        assert not cpm.has_cycles
        assert cpm.project_duration > 0
