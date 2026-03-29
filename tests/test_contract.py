# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the contract compliance checking module.

Validates compliance checks against standard construction contract
provisions per AIA A201, ConsensusDocs 200, and FIDIC conditions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.analytics.contract import (
    ComplianceStatus,
    ContractComplianceChecker,
    ProvisionCategory,
)
from src.analytics.tia import (
    DelayFragment,
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


@pytest.fixture
def checker() -> ContractComplianceChecker:
    """Create a contract compliance checker with default provisions."""
    return ContractComplianceChecker()


def _make_cp_fragment(
    responsible_party: ResponsibleParty = ResponsibleParty.CONTRACTOR,
    duration_hours: float = 80.0,
) -> DelayFragment:
    """Create a fragment on the critical path."""
    return DelayFragment(
        fragment_id="FRAG-TEST",
        name="Test Delay",
        description="Test fragment for compliance",
        responsible_party=responsible_party,
        activities=[
            FragmentActivity(
                fragment_activity_id="FRAG-TEST-A",
                name="Delay Activity",
                duration_hours=duration_hours,
                predecessors=[{"activity_code": "A3050", "rel_type": "FS", "lag_hours": 0}],
                successors=[{"activity_code": "A4010", "rel_type": "FS", "lag_hours": 0}],
            )
        ],
    )


def _make_noncritical_fragment(duration_hours: float = 16.0) -> DelayFragment:
    """Create a fragment on a non-critical path."""
    return DelayFragment(
        fragment_id="FRAG-NC",
        name="Non-Critical Delay",
        description="Test fragment off CP",
        responsible_party=ResponsibleParty.CONTRACTOR,
        activities=[
            FragmentActivity(
                fragment_activity_id="FRAG-NC-A",
                name="Minor Delay",
                duration_hours=duration_hours,
                predecessors=[{"activity_code": "A5030", "rel_type": "FS", "lag_hours": 0}],
                successors=[{"activity_code": "A6010", "rel_type": "FS", "lag_hours": 0}],
            )
        ],
    )


class TestDefaultProvisions:
    """Test: verify standard provisions exist."""

    def test_default_provisions_exist(self, checker: ContractComplianceChecker) -> None:
        """Checker should have default provisions."""
        assert len(checker.provisions) >= 5

    def test_default_provisions_have_required_fields(
        self, checker: ContractComplianceChecker
    ) -> None:
        """Each default provision should have id, name, description, category."""
        for p in checker.provisions:
            assert p.provision_id
            assert p.name
            assert p.description
            assert p.category

    def test_notice_provision_exists(self, checker: ContractComplianceChecker) -> None:
        """There should be a notice provision."""
        notice_provs = [p for p in checker.provisions if p.category == ProvisionCategory.NOTICE]
        assert len(notice_provs) >= 1

    def test_float_ownership_provision_exists(self, checker: ContractComplianceChecker) -> None:
        """There should be a float ownership provision."""
        float_provs = [
            p for p in checker.provisions if p.category == ProvisionCategory.FLOAT_OWNERSHIP
        ]
        assert len(float_provs) >= 1


class TestFloatOwnershipCheck:
    """Test: fragment consuming float should produce a finding."""

    def test_float_ownership_check_cp_fragment(
        self,
        analyzer: TimeImpactAnalyzer,
        checker: ContractComplianceChecker,
    ) -> None:
        """CP fragment should produce a float ownership warning."""
        fragment = _make_cp_fragment()
        tia_result = analyzer.analyze_fragment(fragment)
        checks = checker.check_fragment(fragment, tia_result)

        float_checks = [
            c for c in checks if c.provision.category == ProvisionCategory.FLOAT_OWNERSHIP
        ]
        assert len(float_checks) == 1
        # CP fragment: warning about no float available
        assert float_checks[0].status == ComplianceStatus.WARNING

    def test_float_ownership_noncritical(
        self,
        analyzer: TimeImpactAnalyzer,
        checker: ContractComplianceChecker,
    ) -> None:
        """Non-critical fragment consuming float should produce a finding."""
        fragment = _make_noncritical_fragment(duration_hours=16.0)
        tia_result = analyzer.analyze_fragment(fragment)
        checks = checker.check_fragment(fragment, tia_result)

        float_checks = [
            c for c in checks if c.provision.category == ProvisionCategory.FLOAT_OWNERSHIP
        ]
        assert len(float_checks) == 1


class TestConcurrentCheck:
    """Test: concurrent fragments should produce a finding."""

    def test_concurrent_check(
        self,
        analyzer: TimeImpactAnalyzer,
        checker: ContractComplianceChecker,
    ) -> None:
        """Concurrent fragments should produce concurrent delay findings."""
        fragments = [
            DelayFragment(
                fragment_id="FRAG-CC1",
                name="Owner Delay",
                description="Owner delay on CP",
                responsible_party=ResponsibleParty.OWNER,
                activities=[
                    FragmentActivity(
                        fragment_activity_id="FRAG-CC1-A",
                        name="Owner Wait",
                        duration_hours=40.0,
                        predecessors=[{"activity_code": "A3050", "rel_type": "FS", "lag_hours": 0}],
                        successors=[{"activity_code": "A4010", "rel_type": "FS", "lag_hours": 0}],
                    )
                ],
            ),
            DelayFragment(
                fragment_id="FRAG-CC2",
                name="Contractor Delay",
                description="Contractor delay on CP",
                responsible_party=ResponsibleParty.CONTRACTOR,
                activities=[
                    FragmentActivity(
                        fragment_activity_id="FRAG-CC2-A",
                        name="Contractor Wait",
                        duration_hours=40.0,
                        predecessors=[{"activity_code": "A3050", "rel_type": "FS", "lag_hours": 0}],
                        successors=[{"activity_code": "A4010", "rel_type": "FS", "lag_hours": 0}],
                    )
                ],
            ),
        ]

        analysis = analyzer.analyze_all(fragments)

        # Check all compliance
        all_checks = checker.check_all(fragments, analysis.results)

        # Should have concurrent delay checks with warnings
        concurrent_checks = [
            c
            for c in all_checks
            if c.provision.category == ProvisionCategory.CONCURRENT_DELAY
            and c.status == ComplianceStatus.WARNING
        ]
        assert len(concurrent_checks) >= 1


class TestCheckAll:
    """Test: check_all should produce checks for all fragments."""

    def test_check_all_produces_checks(
        self,
        analyzer: TimeImpactAnalyzer,
        checker: ContractComplianceChecker,
    ) -> None:
        """check_all should return checks for each fragment."""
        fragments = [_make_cp_fragment()]
        analysis = analyzer.analyze_all(fragments)
        all_checks = checker.check_all(fragments, analysis.results)

        assert len(all_checks) > 0
        # Each fragment should produce at least 4 checks (notice, float, pacing, concurrent, time_ext)
        frag_checks = [c for c in all_checks if c.fragment_id == "FRAG-TEST"]
        assert len(frag_checks) >= 4
