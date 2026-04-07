"""Tests for schedule trend analysis engine."""

from __future__ import annotations

from src.analytics.schedule_trends import TrendPoint, analyze_trends


class TestTrendAnalysis:
    """Test trend computation and insight generation."""

    def _make_point(
        self,
        pid: str = "p1",
        dd: str = "2025-01-01",
        acts: int = 100,
        rels: int = 150,
        complete: int = 10,
        avg_float: float = 20.0,
        neg_float: int = 5,
        critical: int = 10,
        near_crit: int = 15,
        name: str = "Test UP 01",
        up: int | None = 1,
    ) -> TrendPoint:
        return TrendPoint(
            project_id=pid,
            project_name=name,
            data_date=dd,
            update_number=up,
            activity_count=acts,
            relationship_count=rels,
            complete_count=complete,
            active_count=5,
            not_started_count=acts - complete - 5,
            complete_pct=round(complete / acts * 100, 1) if acts else 0.0,
            avg_total_float=avg_float,
            negative_float_count=neg_float,
            zero_float_count=3,
            critical_count=critical,
            near_critical_count=near_crit,
            logic_density=round(rels / acts, 2) if acts else 0.0,
        )

    def test_empty_points(self) -> None:
        result = analyze_trends([])
        assert result.series_name == ""
        assert result.points == []

    def test_single_point(self) -> None:
        p = self._make_point()
        result = analyze_trends([p])
        assert len(result.points) == 1
        assert result.insights == []

    def test_scope_growth_insight(self) -> None:
        points = [
            self._make_point(pid="p1", dd="2025-01-01", acts=100, up=1),
            self._make_point(pid="p2", dd="2025-02-01", acts=120, up=2),
        ]
        result = analyze_trends(points)
        assert any("Scope growth" in i for i in result.insights)

    def test_float_erosion_insight(self) -> None:
        points = [
            self._make_point(pid="p1", dd="2025-01-01", avg_float=30.0),
            self._make_point(pid="p2", dd="2025-02-01", avg_float=20.0),
        ]
        result = analyze_trends(points)
        assert any("Float erosion" in i for i in result.insights)

    def test_completion_progress_insight(self) -> None:
        points = [
            self._make_point(pid="p1", dd="2025-01-01", complete=10, acts=100),
            self._make_point(pid="p2", dd="2025-02-01", complete=30, acts=100),
        ]
        result = analyze_trends(points)
        assert any("Progress" in i for i in result.insights)

    def test_critical_path_growth(self) -> None:
        points = [
            self._make_point(pid="p1", dd="2025-01-01", critical=10),
            self._make_point(pid="p2", dd="2025-06-01", critical=50),
        ]
        result = analyze_trends(points)
        assert any("Critical path" in i for i in result.insights)

    def test_sorted_by_data_date(self) -> None:
        points = [
            self._make_point(pid="p2", dd="2025-03-01"),
            self._make_point(pid="p1", dd="2025-01-01"),
        ]
        result = analyze_trends(points)
        assert result.points[0].data_date == "2025-01-01"
        assert result.points[1].data_date == "2025-03-01"

    def test_series_name_extraction(self) -> None:
        points = [
            self._make_point(pid="p1", dd="2025-01-01", name="FDTP - MPS UP 05 Rev 00"),
        ]
        result = analyze_trends(points)
        assert result.series_name == "FDTP - MPS"

    def test_negative_float_trend(self) -> None:
        points = [
            self._make_point(pid="p1", dd="2025-01-01", neg_float=5),
            self._make_point(pid="p2", dd="2025-06-01", neg_float=25),
        ]
        result = analyze_trends(points)
        assert any("Negative float" in i for i in result.insights)

    def test_no_false_insights(self) -> None:
        """Stable schedule should not generate insights."""
        points = [
            self._make_point(pid="p1", dd="2025-01-01", acts=100, avg_float=20.0, critical=10),
            self._make_point(pid="p2", dd="2025-02-01", acts=102, avg_float=19.0, critical=11),
        ]
        result = analyze_trends(points)
        # Small changes should NOT trigger insights
        assert not any("Scope growth" in i for i in result.insights)
        assert not any("Float erosion" in i for i in result.insights)
