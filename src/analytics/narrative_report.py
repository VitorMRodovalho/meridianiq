"""Narrative report generator — structured text from schedule analysis.

Generates professional schedule narrative text for:
- Monthly status reports
- Claims documentation (delay analysis narrative)
- Executive summaries
- Scorecard commentary

Reference: AACE RP 29R-03 — Forensic Schedule Analysis (narrative requirements);
           SCL Protocol — Delay Analysis presentation standards.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class NarrativeSection:
    """A section of a narrative report."""

    title: str
    content: str
    severity: str = "info"  # info, warning, critical


@dataclass
class NarrativeReport:
    """Complete narrative report with sections."""

    title: str
    project_name: str
    data_date: str
    generated_at: str = ""
    sections: list[NarrativeSection] = field(default_factory=list)
    executive_summary: str = ""


def generate_schedule_narrative(
    project_name: str,
    data_date: str,
    summary: dict,
    scorecard: dict | None = None,
    comparison: dict | None = None,
    trends: dict | None = None,
) -> NarrativeReport:
    """Generate a narrative schedule status report.

    Combines schedule summary metrics, scorecard results, comparison
    findings, and trend data into a structured narrative.

    Args:
        project_name: Schedule project name.
        data_date: Data date of the schedule.
        summary: Schedule-view summary dict (activity count, CP, float, etc.).
        scorecard: Optional scorecard result dict.
        comparison: Optional comparison result dict.
        trends: Optional trend analysis result dict.

    Returns:
        NarrativeReport with sections and executive summary.

    Reference: AACE RP 29R-03 — Forensic Schedule Analysis.
    """
    report = NarrativeReport(
        title=f"Schedule Status Report — {project_name}",
        project_name=project_name,
        data_date=data_date,
        generated_at=datetime.now().isoformat(),
    )

    # ── Schedule Overview ─────────────────────────────────
    total = summary.get("total_activities", 0)
    complete_pct = summary.get("complete_pct", 0)
    critical = summary.get("critical_count", 0)
    near_crit = summary.get("near_critical_count", 0)
    neg_float = summary.get("negative_float_count", 0)
    avg_float = summary.get("avg_float_days", 0)
    constraints = summary.get("constraint_count", 0)
    milestones = summary.get("milestones_count", 0)

    overview = (
        f"The schedule contains {total:,} activities with an overall completion "
        f"of {complete_pct:.1f}%. The critical path comprises {critical:,} activities "
        f"({critical / total * 100:.1f}% of total). "
    )

    if neg_float > 0:
        overview += (
            f"There are {neg_float:,} activities with negative total float, "
            f"indicating schedule compression or constraint conflicts. "
        )

    if near_crit > 0:
        overview += (
            f"Additionally, {near_crit:,} activities are near-critical "
            f"(total float between 1 and 10 days). "
        )

    overview += (
        f"Average total float for non-complete activities is {avg_float:.0f} days. "
        f"The schedule uses {constraints:,} date constraints "
        f"and includes {milestones:,} milestones."
    )

    report.sections.append(
        NarrativeSection(
            title="Schedule Overview",
            content=overview,
            severity="info",
        )
    )

    # ── Float Analysis ────────────────────────────────────
    if neg_float > 0 or avg_float < 10:
        severity = "critical" if neg_float > total * 0.1 else "warning"
        float_text = (
            f"Float analysis indicates {'significant ' if severity == 'critical' else ''}"
            f"schedule pressure. {neg_float:,} activities ({neg_float / total * 100:.1f}%) "
            f"have negative float, meaning they are currently projected to finish late. "
        )
        if avg_float < 0:
            float_text += (
                "The average float is negative, suggesting the project finish date is at risk. "
            )
        elif avg_float < 10:
            float_text += "Low average float leaves minimal buffer for unforeseen delays. "

        report.sections.append(
            NarrativeSection(
                title="Float Analysis",
                content=float_text,
                severity=severity,
            )
        )

    # ── Scorecard Assessment ──────────────────────────────
    if scorecard:
        score = scorecard.get("overall_score", 0)
        grade = scorecard.get("overall_grade", "?")
        dims = scorecard.get("dimensions", [])

        card_text = (
            f"The schedule quality scorecard rates this submission as "
            f"Grade {grade} ({score:.0f}/100). "
        )

        for dim in dims:
            dname = dim.get("name", "")
            dscore = dim.get("score", 0)
            dgrade = dim.get("grade", "")
            if dscore < 60:
                card_text += f"The {dname} dimension scored {dscore:.0f} ({dgrade}), indicating deficiencies. "

        severity = "critical" if score < 50 else "warning" if score < 70 else "info"
        report.sections.append(
            NarrativeSection(
                title="Quality Assessment",
                content=card_text,
                severity=severity,
            )
        )

    # ── Comparison / Changes ──────────────────────────────
    if comparison:
        comp_summary = comparison.get("summary", {})
        added = comp_summary.get("activities_added", 0)
        deleted = comp_summary.get("activities_deleted", 0)
        modified = comp_summary.get("activities_modified", 0)
        changed_pct = comp_summary.get("changed_percentage", 0)

        comp_text = (
            f"Comparing to the previous submission: {added:,} activities were added, "
            f"{deleted:,} removed, and {modified:,} modified "
            f"({changed_pct:.1f}% overall change). "
        )

        manip_score = comparison.get("manipulation_score", 0)
        if manip_score > 50:
            comp_text += (
                f"The manipulation score of {manip_score:.0f} exceeds the threshold, "
                f"warranting further review of schedule changes. "
            )

        severity = "warning" if changed_pct > 30 else "info"
        report.sections.append(
            NarrativeSection(
                title="Schedule Changes",
                content=comp_text,
                severity=severity,
            )
        )

    # ── Trend Insights ────────────────────────────────────
    if trends:
        insights = trends.get("insights", [])
        if insights:
            trend_text = "Trend analysis across sequential updates reveals: "
            for insight in insights:
                trend_text += f"{insight}. "

            report.sections.append(
                NarrativeSection(
                    title="Schedule Trends",
                    content=trend_text,
                    severity="warning" if len(insights) > 3 else "info",
                )
            )

    # ── Executive Summary ─────────────────────────────────
    exec_parts = [f"Schedule for {project_name} (data date {data_date}) "]
    exec_parts.append(f"is {complete_pct:.0f}% complete with {total:,} activities. ")

    if scorecard:
        exec_parts.append(f"Quality grade: {scorecard.get('overall_grade', '?')}. ")

    criticals = [s for s in report.sections if s.severity == "critical"]
    warnings = [s for s in report.sections if s.severity == "warning"]
    if criticals:
        exec_parts.append(f"{len(criticals)} critical issue(s) require immediate attention. ")
    if warnings:
        exec_parts.append(f"{len(warnings)} warning(s) noted. ")
    if not criticals and not warnings:
        exec_parts.append("No critical issues identified. ")

    report.executive_summary = "".join(exec_parts)

    return report
