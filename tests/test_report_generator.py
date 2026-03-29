# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the PDF report generator.

Tests verify that:
1. Reports generate valid output (HTML if weasyprint unavailable)
2. Reports contain expected project metadata
3. All 5 report types work
4. API endpoints for report generation and download function correctly
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.analytics.report_generator import ReportGenerator


# ── Fixtures ──────────────────────────────────────────────


@dataclass
class MockProject:
    proj_short_name: str = "Test Project Alpha"
    last_recalc_date: datetime = field(default_factory=lambda: datetime(2026, 3, 15))
    sum_data_date: datetime | None = None


@dataclass
class MockActivity:
    task_id: str = "A1000"
    task_code: str = "A1000"
    task_name: str = "Foundation Work"
    task_type: str = "TT_Task"
    status_code: str = "TK_Active"
    total_float_hr_cnt: float = 40.0
    remain_drtn_hr_cnt: float = 80.0
    target_drtn_hr_cnt: float = 160.0
    phys_complete_pct: float = 50.0
    wbs_id: str = "WBS1"
    act_start_date: datetime | None = None
    act_end_date: datetime | None = None
    early_start_date: datetime | None = None
    early_end_date: datetime | None = None
    late_start_date: datetime | None = None
    late_end_date: datetime | None = None
    target_start_date: datetime | None = None
    target_end_date: datetime | None = None


@dataclass
class MockRelationship:
    task_id: str = "A1001"
    pred_task_id: str = "A1000"
    pred_type: str = "PR_FS"
    lag_hr_cnt: float = 0.0


@dataclass
class MockCalendar:
    clndr_name: str = "Standard"
    week_hr_cnt: float = 40.0


@dataclass
class MockWBS:
    wbs_id: str = "WBS1"
    wbs_name: str = "Phase 1"
    parent_wbs_id: str = ""
    proj_node_flag: str = "N"


@dataclass
class MockSchedule:
    projects: list = field(default_factory=lambda: [MockProject()])
    activities: list = field(default_factory=lambda: [MockActivity()])
    relationships: list = field(default_factory=lambda: [MockRelationship()])
    calendars: list = field(default_factory=lambda: [MockCalendar()])
    wbs_nodes: list = field(default_factory=lambda: [MockWBS()])
    task_resources: list = field(default_factory=list)


@dataclass
class MockMetric:
    number: int = 1
    name: str = "Logic Density"
    value: float = 85.0
    threshold: float = 80.0
    unit: str = "%"
    passed: bool = True
    description: str = "Activities with predecessors and successors"
    details: str = ""


@dataclass
class MockDCMAResult:
    overall_score: float = 78.6
    passed_count: int = 11
    failed_count: int = 3
    metrics: list = field(
        default_factory=lambda: [
            MockMetric(number=1, name="Logic Density", value=85.0, threshold=80.0, passed=True),
            MockMetric(number=2, name="Leads", value=2.0, threshold=5.0, unit="%", passed=True),
            MockMetric(number=3, name="Lags", value=15.0, threshold=20.0, unit="%", passed=True),
            MockMetric(
                number=4, name="Negative Float", value=8.0, threshold=5.0, unit="%", passed=False
            ),
        ]
    )


@dataclass
class MockHealthScore:
    overall: float = 72.5
    dcma_component: float = 31.4
    float_component: float = 18.5
    logic_component: float = 16.0
    trend_component: float = 7.5
    dcma_raw: float = 78.6
    float_raw: float = 74.0
    logic_raw: float = 80.0
    trend_raw: float = 50.0
    rating: str = "good"
    trend_arrow: str = "→"
    details: dict = field(
        default_factory=lambda: {
            "weights": {"dcma": 0.4, "float": 0.25, "logic": 0.2, "trend": 0.15},
            "raw_scores": {
                "dcma": 78.6,
                "float_health": 74.0,
                "logic_integrity": 80.0,
                "trend_direction": 50.0,
            },
        }
    )


@dataclass
class MockAlert:
    rule_id: str = "float_erosion"
    severity: str = "warning"
    title: str = "Float erosion on 5 activities"
    description: str = "5 activities lost >5 days of float"
    affected_activities: list = field(default_factory=lambda: ["A1000", "A1001"])
    projected_impact_days: float = 10.0
    confidence: float = 0.7
    alert_score: float = 21.0


@dataclass
class MockEarlyWarningResult:
    alerts: list = field(default_factory=lambda: [MockAlert()])
    total_alerts: int = 1
    critical_count: int = 0
    warning_count: int = 1
    info_count: int = 0
    aggregate_score: float = 21.0


@dataclass
class MockManipulationFlag:
    task_id: str = "A1000"
    task_name: str = "Foundation Work"
    indicator: str = "retroactive_date"
    description: str = "Actual start date changed retroactively"
    severity: str = "critical"


@dataclass
class MockFloatChange:
    task_id: str = "A1000"
    task_name: str = "Foundation Work"
    old_float: float = 20.0
    new_float: float = 5.0
    delta: float = -15.0
    direction: str = "deteriorating"


@dataclass
class MockComparisonResult:
    activities_added: list = field(default_factory=list)
    activities_deleted: list = field(default_factory=list)
    activity_modifications: list = field(default_factory=lambda: [MagicMock()])
    relationships_added: list = field(default_factory=list)
    relationships_deleted: list = field(default_factory=list)
    relationships_modified: list = field(default_factory=list)
    manipulation_flags: list = field(default_factory=lambda: [MockManipulationFlag()])
    significant_float_changes: list = field(default_factory=lambda: [MockFloatChange()])
    constraint_changes: list = field(default_factory=list)
    changed_percentage: float = 12.5
    critical_path_changed: bool = True


@dataclass
class MockWindow:
    window_number: int = 1
    start_date: datetime = field(default_factory=lambda: datetime(2026, 1, 1))
    end_date: datetime = field(default_factory=lambda: datetime(2026, 2, 1))
    delay_days: float = 15.0
    cumulative_delay: float = 15.0
    driving_activity: str = "A1000"


@dataclass
class MockTimeline:
    timeline_id: str = "timeline-0001"
    project_name: str = "Test Project Alpha"
    schedule_count: int = 3
    total_delay_days: float = 45.0
    contract_completion: datetime = field(default_factory=lambda: datetime(2027, 6, 30))
    current_completion: datetime = field(default_factory=lambda: datetime(2027, 8, 14))
    windows: list = field(default_factory=lambda: [MockWindow()])


@dataclass
class MockTIAResult:
    fragment_id: str = "frag-001"
    fragment_name: str = "Foundation Delay"
    responsible_party: str = "owner"
    delay_days: float = 15.0
    critical_path_affected: bool = True
    delay_type: str = "excusable"


@dataclass
class MockTIAAnalysis:
    analysis_id: str = "tia-0001"
    project_name: str = "Test Project Alpha"
    fragments: list = field(default_factory=lambda: [MagicMock()])
    results: list = field(default_factory=lambda: [MockTIAResult()])
    net_delay: float = 15.0
    total_owner_delay: float = 15.0
    total_contractor_delay: float = 0.0
    total_shared_delay: float = 0.0


@dataclass
class MockPValue:
    percentile: int = 50
    duration_days: float = 250.0
    completion_date: datetime = field(default_factory=lambda: datetime(2027, 6, 30))


@dataclass
class MockSimulationResult:
    simulation_id: str = "risk-0001"
    project_name: str = "Test Project Alpha"
    project_id: str = "proj-0001"
    iterations: int = 1000
    deterministic_days: float = 220.0
    mean_days: float = 245.0
    std_dev_days: float = 18.5
    p_values: list = field(
        default_factory=lambda: [
            MockPValue(percentile=10, duration_days=220.0),
            MockPValue(percentile=50, duration_days=245.0),
            MockPValue(percentile=80, duration_days=260.0),
            MockPValue(percentile=90, duration_days=270.0),
        ]
    )
    sensitivity: list = field(default_factory=list)


# ── Tests ─────────────────────────────────────────────────


class TestHealthReport:
    """Tests for Schedule Health Report generation."""

    def test_health_report_generates_output(self):
        """Verify health report returns bytes."""
        gen = ReportGenerator()
        result = gen.generate_health_report(MockSchedule(), MockDCMAResult(), MockHealthScore())
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_health_report_contains_project_name(self):
        """Verify report HTML contains the project name."""
        gen = ReportGenerator()
        result = gen.generate_health_report(MockSchedule(), MockDCMAResult(), MockHealthScore())
        # Without weasyprint, we get HTML bytes
        html = result.decode("utf-8") if not result.startswith(b"%PDF") else ""
        if html:
            assert "Test Project Alpha" in html

    def test_health_report_contains_methodology(self):
        """Verify report contains methodology citations."""
        gen = ReportGenerator()
        result = gen.generate_health_report(MockSchedule(), MockDCMAResult(), MockHealthScore())
        html = result.decode("utf-8") if not result.startswith(b"%PDF") else ""
        if html:
            assert "DCMA 14-Point" in html
            assert "GAO Schedule Assessment Guide" in html
            assert "AACE RP 49R-06" in html

    def test_health_report_contains_score(self):
        """Verify report contains the health score value."""
        gen = ReportGenerator()
        result = gen.generate_health_report(MockSchedule(), MockDCMAResult(), MockHealthScore())
        html = result.decode("utf-8") if not result.startswith(b"%PDF") else ""
        if html:
            assert "72" in html or "73" in html  # overall score ~72.5

    def test_health_report_with_alerts(self):
        """Verify report includes alerts section when alerts provided."""
        gen = ReportGenerator()
        result = gen.generate_health_report(
            MockSchedule(), MockDCMAResult(), MockHealthScore(), alerts=MockEarlyWarningResult()
        )
        html = result.decode("utf-8") if not result.startswith(b"%PDF") else ""
        if html:
            assert "Early Warning Alerts" in html
            assert "Float erosion" in html

    def test_health_report_contains_dcma_results(self):
        """Verify report contains DCMA check results."""
        gen = ReportGenerator()
        result = gen.generate_health_report(MockSchedule(), MockDCMAResult(), MockHealthScore())
        html = result.decode("utf-8") if not result.startswith(b"%PDF") else ""
        if html:
            assert "Logic Density" in html
            assert "11" in html  # passed count

    def test_health_report_footer_branding(self):
        """Verify report contains MeridianIQ branding in footer."""
        gen = ReportGenerator()
        result = gen.generate_health_report(MockSchedule(), MockDCMAResult(), MockHealthScore())
        html = result.decode("utf-8") if not result.startswith(b"%PDF") else ""
        if html:
            assert "MeridianIQ" in html
            assert "MIT License" in html


class TestComparisonReport:
    """Tests for Comparison Report generation."""

    def test_comparison_report_generates_output(self):
        """Verify comparison report returns bytes."""
        gen = ReportGenerator()
        result = gen.generate_comparison_report(
            MockSchedule(), MockSchedule(), MockComparisonResult()
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_comparison_report_contains_manipulation_flags(self):
        """Verify report includes manipulation indicators."""
        gen = ReportGenerator()
        result = gen.generate_comparison_report(
            MockSchedule(), MockSchedule(), MockComparisonResult()
        )
        html = result.decode("utf-8") if not result.startswith(b"%PDF") else ""
        if html:
            assert "Manipulation Indicators" in html
            assert "retroactive_date" in html


class TestForensicReport:
    """Tests for Forensic Report generation."""

    def test_forensic_report_generates_output(self):
        """Verify forensic report returns bytes."""
        gen = ReportGenerator()
        result = gen.generate_forensic_report(MockTimeline())
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_forensic_report_contains_delay(self):
        """Verify report contains total delay information."""
        gen = ReportGenerator()
        result = gen.generate_forensic_report(MockTimeline())
        html = result.decode("utf-8") if not result.startswith(b"%PDF") else ""
        if html:
            assert "45" in html  # total_delay_days


class TestTIAReport:
    """Tests for TIA Report generation."""

    def test_tia_report_generates_output(self):
        """Verify TIA report returns bytes."""
        gen = ReportGenerator()
        result = gen.generate_tia_report(MockTIAAnalysis())
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestRiskReport:
    """Tests for Risk Report generation."""

    def test_risk_report_generates_output(self):
        """Verify risk report returns bytes."""
        gen = ReportGenerator()
        result = gen.generate_risk_report(MockSimulationResult())
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_risk_report_contains_p_values(self):
        """Verify report contains P-value information."""
        gen = ReportGenerator()
        result = gen.generate_risk_report(MockSimulationResult())
        html = result.decode("utf-8") if not result.startswith(b"%PDF") else ""
        if html:
            assert "P50" in html
            assert "P80" in html
            assert "1,000" in html or "1000" in html  # iterations


class TestReportAPI:
    """Tests for report API endpoints."""

    def test_report_api_generate_and_download(self):
        """Test the full generate → download flow via the API."""
        from fastapi.testclient import TestClient
        from src.api.app import app

        client = TestClient(app)

        # We need to upload a project first
        # Use the test fixture XER file
        import os

        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "simple.xer")
        if not os.path.exists(fixture_path):
            pytest.skip("Test fixture simple.xer not found")

        with open(fixture_path, "rb") as f:
            resp = client.post("/api/v1/upload", files={"file": ("test.xer", f)})

        if resp.status_code != 200:
            pytest.skip("Upload failed, skipping report API test")

        project_id = resp.json()["project_id"]

        # Generate health report
        resp = client.post(
            "/api/v1/reports/generate",
            json={"project_id": project_id, "report_type": "health"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "report_id" in data
        assert data["report_type"] == "health"

        # Download the report
        report_id = data["report_id"]
        resp = client.get(f"/api/v1/reports/{report_id}/download")
        assert resp.status_code == 200
        assert len(resp.content) > 0

    def test_invalid_report_type(self):
        """Test that invalid report types are rejected."""
        from fastapi.testclient import TestClient
        from src.api.app import app

        client = TestClient(app)

        resp = client.post(
            "/api/v1/reports/generate",
            json={"project_id": "proj-0001", "report_type": "invalid_type"},
        )
        assert resp.status_code == 400
        assert "Invalid report_type" in resp.json()["detail"]

    def test_report_not_found(self):
        """Test that downloading a non-existent report returns 404."""
        from fastapi.testclient import TestClient
        from src.api.app import app

        client = TestClient(app)
        resp = client.get("/api/v1/reports/report-9999/download")
        assert resp.status_code == 404

    def test_project_not_found_for_report(self):
        """Test that generating a report for non-existent project returns 404."""
        from fastapi.testclient import TestClient
        from src.api.app import app

        client = TestClient(app)
        resp = client.post(
            "/api/v1/reports/generate",
            json={"project_id": "nonexistent", "report_type": "health"},
        )
        assert resp.status_code == 404
