# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for ML schedule generation engine."""

from __future__ import annotations


import pytest

from src.analytics.schedule_generation import (
    GeneratedSchedule,
    GenerationInput,
    generate_schedule,
)


class TestBasicGeneration:
    def test_returns_result(self) -> None:
        params = GenerationInput(project_type="commercial")
        result = generate_schedule(params)
        assert isinstance(result, GeneratedSchedule)

    def test_has_activities(self) -> None:
        params = GenerationInput(project_type="commercial")
        result = generate_schedule(params)
        assert result.activity_count > 0
        assert len(result.activities) == result.activity_count

    def test_has_relationships(self) -> None:
        params = GenerationInput(project_type="commercial")
        result = generate_schedule(params)
        assert result.relationship_count > 0

    def test_has_predicted_duration(self) -> None:
        params = GenerationInput(project_type="commercial")
        result = generate_schedule(params)
        assert result.predicted_duration_days > 0

    def test_has_parsed_schedule(self) -> None:
        params = GenerationInput(project_type="commercial")
        result = generate_schedule(params)
        assert result.parsed_schedule is not None
        assert len(result.parsed_schedule.activities) == result.activity_count


class TestProjectTypes:
    @pytest.mark.parametrize("ptype", ["commercial", "industrial", "infrastructure", "residential"])
    def test_all_project_types(self, ptype: str) -> None:
        params = GenerationInput(project_type=ptype)
        result = generate_schedule(params)
        assert result.activity_count > 0
        assert result.predicted_duration_days > 0

    def test_unknown_type_falls_back(self) -> None:
        params = GenerationInput(project_type="unknown_type")
        result = generate_schedule(params)
        assert result.activity_count > 0  # Falls back to commercial


class TestSizeCategories:
    def test_larger_has_more_activities(self) -> None:
        small = generate_schedule(GenerationInput(size_category="small"))
        large = generate_schedule(GenerationInput(size_category="large"))
        assert large.activity_count >= small.activity_count

    def test_mega_project(self) -> None:
        params = GenerationInput(size_category="mega")
        result = generate_schedule(params)
        assert result.activity_count > 20


class TestTargetDuration:
    def test_calibration(self) -> None:
        """With target duration, result should be close to target."""
        params = GenerationInput(target_duration_days=200)
        result = generate_schedule(params)
        # Should be within 30% of target
        assert abs(result.predicted_duration_days - 200) / 200 < 0.30

    def test_no_target_uses_natural(self) -> None:
        params = GenerationInput(target_duration_days=0)
        result = generate_schedule(params)
        assert result.predicted_duration_days > 0


class TestComplexity:
    def test_higher_complexity_longer(self) -> None:
        simple = generate_schedule(GenerationInput(complexity_factor=0.5))
        complex_ = generate_schedule(GenerationInput(complexity_factor=2.0))
        assert complex_.predicted_duration_days > simple.predicted_duration_days


class TestParsedScheduleCompatibility:
    def test_cpm_runs_on_generated(self) -> None:
        """Generated schedule should be valid for CPM analysis."""
        from src.analytics.cpm import CPMCalculator

        params = GenerationInput(project_type="industrial")
        result = generate_schedule(params)
        cpm = CPMCalculator(result.parsed_schedule).calculate()
        assert not cpm.has_cycles
        assert cpm.project_duration > 0
        assert len(cpm.critical_path) > 0

    def test_dcma_runs_on_generated(self) -> None:
        """Generated schedule should be valid for DCMA assessment."""
        from src.analytics.dcma14 import DCMA14Analyzer

        params = GenerationInput(project_type="commercial")
        result = generate_schedule(params)
        dcma = DCMA14Analyzer(result.parsed_schedule).analyze()
        assert dcma.overall_score > 0

    def test_delay_prediction_runs_on_generated(self) -> None:
        """Generated schedule should work with delay prediction."""
        from src.analytics.delay_prediction import predict_delays

        params = GenerationInput(project_type="residential")
        result = generate_schedule(params)
        dp = predict_delays(result.parsed_schedule)
        assert len(dp.activity_risks) > 0

    def test_scorecard_runs_on_generated(self) -> None:
        """Generated schedule should work with scorecard."""
        from src.analytics.scorecard import calculate_scorecard

        params = GenerationInput(project_type="commercial")
        result = generate_schedule(params)
        sc = calculate_scorecard(result.parsed_schedule)
        assert sc.overall_score > 0


class TestSummary:
    def test_summary_keys(self) -> None:
        params = GenerationInput(project_type="commercial")
        result = generate_schedule(params)
        s = result.summary
        assert "project_type" in s
        assert "activity_count" in s
        assert "predicted_duration_days" in s
        assert "methodology" in s
        assert "references" in s

    def test_methodology_set(self) -> None:
        params = GenerationInput(project_type="industrial")
        result = generate_schedule(params)
        assert (
            "template" in result.methodology.lower() or "generation" in result.methodology.lower()
        )


class TestReproducibility:
    def test_same_params_same_result(self) -> None:
        params = GenerationInput(project_type="commercial", size_category="medium")
        r1 = generate_schedule(params)
        r2 = generate_schedule(params)
        assert r1.activity_count == r2.activity_count
        assert r1.predicted_duration_days == r2.predicted_duration_days
