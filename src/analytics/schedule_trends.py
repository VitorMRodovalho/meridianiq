"""Schedule trend analysis — track evolution across sequential schedule updates.

Computes period-over-period trends for a series of schedule submissions:
- Activity count growth (scope creep indicator)
- Float erosion (schedule compression)
- Completion progress (earned schedule)
- Critical path length and count
- Relationship density
- Schedule quality score

Reference: AACE RP 29R-03 — Forensic Schedule Analysis;
           DCMA 14-Point Assessment (trending checks over time).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.parser.models import ParsedSchedule


@dataclass
class TrendPoint:
    """A single data point in a schedule trend series."""

    project_id: str
    project_name: str
    data_date: str
    update_number: int | None = None

    # Scope
    activity_count: int = 0
    relationship_count: int = 0
    wbs_count: int = 0
    milestone_count: int = 0

    # Progress
    complete_count: int = 0
    active_count: int = 0
    not_started_count: int = 0
    complete_pct: float = 0.0

    # Float
    avg_total_float: float = 0.0
    negative_float_count: int = 0
    zero_float_count: int = 0
    critical_count: int = 0
    near_critical_count: int = 0

    # Logic
    logic_density: float = 0.0  # relationships / activities
    constraint_count: int = 0
    loe_count: int = 0

    # Duration
    project_duration_days: int = 0

    # Quality (optional — computed from scorecard)
    quality_score: float | None = None
    quality_grade: str = ""


@dataclass
class TrendAnalysis:
    """Complete trend analysis across a series of schedule updates."""

    series_name: str
    points: list[TrendPoint] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)


def compute_trend_point(
    schedule: ParsedSchedule,
    project_id: str,
    update_number: int | None = None,
) -> TrendPoint:
    """Compute trend metrics for a single schedule.

    Args:
        schedule: Parsed schedule data.
        project_id: Project identifier.
        update_number: Optional update sequence number.

    Returns:
        TrendPoint with all computed metrics.
    """
    proj = schedule.projects[0] if schedule.projects else None
    data_date = ""
    project_name = ""
    project_duration = 0

    if proj:
        project_name = proj.proj_short_name or ""
        dd = proj.last_recalc_date or proj.sum_data_date
        if dd:
            data_date = dd.strftime("%Y-%m-%d")
        if proj.plan_start_date and proj.scd_end_date:
            delta = proj.scd_end_date - proj.plan_start_date
            project_duration = delta.days

    acts = schedule.activities
    total = len(acts)

    # Status counts
    complete = sum(1 for a in acts if a.status_code in ("TK_Complete",))
    active = sum(1 for a in acts if a.status_code in ("TK_Active",))
    not_started = total - complete - active

    # Float analysis
    floats = []
    neg_float = 0
    zero_float = 0
    critical = 0
    near_critical = 0
    constraint_count = 0
    loe_count = 0
    milestone_count = 0

    for a in acts:
        # Float (convert hours to days, 8h/day)
        tf_hrs = a.total_float_hr_cnt or 0.0
        tf_days = tf_hrs / 8.0
        floats.append(tf_days)

        if tf_days < 0:
            neg_float += 1
        if tf_days == 0:
            zero_float += 1
        if tf_days <= 0 and a.status_code != "TK_Complete":
            critical += 1
        if 0 < tf_days <= 10 and a.status_code != "TK_Complete":
            near_critical += 1

        # Constraints
        if a.cstr_type and a.cstr_type not in ("", "CS_MEO"):
            constraint_count += 1

        # Types
        if a.task_type in ("TT_LOE",):
            loe_count += 1
        if a.task_type in ("TT_Mile", "TT_FinMile", "TT_WBS"):
            milestone_count += 1

    avg_float = sum(floats) / len(floats) if floats else 0.0
    rels = len(schedule.relationships)
    logic_density = rels / total if total else 0.0

    return TrendPoint(
        project_id=project_id,
        project_name=project_name,
        data_date=data_date,
        update_number=update_number,
        activity_count=total,
        relationship_count=rels,
        wbs_count=len(schedule.wbs_nodes),
        milestone_count=milestone_count,
        complete_count=complete,
        active_count=active,
        not_started_count=not_started,
        complete_pct=round(complete / total * 100, 1) if total else 0.0,
        avg_total_float=round(avg_float, 1),
        negative_float_count=neg_float,
        zero_float_count=zero_float,
        critical_count=critical,
        near_critical_count=near_critical,
        logic_density=round(logic_density, 2),
        constraint_count=constraint_count,
        loe_count=loe_count,
        project_duration_days=project_duration,
    )


def analyze_trends(points: list[TrendPoint]) -> TrendAnalysis:
    """Analyze trends across a series of schedule updates.

    Args:
        points: List of TrendPoints sorted by data_date.

    Returns:
        TrendAnalysis with insights.

    Reference: AACE RP 29R-03 — Forensic Schedule Analysis.
    """
    if not points:
        return TrendAnalysis(series_name="", points=[], insights=[])

    sorted_points = sorted(points, key=lambda p: p.data_date)
    series_name = sorted_points[0].project_name.split(" UP")[0].strip() if sorted_points else ""

    insights: list[str] = []

    if len(sorted_points) >= 2:
        first = sorted_points[0]
        last = sorted_points[-1]

        # Scope creep
        act_growth = last.activity_count - first.activity_count
        act_growth_pct = (act_growth / first.activity_count * 100) if first.activity_count else 0
        if act_growth_pct > 10:
            insights.append(
                f"Scope growth: {act_growth:+d} activities ({act_growth_pct:+.0f}%) "
                f"from {first.data_date} to {last.data_date}"
            )

        # Float erosion
        float_delta = last.avg_total_float - first.avg_total_float
        if float_delta < -5:
            insights.append(
                f"Float erosion: average TF dropped {float_delta:.0f} days "
                f"({first.avg_total_float:.0f}d → {last.avg_total_float:.0f}d)"
            )

        # Completion progress
        complete_delta = last.complete_pct - first.complete_pct
        if complete_delta > 0:
            insights.append(
                f"Progress: completion advanced {complete_delta:+.1f}% "
                f"({first.complete_pct:.1f}% → {last.complete_pct:.1f}%)"
            )

        # Critical path growth
        cp_delta = last.critical_count - first.critical_count
        if cp_delta > 20:
            insights.append(
                f"Critical path expanded: {cp_delta:+d} activities "
                f"({first.critical_count} → {last.critical_count})"
            )

        # Logic density change
        ld_delta = last.logic_density - first.logic_density
        if abs(ld_delta) > 0.1:
            insights.append(
                f"Logic density {'improved' if ld_delta > 0 else 'degraded'}: "
                f"{first.logic_density:.2f} → {last.logic_density:.2f}"
            )

        # Negative float trend
        if last.negative_float_count > first.negative_float_count + 10:
            insights.append(
                f"Negative float growing: {first.negative_float_count} → "
                f"{last.negative_float_count} activities"
            )

    return TrendAnalysis(
        series_name=series_name,
        points=sorted_points,
        insights=insights,
    )
