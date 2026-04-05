# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Half-Step (Bifurcation) analysis — separating progress from revisions.

Implements the bifurcation technique per AACE RP 29R-03 MIP 3.4
(Contemporaneous Split Analysis).  Given two consecutive schedule updates
(Schedule A and Schedule B), creates an intermediate "half-step" schedule
that isolates the effect of actual progress from the effect of logic/plan
revisions.

The half-step schedule (A-1/2) is built by cloning Schedule A and applying
**only** progress-related fields from Schedule B (actuals, remaining
duration proportional to progress, status).  Logic, relationships,
calendars, constraints, and scope changes are deliberately excluded.

References:
    - AACE RP 29R-03 Forensic Schedule Analysis, MIP 3.4
    - Ron Winter PS-1264 "Creating Half-Step Schedules Using P6 Baseline Update"
    - Ron Winter PS-1197 "Introducing the Zero-Step Schedule"
    - SCL Delay and Disruption Protocol, 2nd ed., Time Slice Window Analysis
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.cpm import CPMCalculator
from src.parser.models import ParsedSchedule, Task

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Change classification
# ---------------------------------------------------------------------------


@dataclass
class ChangeClassification:
    """Classification of a single activity change between two schedules."""

    task_id: str
    task_code: str
    task_name: str
    category: str  # "progress" or "revision"
    field_name: str  # which field changed
    old_value: str = ""
    new_value: str = ""
    confidence: str = "high"  # "high", "medium", "low"
    rationale: str = ""


@dataclass
class ClassificationResult:
    """Result of classifying all changes between two schedules."""

    progress_changes: list[ChangeClassification] = field(default_factory=list)
    revision_changes: list[ChangeClassification] = field(default_factory=list)
    ambiguous_changes: list[ChangeClassification] = field(default_factory=list)
    activities_added: list[str] = field(default_factory=list)
    activities_deleted: list[str] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Half-Step result
# ---------------------------------------------------------------------------


@dataclass
class HalfStepResult:
    """Result of a half-step (bifurcation) analysis between two schedules.

    Per AACE RP 29R-03 MIP 3.4, the total delay for a window is split into:
    - progress_effect: delay caused by actual work performance
    - revision_effect: delay caused by schedule logic/plan changes

    The invariant ``progress_effect + revision_effect == total_delay``
    must hold (within floating-point tolerance).
    """

    # Completion dates
    completion_a: float = 0.0  # Schedule A project duration (days)
    completion_half_step: float = 0.0  # Half-step schedule project duration
    completion_b: float = 0.0  # Schedule B project duration

    # Effects (in working days)
    progress_effect: float = 0.0  # completion_half_step - completion_a
    revision_effect: float = 0.0  # completion_b - completion_half_step
    total_delay: float = 0.0  # completion_b - completion_a

    # Critical path info
    critical_path_a: list[str] = field(default_factory=list)
    critical_path_half_step: list[str] = field(default_factory=list)
    critical_path_b: list[str] = field(default_factory=list)

    # Change classification
    classification: ClassificationResult | None = None

    # Metadata
    activities_updated: int = 0  # activities with progress transferred
    invariant_check: bool = False  # True if progress + revision == total

    summary: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------


def classify_changes(
    schedule_a: ParsedSchedule,
    schedule_b: ParsedSchedule,
) -> ClassificationResult:
    """Classify every change between two schedules as progress or revision.

    Progress fields: status_code, act_start_date, act_end_date,
    remain_drtn_hr_cnt (proportional to phys_complete_pct), phys_complete_pct.

    Revision fields: relationships added/deleted/modified, activities
    added/deleted, calendar changes, constraint changes, duration changes
    on not-started activities.

    Args:
        schedule_a: The earlier (baseline) schedule.
        schedule_b: The later (update) schedule.

    Returns:
        A ``ClassificationResult`` with all changes categorised.
    """
    result = ClassificationResult()

    # Build lookup maps
    a_by_id: dict[str, Task] = {t.task_id: t for t in schedule_a.activities}
    b_by_id: dict[str, Task] = {t.task_id: t for t in schedule_b.activities}

    # Match by task_id, then fallback to task_code
    a_by_code: dict[str, Task] = {t.task_code: t for t in schedule_a.activities if t.task_code}
    b_by_code: dict[str, Task] = {t.task_code: t for t in schedule_b.activities if t.task_code}

    matched_a: set[str] = set()
    matched_b: set[str] = set()
    pairs: list[tuple[Task, Task]] = []

    # Tier 1: match by task_id
    for tid in set(a_by_id.keys()) & set(b_by_id.keys()):
        pairs.append((a_by_id[tid], b_by_id[tid]))
        matched_a.add(tid)
        matched_b.add(tid)

    # Tier 2: match remaining by task_code
    for code in set(a_by_code.keys()) & set(b_by_code.keys()):
        ta = a_by_code[code]
        tb = b_by_code[code]
        if ta.task_id not in matched_a and tb.task_id not in matched_b:
            pairs.append((ta, tb))
            matched_a.add(ta.task_id)
            matched_b.add(tb.task_id)

    # Added/deleted
    for t in schedule_b.activities:
        if t.task_id not in matched_b:
            result.activities_added.append(t.task_code or t.task_id)
    for t in schedule_a.activities:
        if t.task_id not in matched_a:
            result.activities_deleted.append(t.task_code or t.task_id)

    # Classify per-activity field changes
    for task_a, task_b in pairs:
        tid = task_a.task_id
        code = task_b.task_code or task_b.task_id
        name = task_b.task_name or task_a.task_name

        _classify_activity_changes(task_a, task_b, tid, code, name, result)

    # Relationship changes are always revisions
    a_rels = {
        (r.task_id, r.pred_task_id, r.pred_type, r.lag_hr_cnt) for r in schedule_a.relationships
    }
    b_rels = {
        (r.task_id, r.pred_task_id, r.pred_type, r.lag_hr_cnt) for r in schedule_b.relationships
    }
    for rel in b_rels - a_rels:
        result.revision_changes.append(
            ChangeClassification(
                task_id=rel[0],
                task_code=rel[0],
                task_name="",
                category="revision",
                field_name="relationship_added",
                new_value=f"{rel[2]} lag={rel[3]}",
                rationale="New or modified relationship is a schedule revision",
            )
        )
    for rel in a_rels - b_rels:
        result.revision_changes.append(
            ChangeClassification(
                task_id=rel[0],
                task_code=rel[0],
                task_name="",
                category="revision",
                field_name="relationship_deleted",
                old_value=f"{rel[2]} lag={rel[3]}",
                rationale="Removed relationship is a schedule revision",
            )
        )

    # Summary
    result.summary = {
        "progress_changes": len(result.progress_changes),
        "revision_changes": len(result.revision_changes),
        "ambiguous_changes": len(result.ambiguous_changes),
        "activities_added": len(result.activities_added),
        "activities_deleted": len(result.activities_deleted),
        "matched_pairs": len(pairs),
    }

    return result


def _classify_activity_changes(
    task_a: Task,
    task_b: Task,
    tid: str,
    code: str,
    name: str,
    result: ClassificationResult,
) -> None:
    """Classify field-level changes for a single matched activity pair."""
    # Status change → progress
    if task_a.status_code != task_b.status_code:
        result.progress_changes.append(
            ChangeClassification(
                task_id=tid,
                task_code=code,
                task_name=name,
                category="progress",
                field_name="status_code",
                old_value=task_a.status_code,
                new_value=task_b.status_code,
                rationale="Status change reflects actual work progress",
            )
        )

    # Actual start date → progress
    if task_a.act_start_date != task_b.act_start_date:
        result.progress_changes.append(
            ChangeClassification(
                task_id=tid,
                task_code=code,
                task_name=name,
                category="progress",
                field_name="act_start_date",
                old_value=str(task_a.act_start_date or ""),
                new_value=str(task_b.act_start_date or ""),
                rationale="Actual start date records real work commencement",
            )
        )

    # Actual end date → progress
    if task_a.act_end_date != task_b.act_end_date:
        result.progress_changes.append(
            ChangeClassification(
                task_id=tid,
                task_code=code,
                task_name=name,
                category="progress",
                field_name="act_end_date",
                old_value=str(task_a.act_end_date or ""),
                new_value=str(task_b.act_end_date or ""),
                rationale="Actual end date records real work completion",
            )
        )

    # Physical percent complete → progress
    if abs(task_a.phys_complete_pct - task_b.phys_complete_pct) > 0.01:
        result.progress_changes.append(
            ChangeClassification(
                task_id=tid,
                task_code=code,
                task_name=name,
                category="progress",
                field_name="phys_complete_pct",
                old_value=str(task_a.phys_complete_pct),
                new_value=str(task_b.phys_complete_pct),
                rationale="Physical percent complete reflects measured progress",
            )
        )

    # Remaining duration — needs heuristic
    if abs(task_a.remain_drtn_hr_cnt - task_b.remain_drtn_hr_cnt) > 0.01:
        _classify_remaining_duration(task_a, task_b, tid, code, name, result)

    # Constraint changes → revision
    if task_a.cstr_type != task_b.cstr_type or task_a.cstr_date != task_b.cstr_date:
        result.revision_changes.append(
            ChangeClassification(
                task_id=tid,
                task_code=code,
                task_name=name,
                category="revision",
                field_name="constraint",
                old_value=f"{task_a.cstr_type} {task_a.cstr_date}",
                new_value=f"{task_b.cstr_type} {task_b.cstr_date}",
                rationale="Constraint changes are plan revisions, not progress",
            )
        )

    # Calendar change → revision
    if task_a.clndr_id != task_b.clndr_id:
        result.revision_changes.append(
            ChangeClassification(
                task_id=tid,
                task_code=code,
                task_name=name,
                category="revision",
                field_name="calendar",
                old_value=task_a.clndr_id,
                new_value=task_b.clndr_id,
                rationale="Calendar reassignment is a plan revision",
            )
        )

    # Task type change → revision
    if task_a.task_type != task_b.task_type:
        result.revision_changes.append(
            ChangeClassification(
                task_id=tid,
                task_code=code,
                task_name=name,
                category="revision",
                field_name="task_type",
                old_value=task_a.task_type,
                new_value=task_b.task_type,
                rationale="Activity type change is a plan revision",
            )
        )

    # Target duration on not-started → revision
    if (
        task_b.status_code.lower() == "tk_notstart"
        and task_a.status_code.lower() == "tk_notstart"
        and abs(task_a.target_drtn_hr_cnt - task_b.target_drtn_hr_cnt) > 0.01
    ):
        result.revision_changes.append(
            ChangeClassification(
                task_id=tid,
                task_code=code,
                task_name=name,
                category="revision",
                field_name="target_duration",
                old_value=str(task_a.target_drtn_hr_cnt),
                new_value=str(task_b.target_drtn_hr_cnt),
                rationale="Duration change on not-started activity is a plan revision",
            )
        )


def _classify_remaining_duration(
    task_a: Task,
    task_b: Task,
    tid: str,
    code: str,
    name: str,
    result: ClassificationResult,
) -> None:
    """Classify a remaining duration change as progress, revision, or ambiguous.

    Heuristics per Ron Winter PS-1264:
    - If activity went from Not Started to Active → progress
    - If activity is Active and RD decreased proportionally to progress → progress
    - If activity is still Not Started and RD changed → revision
    - Otherwise → ambiguous (flag for analyst review)
    """
    old_rd = task_a.remain_drtn_hr_cnt
    new_rd = task_b.remain_drtn_hr_cnt

    base_cls = ChangeClassification(
        task_id=tid,
        task_code=code,
        task_name=name,
        category="progress",
        field_name="remain_drtn_hr_cnt",
        old_value=str(old_rd),
        new_value=str(new_rd),
    )

    a_status = task_a.status_code.lower()
    b_status = task_b.status_code.lower()

    # Not Started → Active: RD change is progress
    if a_status == "tk_notstart" and b_status == "tk_active":
        base_cls.category = "progress"
        base_cls.confidence = "high"
        base_cls.rationale = "Activity started — remaining duration change reflects actual progress"
        result.progress_changes.append(base_cls)
        return

    # Both Not Started: RD change is revision
    if a_status == "tk_notstart" and b_status == "tk_notstart":
        base_cls.category = "revision"
        base_cls.confidence = "high"
        base_cls.rationale = "Remaining duration changed on not-started activity — plan revision"
        result.revision_changes.append(base_cls)
        return

    # Active → Active: check proportionality to progress
    if a_status == "tk_active" and b_status == "tk_active":
        progress_delta = task_b.phys_complete_pct - task_a.phys_complete_pct
        rd_delta = old_rd - new_rd  # positive means RD decreased

        if progress_delta > 0.01 and rd_delta > 0:
            # Progress increased and RD decreased — likely progress
            # Check proportionality: expected RD = original * (1 - progress)
            target = task_a.target_drtn_hr_cnt
            if target > 0:
                expected_rd = target * (1.0 - task_b.phys_complete_pct / 100.0)
                tolerance = target * 0.15  # 15% tolerance
                if abs(new_rd - expected_rd) <= tolerance:
                    base_cls.category = "progress"
                    base_cls.confidence = "high"
                    base_cls.rationale = (
                        f"RD change proportional to progress "
                        f"({task_a.phys_complete_pct}% → {task_b.phys_complete_pct}%)"
                    )
                    result.progress_changes.append(base_cls)
                    return

            # RD decreased with progress but not proportional — ambiguous
            base_cls.category = "progress"
            base_cls.confidence = "medium"
            base_cls.rationale = (
                "RD decreased with progress but not strictly proportional — "
                "treated as progress (conservative)"
            )
            result.ambiguous_changes.append(base_cls)
            return

        if progress_delta <= 0.01 and abs(rd_delta) > 0.01:
            # No progress but RD changed — revision
            base_cls.category = "revision"
            base_cls.confidence = "high"
            base_cls.rationale = (
                "Remaining duration changed without corresponding progress — "
                "planner revised the estimate"
            )
            result.revision_changes.append(base_cls)
            return

    # Completed activity — RD should be 0; any change is progress
    if b_status == "tk_complete":
        base_cls.category = "progress"
        base_cls.confidence = "high"
        base_cls.rationale = "Activity completed — RD zeroed out as part of progress"
        result.progress_changes.append(base_cls)
        return

    # Fallback: ambiguous
    base_cls.category = "progress"
    base_cls.confidence = "low"
    base_cls.rationale = (
        "Cannot determine if RD change is progress or revision — "
        "defaulting to progress (conservative for half-step)"
    )
    result.ambiguous_changes.append(base_cls)


def create_half_step_schedule(
    schedule_a: ParsedSchedule,
    schedule_b: ParsedSchedule,
) -> tuple[ParsedSchedule, int]:
    """Create a half-step schedule by applying only progress from B to A.

    Per AACE RP 29R-03 MIP 3.4, the half-step schedule represents what
    the project completion date would have been if only actual progress
    occurred and no logic/plan revisions were made.

    The half-step schedule is a deep copy of Schedule A with the following
    fields transferred from matching activities in Schedule B:
    - status_code
    - act_start_date
    - act_end_date
    - phys_complete_pct
    - remain_drtn_hr_cnt (only if classified as progress)
    - act_work_qty / remain_work_qty

    Fields NOT transferred (kept from Schedule A):
    - relationships (TASKPRED)
    - calendars
    - constraints
    - task_type, duration_type
    - activities added in B (not included)
    - activities deleted from A (kept)

    Args:
        schedule_a: The earlier (baseline) schedule.
        schedule_b: The later (update) schedule.

    Returns:
        Tuple of (half-step ParsedSchedule, count of activities updated).
    """
    # Deep copy Schedule A as base
    half_step = copy.deepcopy(schedule_a)

    # Build lookup for Schedule B activities
    b_by_id: dict[str, Task] = {t.task_id: t for t in schedule_b.activities}
    b_by_code: dict[str, Task] = {t.task_code: t for t in schedule_b.activities if t.task_code}

    # Advance data date to Schedule B's data date
    if half_step.projects and schedule_b.projects:
        b_proj = schedule_b.projects[0]
        half_step.projects[0].last_recalc_date = b_proj.last_recalc_date
        half_step.projects[0].sum_data_date = b_proj.sum_data_date

    updated_count = 0

    for task_hs in half_step.activities:
        # Find matching task in Schedule B
        task_b = b_by_id.get(task_hs.task_id)
        if task_b is None:
            task_b = b_by_code.get(task_hs.task_code) if task_hs.task_code else None
        if task_b is None:
            continue  # Activity not in B — keep A's version unchanged

        # Determine if remaining duration change is progress
        rd_is_progress = _is_remaining_duration_progress(task_hs, task_b)

        # Transfer progress-only fields
        progress_transferred = False

        if task_hs.status_code != task_b.status_code:
            task_hs.status_code = task_b.status_code
            progress_transferred = True

        if task_hs.act_start_date != task_b.act_start_date:
            task_hs.act_start_date = task_b.act_start_date
            progress_transferred = True

        if task_hs.act_end_date != task_b.act_end_date:
            task_hs.act_end_date = task_b.act_end_date
            progress_transferred = True

        if abs(task_hs.phys_complete_pct - task_b.phys_complete_pct) > 0.01:
            task_hs.phys_complete_pct = task_b.phys_complete_pct
            progress_transferred = True

        if rd_is_progress and abs(task_hs.remain_drtn_hr_cnt - task_b.remain_drtn_hr_cnt) > 0.01:
            task_hs.remain_drtn_hr_cnt = task_b.remain_drtn_hr_cnt
            progress_transferred = True

        # Work quantities
        if abs(task_hs.act_work_qty - task_b.act_work_qty) > 0.01:
            task_hs.act_work_qty = task_b.act_work_qty
            progress_transferred = True

        if abs(task_hs.remain_work_qty - task_b.remain_work_qty) > 0.01:
            task_hs.remain_work_qty = task_b.remain_work_qty
            progress_transferred = True

        # For completed activities, zero out remaining duration
        if task_b.status_code.lower() == "tk_complete":
            task_hs.remain_drtn_hr_cnt = 0.0

        if progress_transferred:
            updated_count += 1

    return half_step, updated_count


def _is_remaining_duration_progress(task_a: Task, task_b: Task) -> bool:
    """Determine if a remaining duration change should be treated as progress.

    Uses the same heuristics as ``_classify_remaining_duration`` but returns
    a simple boolean for use during schedule construction.
    """
    a_status = task_a.status_code.lower()
    b_status = task_b.status_code.lower()

    # Not Started → Active: progress
    if a_status == "tk_notstart" and b_status == "tk_active":
        return True

    # Both Not Started: revision
    if a_status == "tk_notstart" and b_status == "tk_notstart":
        return False

    # Completed: progress
    if b_status == "tk_complete":
        return True

    # Active → Active: check if progress increased
    if a_status == "tk_active" and b_status == "tk_active":
        progress_delta = task_b.phys_complete_pct - task_a.phys_complete_pct
        rd_delta = task_a.remain_drtn_hr_cnt - task_b.remain_drtn_hr_cnt
        # Progress increased and RD decreased → progress
        if progress_delta > 0.01 and rd_delta > 0:
            return True
        # No progress but RD changed → revision
        if progress_delta <= 0.01:
            return False

    # Default: treat as progress (conservative for half-step)
    return True


def analyze_half_step(
    schedule_a: ParsedSchedule,
    schedule_b: ParsedSchedule,
) -> HalfStepResult:
    """Run a complete half-step (bifurcation) analysis.

    Per AACE RP 29R-03 MIP 3.4:
    1. Classify all changes between A and B as progress or revision
    2. Create half-step schedule (A + progress only)
    3. Run CPM on A, half-step, and B
    4. Calculate progress_effect and revision_effect
    5. Verify invariant: progress_effect + revision_effect == total_delay

    Args:
        schedule_a: The earlier (baseline) schedule.
        schedule_b: The later (update) schedule.

    Returns:
        A ``HalfStepResult`` with separated delay effects.
    """
    result = HalfStepResult()

    # Step 1: Classify changes
    classification = classify_changes(schedule_a, schedule_b)
    result.classification = classification

    # Step 2: Create half-step schedule
    half_step_schedule, updated_count = create_half_step_schedule(schedule_a, schedule_b)
    result.activities_updated = updated_count

    # Step 3: Run CPM on all three schedules
    cpm_a = CPMCalculator(schedule_a).calculate()
    cpm_hs = CPMCalculator(half_step_schedule).calculate()
    cpm_b = CPMCalculator(schedule_b).calculate()

    result.completion_a = cpm_a.project_duration
    result.completion_half_step = cpm_hs.project_duration
    result.completion_b = cpm_b.project_duration

    # Extract critical paths (as task codes for readability)
    result.critical_path_a = _cp_codes(cpm_a)
    result.critical_path_half_step = _cp_codes(cpm_hs)
    result.critical_path_b = _cp_codes(cpm_b)

    # Step 4: Calculate effects
    result.progress_effect = round(result.completion_half_step - result.completion_a, 6)
    result.revision_effect = round(result.completion_b - result.completion_half_step, 6)
    result.total_delay = round(result.completion_b - result.completion_a, 6)

    # Step 5: Verify invariant
    expected = round(result.progress_effect + result.revision_effect, 6)
    result.invariant_check = abs(expected - result.total_delay) < 0.01

    if not result.invariant_check:
        logger.warning(
            "Half-step invariant violation: progress(%.2f) + revision(%.2f) = %.2f != total(%.2f)",
            result.progress_effect,
            result.revision_effect,
            expected,
            result.total_delay,
        )

    # Build summary
    result.summary = _build_summary(result)

    return result


def _cp_codes(cpm_result: Any) -> list[str]:
    """Extract critical path as task codes (not internal IDs)."""
    codes: list[str] = []
    for tid in cpm_result.critical_path:
        ar = cpm_result.activity_results.get(tid)
        if ar:
            codes.append(ar.task_code or tid)
    return codes


def _build_summary(result: HalfStepResult) -> dict[str, Any]:
    """Build a human-readable summary of the half-step analysis."""
    progress_direction = (
        "delay"
        if result.progress_effect > 0.01
        else "acceleration"
        if result.progress_effect < -0.01
        else "neutral"
    )
    revision_direction = (
        "delay"
        if result.revision_effect > 0.01
        else "acceleration"
        if result.revision_effect < -0.01
        else "neutral"
    )

    cls = result.classification
    return {
        "methodology": "AACE RP 29R-03 MIP 3.4 — Contemporaneous Split Analysis",
        "completion_a_days": result.completion_a,
        "completion_half_step_days": result.completion_half_step,
        "completion_b_days": result.completion_b,
        "progress_effect_days": result.progress_effect,
        "progress_direction": progress_direction,
        "revision_effect_days": result.revision_effect,
        "revision_direction": revision_direction,
        "total_delay_days": result.total_delay,
        "invariant_holds": result.invariant_check,
        "activities_updated": result.activities_updated,
        "progress_changes": cls.summary.get("progress_changes", 0) if cls else 0,
        "revision_changes": cls.summary.get("revision_changes", 0) if cls else 0,
        "ambiguous_changes": cls.summary.get("ambiguous_changes", 0) if cls else 0,
        "activities_added_in_b": cls.summary.get("activities_added", 0) if cls else 0,
        "activities_deleted_from_a": (cls.summary.get("activities_deleted", 0) if cls else 0),
        "cp_stability_a_to_hs": _cp_stability(
            result.critical_path_a, result.critical_path_half_step
        ),
        "cp_stability_hs_to_b": _cp_stability(
            result.critical_path_half_step, result.critical_path_b
        ),
    }


def _cp_stability(cp1: list[str], cp2: list[str]) -> float:
    """Calculate critical path stability between two CP lists (0-100%)."""
    if not cp1 and not cp2:
        return 100.0
    if not cp1 or not cp2:
        return 0.0
    common = set(cp1) & set(cp2)
    union = set(cp1) | set(cp2)
    return round(len(common) / len(union) * 100, 1)
