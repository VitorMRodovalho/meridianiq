# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the Time Impact Analysis (TIA) engine.

Validates fragment insertion, CPM recalculation, delay classification,
and concurrency detection per AACE RP 52R-06.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.analytics.tia import (
    DelayFragment,
    DelayType,
    FragmentActivity,
    ResponsibleParty,
    TimeImpactAnalyzer,
)
from src.parser import XERReader, ParsedSchedule

SAMPLE_XER = Path(__file__).parent / "fixtures" / "sample.xer"


@pytest.fixture
def schedule() -> ParsedSchedule:
    """Parse the sample XER file."""
    reader = XERReader(SAMPLE_XER)
    return reader.parse()


@pytest.fixture
def analyzer(schedule: ParsedSchedule) -> TimeImpactAnalyzer:
    """Create a TIA analyzer with the sample schedule."""
    return TimeImpactAnalyzer(schedule)


def _make_cp_fragment(
    fragment_id: str = "FRAG-CP",
    name: str = "CP Delay Fragment",
    responsible_party: ResponsibleParty = ResponsibleParty.CONTRACTOR,
    duration_hours: float = 80.0,
) -> DelayFragment:
    """Create a fragment that inserts on the critical path.

    Inserts between A3050 (Roof Framing, CP, TF=0) and A4010 (Roof Membrane, CP, TF=0).
    """
    return DelayFragment(
        fragment_id=fragment_id,
        name=name,
        description="Test fragment on CP",
        responsible_party=responsible_party,
        activities=[
            FragmentActivity(
                fragment_activity_id=f"{fragment_id}-A",
                name="Delay Activity",
                duration_hours=duration_hours,
                predecessors=[{"activity_code": "A3050", "rel_type": "FS", "lag_hours": 0}],
                successors=[{"activity_code": "A4010", "rel_type": "FS", "lag_hours": 0}],
            )
        ],
    )


def _make_noncritical_fragment(
    fragment_id: str = "FRAG-NC",
    duration_hours: float = 40.0,
) -> DelayFragment:
    """Create a fragment on a non-critical path.

    Inserts after A1040 (Funding Approval, TF=160h = 20 days).
    This activity has no successors that would make the fragment critical.
    We connect it to A5030 (Fixtures & Fittings, TF=40h).
    """
    return DelayFragment(
        fragment_id=fragment_id,
        name="Non-Critical Delay",
        description="Test fragment off CP",
        responsible_party=ResponsibleParty.CONTRACTOR,
        activities=[
            FragmentActivity(
                fragment_activity_id=f"{fragment_id}-A",
                name="Minor Equipment Wait",
                duration_hours=duration_hours,
                predecessors=[{"activity_code": "A5030", "rel_type": "FS", "lag_hours": 0}],
                successors=[{"activity_code": "A6010", "rel_type": "FS", "lag_hours": 0}],
            )
        ],
    )


class TestSingleFragmentOnCP:
    """Test: fragment on CP should cause project delay."""

    def test_single_fragment_on_cp(self, analyzer: TimeImpactAnalyzer) -> None:
        """Fragment inserted on the critical path should increase project duration."""
        fragment = _make_cp_fragment(duration_hours=80.0)
        result = analyzer.analyze_fragment(fragment)

        assert result.delay_days > 0, f"Expected positive delay, got {result.delay_days}"
        assert result.impacted_completion_days > result.unimpacted_completion_days

    def test_cp_fragment_delay_magnitude(self, analyzer: TimeImpactAnalyzer) -> None:
        """Delay should be approximately equal to the fragment duration in days."""
        fragment = _make_cp_fragment(duration_hours=80.0)
        result = analyzer.analyze_fragment(fragment)

        # 80 hours / 8 hours per day = 10 days
        expected_delay = 80.0 / 8.0
        assert abs(result.delay_days - expected_delay) < 0.1, (
            f"Expected ~{expected_delay} days delay, got {result.delay_days}"
        )

    def test_cp_fragment_affects_critical_path(self, analyzer: TimeImpactAnalyzer) -> None:
        """Fragment on CP should be marked as critical_path_affected."""
        fragment = _make_cp_fragment()
        result = analyzer.analyze_fragment(fragment)

        assert result.critical_path_affected is True


class TestSingleFragmentOffCP:
    """Test: fragment with float should NOT cause project delay."""

    def test_single_fragment_off_cp(self, analyzer: TimeImpactAnalyzer) -> None:
        """Fragment on non-critical path (within float) should not delay project."""
        # A5030 has TF=40h = 5 days. Fragment of 2 days should not cause delay.
        fragment = _make_noncritical_fragment(duration_hours=16.0)
        result = analyzer.analyze_fragment(fragment)

        assert result.delay_days <= 0.01, f"Expected no project delay, got {result.delay_days}"

    def test_noncritical_fragment_not_on_cp(self, analyzer: TimeImpactAnalyzer) -> None:
        """Small fragment on non-CP should not be marked as CP-affecting."""
        fragment = _make_noncritical_fragment(duration_hours=16.0)
        result = analyzer.analyze_fragment(fragment)

        # Should not be on the critical path if within float
        assert result.critical_path_affected is False


class TestOwnerDelayClassification:
    """Test: owner fragment should be classified as excusable compensable."""

    def test_owner_delay_classification(self, analyzer: TimeImpactAnalyzer) -> None:
        """Owner-caused delay on CP -> EXCUSABLE_COMPENSABLE."""
        fragment = _make_cp_fragment(
            fragment_id="FRAG-OWNER",
            responsible_party=ResponsibleParty.OWNER,
        )
        result = analyzer.analyze_fragment(fragment)

        assert result.delay_type == DelayType.EXCUSABLE_COMPENSABLE


class TestContractorDelayClassification:
    """Test: contractor fragment should be classified as non-excusable."""

    def test_contractor_delay_classification(self, analyzer: TimeImpactAnalyzer) -> None:
        """Contractor-caused delay on CP -> NON_EXCUSABLE."""
        fragment = _make_cp_fragment(
            fragment_id="FRAG-CONTR",
            responsible_party=ResponsibleParty.CONTRACTOR,
        )
        result = analyzer.analyze_fragment(fragment)

        assert result.delay_type == DelayType.NON_EXCUSABLE


class TestMultipleFragments:
    """Test: analyze all fragments and verify totals."""

    def test_multiple_fragments(self, analyzer: TimeImpactAnalyzer) -> None:
        """Analyzing multiple fragments should produce correct totals."""
        fragments = [
            _make_cp_fragment(
                fragment_id="FRAG-M1",
                responsible_party=ResponsibleParty.OWNER,
                duration_hours=40.0,
            ),
            _make_cp_fragment(
                fragment_id="FRAG-M2",
                responsible_party=ResponsibleParty.CONTRACTOR,
                duration_hours=40.0,
            ),
        ]

        analysis = analyzer.analyze_all(fragments)

        assert len(analysis.results) == 2
        assert analysis.total_owner_delay > 0
        assert analysis.total_contractor_delay > 0
        assert analysis.net_delay > 0

    def test_analysis_has_summary(self, analyzer: TimeImpactAnalyzer) -> None:
        """Analysis should produce a summary dictionary."""
        fragments = [
            _make_cp_fragment(fragment_id="FRAG-S1"),
        ]
        analysis = analyzer.analyze_all(fragments)

        assert "fragment_count" in analysis.summary
        assert "base_completion_days" in analysis.summary
        assert analysis.summary["fragment_count"] == 1


class TestConcurrentDetection:
    """Test: two CP fragments should be marked concurrent."""

    def test_concurrent_detection(self, analyzer: TimeImpactAnalyzer) -> None:
        """Two fragments both on CP with delay should be marked concurrent."""
        fragments = [
            _make_cp_fragment(
                fragment_id="FRAG-C1",
                responsible_party=ResponsibleParty.OWNER,
                duration_hours=40.0,
            ),
            _make_cp_fragment(
                fragment_id="FRAG-C2",
                responsible_party=ResponsibleParty.CONTRACTOR,
                duration_hours=40.0,
            ),
        ]

        analysis = analyzer.analyze_all(fragments)

        # Both should be on CP and have delay > 0
        for r in analysis.results:
            assert r.delay_days > 0
            assert r.critical_path_affected is True

        # Both should be marked as concurrent
        for r in analysis.results:
            assert len(r.concurrent_with) > 0
            assert r.delay_type == DelayType.CONCURRENT


class TestFragmentInsertion:
    """Test: verify NetworkX graph has fragment nodes and edges."""

    def test_fragment_insertion(self, analyzer: TimeImpactAnalyzer) -> None:
        """Fragment activities should appear in the impacted graph."""
        fragment = _make_cp_fragment(fragment_id="FRAG-INS")

        impacted_graph = analyzer._build_impacted_graph(fragment)

        # Fragment activity node should exist
        assert "FRAG-INS-A" in impacted_graph.nodes

        # Fragment should have correct duration
        duration = impacted_graph.nodes["FRAG-INS-A"]["duration"]
        assert abs(duration - 80.0 / 8.0) < 0.01

        # Should have edges from predecessor and to successor
        # A3050 -> FRAG-INS-A
        pred_id = analyzer._code_to_id["A3050"]
        assert impacted_graph.has_edge(pred_id, "FRAG-INS-A")

        # FRAG-INS-A -> A4010
        succ_id = analyzer._code_to_id["A4010"]
        assert impacted_graph.has_edge("FRAG-INS-A", succ_id)

    def test_base_graph_unchanged(self, analyzer: TimeImpactAnalyzer) -> None:
        """Building an impacted graph should not modify the base graph."""
        base_node_count = len(analyzer._base_graph.nodes)
        fragment = _make_cp_fragment()

        _ = analyzer._build_impacted_graph(fragment)

        assert len(analyzer._base_graph.nodes) == base_node_count


class TestZeroDurationFragment:
    """Test: edge case -- zero duration fragment."""

    def test_zero_duration_fragment(self, analyzer: TimeImpactAnalyzer) -> None:
        """A zero-duration fragment should cause no delay."""
        fragment = _make_cp_fragment(
            fragment_id="FRAG-ZERO",
            duration_hours=0.0,
        )
        result = analyzer.analyze_fragment(fragment)

        assert abs(result.delay_days) < 0.01, f"Expected zero delay, got {result.delay_days}"
