# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Contract compliance checking for delay events.

Checks delay events against standard construction contract provisions
per AIA A201, ConsensusDocs 200, and FIDIC conditions.

References:
    - AIA A201-2017 General Conditions of the Contract for Construction
    - ConsensusDocs 200 Standard Agreement and General Conditions
    - FIDIC Conditions of Contract (Red Book, 1999)
    - AACE RP 52R-06 Time Impact Analysis
    - AACE RP 29R-03 Forensic Schedule Analysis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.analytics.tia import (
    DelayFragment,
    ResponsibleParty,
    TIAResult,
)

logger = logging.getLogger(__name__)


class ComplianceStatus(str, Enum):
    """Status of a compliance check."""

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    INFO = "info"


class ProvisionCategory(str, Enum):
    """Category of a contract provision."""

    NOTICE = "notice"
    FLOAT_OWNERSHIP = "float_ownership"
    CONCURRENT_DELAY = "concurrent_delay"
    PACING = "pacing"
    FORCE_MAJEURE = "force_majeure"
    TIME_EXTENSION = "time_extension"


@dataclass
class ContractProvision:
    """A standard contract provision for delay analysis.

    Represents a contractual requirement or standard practice that
    delay events must be checked against.
    """

    provision_id: str
    name: str
    description: str
    category: ProvisionCategory
    reference: str = ""
    threshold_days: float = 0.0
    details: str = ""


@dataclass
class ComplianceCheck:
    """Result of checking a fragment against a contract provision.

    Each check evaluates one provision for one delay fragment and
    produces a status, finding, and recommendation.
    """

    fragment_id: str
    fragment_name: str
    provision: ContractProvision
    status: ComplianceStatus = ComplianceStatus.INFO
    finding: str = ""
    recommendation: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class ContractComplianceChecker:
    """Check delay fragments against standard contract provisions.

    Evaluates each delay fragment and its TIA result against a set
    of contract provisions covering notice requirements, float
    ownership, pacing delays, and concurrent delay implications.

    Usage::

        checker = ContractComplianceChecker()
        checks = checker.check_fragment(fragment, tia_result)
        # or
        all_checks = checker.check_all(fragments, results)
    """

    DEFAULT_PROVISIONS: list[ContractProvision] = [
        ContractProvision(
            provision_id="PROV-001",
            name="Timely Notice of Delay",
            description=(
                "Contractor must provide written notice of delay-causing "
                "events within the contractually specified period."
            ),
            category=ProvisionCategory.NOTICE,
            reference="AIA A201-2017 Section 15.1.3; FIDIC Clause 20.1",
            threshold_days=7.0,
            details=(
                "Standard notice periods range from 5 to 21 days depending "
                "on the contract. AIA A201 requires 21 days; FIDIC requires "
                "28 days; many contracts specify 5-10 business days."
            ),
        ),
        ContractProvision(
            provision_id="PROV-002",
            name="Float Ownership -- Project Float",
            description=(
                "Total float is a shared project resource, not owned by "
                "any single party. Consumption of project float by one "
                "party may affect the other party's scheduling flexibility."
            ),
            category=ProvisionCategory.FLOAT_OWNERSHIP,
            reference="ConsensusDocs 200 Section 6.3; AACE RP 29R-03",
            threshold_days=0.0,
            details=(
                "Most standard contracts and court rulings treat float as "
                "a shared resource. The party that first consumes float "
                "may not be liable for delay, but the consumption should "
                "be documented."
            ),
        ),
        ContractProvision(
            provision_id="PROV-003",
            name="Concurrent Delay Analysis",
            description=(
                "When delays from multiple parties overlap, the concurrent "
                "delay doctrine may apply. Typically, neither party can "
                "recover damages for the concurrent period."
            ),
            category=ProvisionCategory.CONCURRENT_DELAY,
            reference="SCL Protocol Core Principle 10; Keating on Construction Contracts",
            threshold_days=0.0,
            details=(
                "Under the SCL Protocol, true concurrent delay exists when "
                "two or more delay events occur at the same time and both "
                "independently affect the critical path. The contractor "
                "may still be entitled to time but not compensation."
            ),
        ),
        ContractProvision(
            provision_id="PROV-004",
            name="Pacing Delay Detection",
            description=(
                "A pacing delay occurs when a party deliberately slows "
                "work because another delay has already consumed the float "
                "or pushed the completion date. Pacing delays should not "
                "be counted as independent delays."
            ),
            category=ProvisionCategory.PACING,
            reference="AACE RP 29R-03 Section 4.5",
            threshold_days=0.0,
            details=(
                "Pacing delays are identified when a non-critical activity "
                "is deliberately slowed to match a parallel critical delay. "
                "The key indicator is zero or near-zero delay impact with "
                "float consumption."
            ),
        ),
        ContractProvision(
            provision_id="PROV-005",
            name="Force Majeure Verification",
            description=(
                "Force majeure events must meet specific contractual "
                "criteria: the event must be beyond the control of both "
                "parties, unforeseeable, and unavoidable."
            ),
            category=ProvisionCategory.FORCE_MAJEURE,
            reference="AIA A201-2017 Section 8.3; FIDIC Clause 19",
            threshold_days=0.0,
            details=(
                "Common force majeure events include natural disasters, "
                "epidemics, war, government actions, and labor disputes. "
                "The claiming party must demonstrate that the event was "
                "the proximate cause of the delay."
            ),
        ),
        ContractProvision(
            provision_id="PROV-006",
            name="Time Extension Entitlement",
            description=(
                "Time extensions should be supported by a prospective "
                "Time Impact Analysis demonstrating the delay's effect "
                "on the project completion date."
            ),
            category=ProvisionCategory.TIME_EXTENSION,
            reference="AACE RP 52R-06; AIA A201-2017 Section 8.3.1",
            threshold_days=0.0,
            details=(
                "A valid time extension request requires: (1) a qualifying "
                "delay event, (2) timely notice, (3) a TIA showing impact "
                "on the critical path, and (4) no concurrent contractor "
                "delay negating the claim."
            ),
        ),
    ]

    def __init__(self, provisions: list[ContractProvision] | None = None) -> None:
        """Initialise with contract provisions.

        Args:
            provisions: Custom provisions to use. If None, uses the
                default set of standard provisions.
        """
        self.provisions = provisions or list(self.DEFAULT_PROVISIONS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_fragment(
        self,
        fragment: DelayFragment,
        tia_result: TIAResult,
    ) -> list[ComplianceCheck]:
        """Run all compliance checks for a single fragment.

        Args:
            fragment: The delay fragment.
            tia_result: The TIA result for this fragment.

        Returns:
            List of compliance check results.
        """
        checks: list[ComplianceCheck] = []

        checks.append(self._check_notice(fragment, tia_result))
        checks.append(self._check_float_ownership(fragment, tia_result))
        checks.append(self._check_pacing(fragment, tia_result))
        checks.append(self._check_concurrent(fragment, tia_result))

        if fragment.responsible_party == ResponsibleParty.FORCE_MAJEURE:
            checks.append(self._check_force_majeure(fragment, tia_result))

        checks.append(self._check_time_extension(fragment, tia_result))

        return checks

    def check_all(
        self,
        fragments: list[DelayFragment],
        results: list[TIAResult],
    ) -> list[ComplianceCheck]:
        """Run compliance checks for all fragments.

        Args:
            fragments: List of delay fragments.
            results: Corresponding TIA results (same order).

        Returns:
            Combined list of all compliance check results.
        """
        all_checks: list[ComplianceCheck] = []

        result_map = {r.fragment.fragment_id: r for r in results}

        for fragment in fragments:
            tia_result = result_map.get(fragment.fragment_id)
            if tia_result is None:
                logger.warning("No TIA result found for fragment %s", fragment.fragment_id)
                continue
            checks = self.check_fragment(fragment, tia_result)
            all_checks.extend(checks)

        return all_checks

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _get_provision(self, provision_id: str) -> ContractProvision:
        """Look up a provision by ID, falling back to defaults."""
        for p in self.provisions:
            if p.provision_id == provision_id:
                return p
        # Return first matching default
        for p in self.DEFAULT_PROVISIONS:
            if p.provision_id == provision_id:
                return p
        return ContractProvision(
            provision_id=provision_id,
            name="Unknown",
            description="",
            category=ProvisionCategory.NOTICE,
        )

    def _check_notice(self, fragment: DelayFragment, result: TIAResult) -> ComplianceCheck:
        """Check if timely notice requirements can be met.

        Standard construction contracts require notice within 5-21 days
        of a delay-causing event. This check flags fragments where the
        delay exceeds the notice threshold, indicating notice should
        have been given.

        Args:
            fragment: The delay fragment.
            result: The TIA result.

        Returns:
            A ComplianceCheck for the notice provision.
        """
        provision = self._get_provision("PROV-001")

        check = ComplianceCheck(
            fragment_id=fragment.fragment_id,
            fragment_name=fragment.name,
            provision=provision,
        )

        if result.delay_days <= 0:
            check.status = ComplianceStatus.INFO
            check.finding = (
                "No project delay caused. Notice requirements are "
                "less critical when no delay to completion occurs."
            )
            check.recommendation = "Document the event for the project record regardless."
        elif result.delay_days > 0:
            check.status = ComplianceStatus.WARNING
            check.finding = (
                f"Fragment causes {result.delay_days:.1f} days of project delay. "
                f"Written notice must be provided within {provision.threshold_days:.0f} "
                f"days of the delay event per contract requirements."
            )
            check.recommendation = (
                "Verify that written notice was provided within the contractual "
                "period. Late notice may waive time extension entitlement."
            )

        check.details = {
            "delay_days": result.delay_days,
            "notice_threshold_days": provision.threshold_days,
            "responsible_party": fragment.responsible_party.value,
        }

        return check

    def _check_float_ownership(self, fragment: DelayFragment, result: TIAResult) -> ComplianceCheck:
        """Analyze float consumption -- project float vs activity float.

        Checks whether the fragment consumes shared project float and
        whether that consumption affects other parties.

        Args:
            fragment: The delay fragment.
            result: The TIA result.

        Returns:
            A ComplianceCheck for the float ownership provision.
        """
        provision = self._get_provision("PROV-002")

        check = ComplianceCheck(
            fragment_id=fragment.fragment_id,
            fragment_name=fragment.name,
            provision=provision,
        )

        if result.critical_path_affected:
            check.status = ComplianceStatus.WARNING
            check.finding = (
                "Fragment is on the critical path. No float available -- "
                "any delay directly impacts the project completion date."
            )
            check.recommendation = (
                "This delay directly affects project completion. "
                "Float ownership is not at issue for critical path delays."
            )
        elif result.float_consumed_hours > 0:
            float_days = result.float_consumed_hours / 8.0
            check.status = ComplianceStatus.WARNING
            check.finding = (
                f"Fragment consumes approximately {float_days:.1f} days of "
                f"shared project float. While this does not currently delay "
                f"the project, it reduces scheduling flexibility for both parties."
            )
            check.recommendation = (
                "Document float consumption. Under most contracts, float is "
                "a shared resource. Future delays on this path may now become "
                "critical."
            )
        else:
            check.status = ComplianceStatus.PASS
            check.finding = "Fragment does not significantly consume project float."
            check.recommendation = "No action required."

        check.details = {
            "critical_path_affected": result.critical_path_affected,
            "float_consumed_hours": result.float_consumed_hours,
            "delay_days": result.delay_days,
        }

        return check

    def _check_pacing(self, fragment: DelayFragment, result: TIAResult) -> ComplianceCheck:
        """Detect if the delay is actually a pacing delay.

        A pacing delay occurs when an activity is deliberately slowed
        because another delay has already consumed available float or
        pushed the critical path. The key indicator is: the fragment
        causes zero or near-zero project delay but consumes float.

        Args:
            fragment: The delay fragment.
            result: The TIA result.

        Returns:
            A ComplianceCheck for the pacing provision.
        """
        provision = self._get_provision("PROV-004")

        check = ComplianceCheck(
            fragment_id=fragment.fragment_id,
            fragment_name=fragment.name,
            provision=provision,
        )

        total_frag_hours = sum(a.duration_hours for a in fragment.activities)
        total_frag_days = total_frag_hours / 8.0

        is_pacing = (
            total_frag_days > 0
            and result.delay_days <= 0
            and result.float_consumed_hours > 0
            and not result.critical_path_affected
        )

        if is_pacing:
            check.status = ComplianceStatus.WARNING
            check.finding = (
                f"Possible pacing delay detected. Fragment has "
                f"{total_frag_days:.1f} days of activity duration but causes "
                f"no project delay. Float consumed: "
                f"{result.float_consumed_hours / 8.0:.1f} days. This may "
                f"indicate the work was deliberately paced to match a "
                f"parallel critical delay."
            )
            check.recommendation = (
                "Investigate whether this delay is a genuine independent "
                "delay or a pacing response to another critical delay. "
                "Pacing delays should not be counted as independent delays."
            )
        else:
            check.status = ComplianceStatus.PASS
            check.finding = "No pacing delay indicators detected."
            check.recommendation = "No action required."

        check.details = {
            "fragment_duration_days": total_frag_days,
            "delay_days": result.delay_days,
            "float_consumed_hours": result.float_consumed_hours,
            "critical_path_affected": result.critical_path_affected,
            "is_pacing": is_pacing,
        }

        return check

    def _check_concurrent(self, fragment: DelayFragment, result: TIAResult) -> ComplianceCheck:
        """Check concurrent delay implications.

        If the fragment has been marked as concurrent with other
        fragments, the concurrent delay doctrine applies.

        Args:
            fragment: The delay fragment.
            result: The TIA result.

        Returns:
            A ComplianceCheck for the concurrent delay provision.
        """
        provision = self._get_provision("PROV-003")

        check = ComplianceCheck(
            fragment_id=fragment.fragment_id,
            fragment_name=fragment.name,
            provision=provision,
        )

        if result.concurrent_with:
            check.status = ComplianceStatus.WARNING
            concurrent_ids = ", ".join(result.concurrent_with)
            check.finding = (
                f"Fragment is concurrent with: {concurrent_ids}. "
                f"Under the concurrent delay doctrine, neither party "
                f"can recover delay damages for the overlapping period."
            )
            check.recommendation = (
                "Apply the dominant cause test or apportionment method "
                "per the contract terms. Under the SCL Protocol, the "
                "contractor may still be entitled to a time extension "
                "but not prolongation costs."
            )
        else:
            check.status = ComplianceStatus.PASS
            check.finding = "No concurrent delays detected for this fragment."
            check.recommendation = "No action required."

        check.details = {
            "concurrent_with": result.concurrent_with,
            "delay_type": result.delay_type.value,
        }

        return check

    def _check_force_majeure(self, fragment: DelayFragment, result: TIAResult) -> ComplianceCheck:
        """Check force majeure classification requirements.

        Force majeure events must meet specific contractual criteria:
        beyond control, unforeseeable, and unavoidable.

        Args:
            fragment: The delay fragment.
            result: The TIA result.

        Returns:
            A ComplianceCheck for the force majeure provision.
        """
        provision = self._get_provision("PROV-005")

        check = ComplianceCheck(
            fragment_id=fragment.fragment_id,
            fragment_name=fragment.name,
            provision=provision,
        )

        check.status = ComplianceStatus.WARNING
        check.finding = (
            "Fragment is classified as force majeure. Verify that the "
            "event meets all contractual criteria: (1) beyond control "
            "of both parties, (2) could not have been foreseen, "
            "(3) effects could not have been avoided or overcome."
        )
        check.recommendation = (
            "Gather supporting documentation including government orders, "
            "weather records, or other evidence. The claiming party bears "
            "the burden of proof for force majeure classification."
        )

        check.details = {
            "responsible_party": fragment.responsible_party.value,
            "delay_days": result.delay_days,
        }

        return check

    def _check_time_extension(self, fragment: DelayFragment, result: TIAResult) -> ComplianceCheck:
        """Evaluate time extension entitlement.

        A valid time extension requires: qualifying event, timely notice,
        TIA showing CP impact, and no concurrent contractor delay.

        Args:
            fragment: The delay fragment.
            result: The TIA result.

        Returns:
            A ComplianceCheck for the time extension provision.
        """
        provision = self._get_provision("PROV-006")

        check = ComplianceCheck(
            fragment_id=fragment.fragment_id,
            fragment_name=fragment.name,
            provision=provision,
        )

        # Determine entitlement
        qualifies = (
            result.delay_days > 0
            and result.critical_path_affected
            and fragment.responsible_party
            in (
                ResponsibleParty.OWNER,
                ResponsibleParty.FORCE_MAJEURE,
                ResponsibleParty.THIRD_PARTY,
            )
        )

        has_concurrent = bool(result.concurrent_with)

        if qualifies and not has_concurrent:
            check.status = ComplianceStatus.PASS
            check.finding = (
                f"Fragment qualifies for a time extension of "
                f"{result.delay_days:.1f} days. The delay is caused by "
                f"{fragment.responsible_party.value}, affects the critical "
                f"path, and has no concurrent contractor delays."
            )
            check.recommendation = (
                "Prepare a formal time extension request with this TIA as supporting documentation."
            )
        elif qualifies and has_concurrent:
            check.status = ComplianceStatus.WARNING
            check.finding = (
                f"Fragment may qualify for a time extension of "
                f"{result.delay_days:.1f} days, but concurrent delays "
                f"exist. The time extension amount may be reduced."
            )
            check.recommendation = (
                "Apply concurrent delay apportionment per contract terms. "
                "The contractor may still be entitled to time but reduced "
                "or no compensation."
            )
        elif result.delay_days > 0 and not result.critical_path_affected:
            check.status = ComplianceStatus.INFO
            check.finding = (
                "Fragment does not affect the critical path. Time extension "
                "is generally not warranted for non-critical delays."
            )
            check.recommendation = (
                "Document the event. If future delays make this path "
                "critical, a time extension may then be warranted."
            )
        elif fragment.responsible_party == ResponsibleParty.CONTRACTOR:
            check.status = ComplianceStatus.FAIL
            check.finding = (
                "Contractor-caused delay. No time extension entitlement. "
                "Liquidated damages may apply."
            )
            check.recommendation = (
                "Evaluate mitigation options. The contractor should prepare a recovery schedule."
            )
        else:
            check.status = ComplianceStatus.INFO
            check.finding = "No project delay caused by this fragment."
            check.recommendation = "No action required."

        check.details = {
            "qualifies_for_extension": qualifies,
            "delay_days": result.delay_days,
            "critical_path_affected": result.critical_path_affected,
            "responsible_party": fragment.responsible_party.value,
            "has_concurrent": has_concurrent,
        }

        return check
