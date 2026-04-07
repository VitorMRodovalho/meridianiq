"""Tests for narrative report generator."""

from __future__ import annotations

from src.analytics.narrative_report import generate_schedule_narrative


class TestNarrativeReport:
    """Test narrative report generation."""

    def _make_summary(
        self,
        total: int = 8000,
        complete_pct: float = 25.0,
        critical: int = 500,
        near_crit: int = 200,
        neg_float: int = 300,
        avg_float: float = 50.0,
    ) -> dict:
        return {
            "total_activities": total,
            "complete_pct": complete_pct,
            "critical_count": critical,
            "near_critical_count": near_crit,
            "negative_float_count": neg_float,
            "avg_float_days": avg_float,
            "constraint_count": 100,
            "milestones_count": 50,
        }

    def test_basic_report(self) -> None:
        report = generate_schedule_narrative("Test", "2025-01-01", self._make_summary())
        assert report.title == "Schedule Status Report — Test"
        assert report.project_name == "Test"
        assert len(report.sections) >= 1
        assert report.executive_summary != ""

    def test_overview_section(self) -> None:
        report = generate_schedule_narrative("Test", "2025-01-01", self._make_summary())
        overview = report.sections[0]
        assert overview.title == "Schedule Overview"
        assert "8,000 activities" in overview.content

    def test_negative_float_warning(self) -> None:
        report = generate_schedule_narrative(
            "Test", "2025-01-01", self._make_summary(neg_float=500)
        )
        float_sections = [s for s in report.sections if s.title == "Float Analysis"]
        assert len(float_sections) == 1
        assert "500" in float_sections[0].content

    def test_critical_float_severity(self) -> None:
        report = generate_schedule_narrative(
            "Test", "2025-01-01", self._make_summary(neg_float=2000, total=8000)
        )
        float_sections = [s for s in report.sections if s.title == "Float Analysis"]
        assert float_sections[0].severity == "critical"

    def test_scorecard_section(self) -> None:
        scorecard = {
            "overall_score": 65.0,
            "overall_grade": "D",
            "dimensions": [
                {"name": "Validation", "score": 45, "grade": "F"},
                {"name": "Health", "score": 70, "grade": "C"},
            ],
        }
        report = generate_schedule_narrative(
            "Test", "2025-01-01", self._make_summary(), scorecard=scorecard
        )
        quality = [s for s in report.sections if s.title == "Quality Assessment"]
        assert len(quality) == 1
        assert "Grade D" in quality[0].content
        assert "Validation" in quality[0].content

    def test_comparison_section(self) -> None:
        comparison = {
            "summary": {
                "activities_added": 100,
                "activities_deleted": 50,
                "activities_modified": 500,
                "changed_percentage": 45.0,
            },
            "manipulation_score": 60,
        }
        report = generate_schedule_narrative(
            "Test", "2025-01-01", self._make_summary(), comparison=comparison
        )
        changes = [s for s in report.sections if s.title == "Schedule Changes"]
        assert len(changes) == 1
        assert "100" in changes[0].content
        assert "manipulation" in changes[0].content.lower()

    def test_trends_section(self) -> None:
        trends = {"insights": ["Scope growth: +500 activities", "Float erosion: -20 days"]}
        report = generate_schedule_narrative(
            "Test", "2025-01-01", self._make_summary(), trends=trends
        )
        trend_sections = [s for s in report.sections if s.title == "Schedule Trends"]
        assert len(trend_sections) == 1

    def test_executive_summary_with_critical(self) -> None:
        report = generate_schedule_narrative(
            "Test", "2025-01-01", self._make_summary(neg_float=2000, total=8000)
        )
        assert "critical" in report.executive_summary.lower()

    def test_no_float_warning_when_healthy(self) -> None:
        report = generate_schedule_narrative(
            "Test", "2025-01-01", self._make_summary(neg_float=0, avg_float=100)
        )
        float_sections = [s for s in report.sections if s.title == "Float Analysis"]
        assert len(float_sections) == 0
