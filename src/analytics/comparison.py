# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Schedule comparison engine for detecting changes between two XER snapshots.

Compares a *baseline* and *update* ``ParsedSchedule`` to identify activity
changes, relationship changes, float shifts, constraint modifications,
progress issues, and schedule manipulation indicators.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.cpm import CPMCalculator
from src.parser.models import ParsedSchedule, Relationship, Task

logger = logging.getLogger(__name__)

# Float change severity thresholds (in hours, 8h/day)
_FLOAT_THRESHOLD_MINOR = 5 * 8.0  # 5 days
_FLOAT_THRESHOLD_MODERATE = 10 * 8.0  # 10 days
_FLOAT_THRESHOLD_MAJOR = 20 * 8.0  # 20 days


@dataclass
class ActivityChange:
    """A single detected change to an activity between baseline and update."""

    task_id: str
    task_name: str
    change_type: (
        str  # "added", "deleted", "duration", "description", "status", "dates", "calendar", "type"
    )
    old_value: str = ""
    new_value: str = ""
    severity: str = "info"  # "info", "warning", "critical"


@dataclass
class RelationshipChange:
    """A single detected change to a relationship between baseline and update."""

    task_id: str
    pred_task_id: str
    change_type: str  # "added", "deleted", "type_changed", "lag_changed"
    old_value: str = ""
    new_value: str = ""


@dataclass
class FloatChange:
    """A significant total-float change for an activity."""

    task_id: str
    task_name: str
    old_float: float
    new_float: float
    delta: float
    direction: str  # "improving", "deteriorating"


@dataclass
class ManipulationFlag:
    """A potential schedule manipulation indicator."""

    task_id: str
    task_name: str
    indicator: str  # "retroactive_date", "oos_progress", "unjustified_duration", "cp_logic_shift", "constraint_masking"
    description: str
    severity: str = "critical"


@dataclass
class CodeRestructuring:
    """A detected activity code change between schedule versions."""

    task_id: str
    old_code: str
    new_code: str
    activity_name: str


@dataclass
class MatchStats:
    """Statistics about how activities were matched between schedules."""

    matched_by_task_id: int = 0
    matched_by_task_code: int = 0
    total_matched: int = 0
    added: int = 0
    deleted: int = 0
    code_restructured: int = 0


@dataclass
class ComparisonResult:
    """Full comparison output between baseline and update schedules."""

    activities_added: list[ActivityChange] = field(default_factory=list)
    activities_deleted: list[ActivityChange] = field(default_factory=list)
    activity_modifications: list[ActivityChange] = field(default_factory=list)
    duration_changes: list[ActivityChange] = field(default_factory=list)
    relationships_added: list[RelationshipChange] = field(default_factory=list)
    relationships_deleted: list[RelationshipChange] = field(default_factory=list)
    relationships_modified: list[RelationshipChange] = field(default_factory=list)
    significant_float_changes: list[FloatChange] = field(default_factory=list)
    constraint_changes: list[ActivityChange] = field(default_factory=list)
    manipulation_flags: list[ManipulationFlag] = field(default_factory=list)
    code_restructuring: list[CodeRestructuring] = field(default_factory=list)
    match_stats: MatchStats = field(default_factory=MatchStats)
    changed_percentage: float = 0.0
    critical_path_changed: bool = False
    activities_joined_cp: list[str] = field(default_factory=list)
    activities_left_cp: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


class ScheduleComparison:
    """Compare two ``ParsedSchedule`` objects (baseline vs update).

    Detects activity changes, relationship changes, float shifts,
    constraint modifications, progress issues, and potential schedule
    manipulation indicators.

    Usage::

        cmp = ScheduleComparison(baseline, update)
        result = cmp.compare()
        print(f"Changed %: {result.changed_percentage:.1f}%")
    """

    def __init__(self, baseline: ParsedSchedule, update: ParsedSchedule) -> None:
        """Initialise comparison with multi-layer activity matching.

        Matching strategy (3 tiers):
        1. Match by task_id (P6 internal ID — most reliable for same-database exports)
        2. Match remaining by task_code (user-visible ID — fallback for cross-database)
        3. Remaining unmatched = truly added/deleted
        4. Detect code restructuring where task_id matches but task_code changed

        Args:
            baseline: The earlier (baseline) parsed schedule.
            update: The later (update) parsed schedule.
        """
        self.baseline = baseline
        self.update = update

        # Multi-layer matching
        self._matched: list[tuple[Task, Task]] = []
        self._added: list[Task] = []
        self._deleted: list[Task] = []
        self._code_changes: list[CodeRestructuring] = []
        self._match_stats = MatchStats()
        self._run_matching()

        # Build keyed lookup for matched pairs (use a stable key for each pair)
        # Use the update activity's task_code (or task_id) as the canonical key
        self._base_tasks: dict[str, Task] = {}
        self._upd_tasks: dict[str, Task] = {}
        for base_t, upd_t in self._matched:
            key = upd_t.task_code or upd_t.task_id
            self._base_tasks[key] = base_t
            self._upd_tasks[key] = upd_t

        # Build task_id→canonical_key lookups for relationship cross-referencing
        base_id_to_key: dict[str, str] = {}
        upd_id_to_key: dict[str, str] = {}
        for base_t, upd_t in self._matched:
            key = upd_t.task_code or upd_t.task_id
            base_id_to_key[base_t.task_id] = key
            upd_id_to_key[upd_t.task_id] = key
        # Also add unmatched activities for relationship resolution
        for t in self._added:
            upd_id_to_key[t.task_id] = t.task_code or t.task_id
        for t in self._deleted:
            base_id_to_key[t.task_id] = t.task_code or t.task_id

        # Build relationship keys using canonical keys
        self._base_rels: dict[tuple[str, str], Relationship] = {}
        for r in baseline.relationships:
            succ_key = base_id_to_key.get(r.task_id, r.task_id)
            pred_key = base_id_to_key.get(r.pred_task_id, r.pred_task_id)
            self._base_rels[(succ_key, pred_key)] = r

        self._upd_rels: dict[tuple[str, str], Relationship] = {}
        for r in update.relationships:
            succ_key = upd_id_to_key.get(r.task_id, r.task_id)
            pred_key = upd_id_to_key.get(r.pred_task_id, r.pred_task_id)
            self._upd_rels[(succ_key, pred_key)] = r

    def _run_matching(self) -> None:
        """Execute multi-layer activity matching."""
        base_activities = self.baseline.activities
        upd_activities = self.update.activities

        # Tier 1: Match by task_id (P6 internal ID)
        base_by_id: dict[str, Task] = {t.task_id: t for t in base_activities}
        upd_by_id: dict[str, Task] = {t.task_id: t for t in upd_activities}
        id_matches = set(base_by_id.keys()) & set(upd_by_id.keys())

        matched_base_ids: set[str] = set()
        matched_upd_ids: set[str] = set()

        for tid in id_matches:
            self._matched.append((base_by_id[tid], upd_by_id[tid]))
            matched_base_ids.add(tid)
            matched_upd_ids.add(tid)

        # Detect code restructuring (task_id matches but task_code changed)
        for base_t, upd_t in self._matched:
            if base_t.task_code and upd_t.task_code and base_t.task_code != upd_t.task_code:
                self._code_changes.append(
                    CodeRestructuring(
                        task_id=base_t.task_id,
                        old_code=base_t.task_code,
                        new_code=upd_t.task_code,
                        activity_name=upd_t.task_name or base_t.task_name,
                    )
                )

        # Tier 2: Match remaining by task_code (fallback)
        remaining_base = {
            t.task_code: t
            for t in base_activities
            if t.task_id not in matched_base_ids and t.task_code
        }
        remaining_upd = {
            t.task_code: t
            for t in upd_activities
            if t.task_id not in matched_upd_ids and t.task_code
        }
        code_matches = set(remaining_base.keys()) & set(remaining_upd.keys())

        for code in code_matches:
            self._matched.append((remaining_base[code], remaining_upd[code]))
            matched_base_ids.add(remaining_base[code].task_id)
            matched_upd_ids.add(remaining_upd[code].task_id)

        # Truly unmatched = added or deleted
        self._added = [t for t in upd_activities if t.task_id not in matched_upd_ids]
        self._deleted = [t for t in base_activities if t.task_id not in matched_base_ids]

        # Record stats
        self._match_stats = MatchStats(
            matched_by_task_id=len(id_matches),
            matched_by_task_code=len(code_matches),
            total_matched=len(self._matched),
            added=len(self._added),
            deleted=len(self._deleted),
            code_restructured=len(self._code_changes),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compare(self) -> ComparisonResult:
        """Run full comparison between baseline and update schedules.

        Returns:
            A ``ComparisonResult`` populated with all detected changes.
        """
        result = ComparisonResult()
        result.code_restructuring = list(self._code_changes)
        result.match_stats = self._match_stats

        self._compare_activities(result)
        self._compare_relationships(result)
        self._compare_float(result)
        self._compare_constraints(result)
        self._detect_manipulation(result)
        self._compare_critical_path(result)
        self._calculate_summary(result)

        return result

    # ------------------------------------------------------------------
    # Activity comparison
    # ------------------------------------------------------------------

    def _compare_activities(self, result: ComparisonResult) -> None:
        """Detect added, deleted, and modified activities.

        Uses pre-computed multi-layer matching results.

        Args:
            result: The result object to populate.
        """
        # Added activities (truly new — not matched by task_id or task_code)
        for task in self._added:
            result.activities_added.append(
                ActivityChange(
                    task_id=task.task_code or task.task_id,
                    task_name=task.task_name,
                    change_type="added",
                    new_value=task.task_code,
                    severity="warning",
                )
            )

        # Deleted activities (truly removed — not matched by task_id or task_code)
        for task in self._deleted:
            result.activities_deleted.append(
                ActivityChange(
                    task_id=task.task_code or task.task_id,
                    task_name=task.task_name,
                    change_type="deleted",
                    old_value=task.task_code,
                    severity="warning",
                )
            )

        # Modified activities (matched pairs)
        for base_t, upd_t in self._matched:
            self._detect_activity_modifications(base_t, upd_t, result)

    def _detect_activity_modifications(
        self, base: Task, upd: Task, result: ComparisonResult
    ) -> None:
        """Compare individual fields of a matched activity pair.

        Args:
            base: Baseline version of the activity.
            upd: Update version of the activity.
            result: The result object to populate.
        """
        tid = base.task_code or base.task_id

        # Description change
        if base.task_name != upd.task_name:
            result.activity_modifications.append(
                ActivityChange(
                    task_id=tid,
                    task_name=upd.task_name,
                    change_type="description",
                    old_value=base.task_name,
                    new_value=upd.task_name,
                    severity="info",
                )
            )

        # Duration change (target or remaining)
        if base.target_drtn_hr_cnt != upd.target_drtn_hr_cnt:
            result.duration_changes.append(
                ActivityChange(
                    task_id=tid,
                    task_name=upd.task_name,
                    change_type="duration",
                    old_value=str(base.target_drtn_hr_cnt),
                    new_value=str(upd.target_drtn_hr_cnt),
                    severity="warning",
                )
            )

        # Status change
        if base.status_code != upd.status_code:
            result.activity_modifications.append(
                ActivityChange(
                    task_id=tid,
                    task_name=upd.task_name,
                    change_type="status",
                    old_value=base.status_code,
                    new_value=upd.status_code,
                    severity="info",
                )
            )

        # Calendar change
        if base.clndr_id != upd.clndr_id:
            result.activity_modifications.append(
                ActivityChange(
                    task_id=tid,
                    task_name=upd.task_name,
                    change_type="calendar",
                    old_value=base.clndr_id,
                    new_value=upd.clndr_id,
                    severity="warning",
                )
            )

        # Type change
        if base.task_type != upd.task_type:
            result.activity_modifications.append(
                ActivityChange(
                    task_id=tid,
                    task_name=upd.task_name,
                    change_type="type",
                    old_value=base.task_type,
                    new_value=upd.task_type,
                    severity="warning",
                )
            )

        # Date changes (actual dates differ for completed/in-progress)
        date_changed = False
        if base.act_start_date != upd.act_start_date:
            date_changed = True
        if base.act_end_date != upd.act_end_date:
            date_changed = True

        if date_changed:
            old_dates = f"AS={base.act_start_date}, AF={base.act_end_date}"
            new_dates = f"AS={upd.act_start_date}, AF={upd.act_end_date}"
            result.activity_modifications.append(
                ActivityChange(
                    task_id=tid,
                    task_name=upd.task_name,
                    change_type="dates",
                    old_value=old_dates,
                    new_value=new_dates,
                    severity="warning",
                )
            )

    # ------------------------------------------------------------------
    # Relationship comparison
    # ------------------------------------------------------------------

    def _compare_relationships(self, result: ComparisonResult) -> None:
        """Detect added, deleted, and modified relationships.

        Args:
            result: The result object to populate.
        """
        base_keys = set(self._base_rels.keys())
        upd_keys = set(self._upd_rels.keys())

        # Added relationships
        for key in sorted(upd_keys - base_keys):
            rel = self._upd_rels[key]
            result.relationships_added.append(
                RelationshipChange(
                    task_id=rel.task_id,
                    pred_task_id=rel.pred_task_id,
                    change_type="added",
                    new_value=f"{rel.pred_type} lag={rel.lag_hr_cnt}",
                )
            )

        # Deleted relationships
        for key in sorted(base_keys - upd_keys):
            rel = self._base_rels[key]
            result.relationships_deleted.append(
                RelationshipChange(
                    task_id=rel.task_id,
                    pred_task_id=rel.pred_task_id,
                    change_type="deleted",
                    old_value=f"{rel.pred_type} lag={rel.lag_hr_cnt}",
                )
            )

        # Modified relationships (same key, different attributes)
        for key in sorted(base_keys & upd_keys):
            base_r = self._base_rels[key]
            upd_r = self._upd_rels[key]

            if base_r.pred_type != upd_r.pred_type:
                result.relationships_modified.append(
                    RelationshipChange(
                        task_id=base_r.task_id,
                        pred_task_id=base_r.pred_task_id,
                        change_type="type_changed",
                        old_value=base_r.pred_type,
                        new_value=upd_r.pred_type,
                    )
                )

            if abs(base_r.lag_hr_cnt - upd_r.lag_hr_cnt) > 0.01:
                result.relationships_modified.append(
                    RelationshipChange(
                        task_id=base_r.task_id,
                        pred_task_id=base_r.pred_task_id,
                        change_type="lag_changed",
                        old_value=str(base_r.lag_hr_cnt),
                        new_value=str(upd_r.lag_hr_cnt),
                    )
                )

    # ------------------------------------------------------------------
    # Float comparison
    # ------------------------------------------------------------------

    def _compare_float(self, result: ComparisonResult) -> None:
        """Detect significant total-float changes.

        Significant thresholds: >5 days, >10 days, >20 days (in hours).

        Args:
            result: The result object to populate.
        """
        for base_t, upd_t in self._matched:
            tid = upd_t.task_code or upd_t.task_id

            old_f = base_t.total_float_hr_cnt
            new_f = upd_t.total_float_hr_cnt

            if old_f is None or new_f is None:
                continue

            delta = new_f - old_f
            abs_delta = abs(delta)

            if abs_delta >= _FLOAT_THRESHOLD_MINOR:
                direction = "improving" if delta > 0 else "deteriorating"
                result.significant_float_changes.append(
                    FloatChange(
                        task_id=tid,
                        task_name=upd_t.task_name,
                        old_float=old_f,
                        new_float=new_f,
                        delta=delta,
                        direction=direction,
                    )
                )

    # ------------------------------------------------------------------
    # Constraint comparison
    # ------------------------------------------------------------------

    def _compare_constraints(self, result: ComparisonResult) -> None:
        """Detect added, removed, and modified constraints.

        Args:
            result: The result object to populate.
        """
        for base_t, upd_t in self._matched:
            tid = upd_t.task_code or upd_t.task_id

            base_cstr = (base_t.cstr_type or "").strip()
            upd_cstr = (upd_t.cstr_type or "").strip()

            if base_cstr != upd_cstr:
                if not base_cstr and upd_cstr:
                    change_type = "added"
                    severity = "warning"
                elif base_cstr and not upd_cstr:
                    change_type = "deleted"
                    severity = "info"
                else:
                    change_type = "modified"
                    severity = "warning"

                result.constraint_changes.append(
                    ActivityChange(
                        task_id=tid,
                        task_name=upd_t.task_name,
                        change_type=change_type,
                        old_value=base_cstr,
                        new_value=upd_cstr,
                        severity=severity,
                    )
                )

            # Also check secondary constraint
            base_cstr2 = (base_t.cstr_type2 or "").strip()
            upd_cstr2 = (upd_t.cstr_type2 or "").strip()

            if base_cstr2 != upd_cstr2:
                if not base_cstr2 and upd_cstr2:
                    change_type = "added"
                    severity = "warning"
                elif base_cstr2 and not upd_cstr2:
                    change_type = "deleted"
                    severity = "info"
                else:
                    change_type = "modified"
                    severity = "warning"

                result.constraint_changes.append(
                    ActivityChange(
                        task_id=tid,
                        task_name=upd_t.task_name,
                        change_type=change_type,
                        old_value=base_cstr2,
                        new_value=upd_cstr2,
                        severity=severity,
                    )
                )

        # Check new activities for constraints (newly added with constraints)
        for upd_t in self._added:
            tid = upd_t.task_code or upd_t.task_id
            upd_cstr = (upd_t.cstr_type or "").strip()
            if upd_cstr:
                result.constraint_changes.append(
                    ActivityChange(
                        task_id=tid,
                        task_name=upd_t.task_name,
                        change_type="added",
                        old_value="",
                        new_value=upd_cstr,
                        severity="warning",
                    )
                )

    # ------------------------------------------------------------------
    # Manipulation detection
    # ------------------------------------------------------------------

    def _detect_manipulation(self, result: ComparisonResult) -> None:
        """Detect potential schedule manipulation indicators.

        Checks for:
        - Retroactive actual date changes
        - Out-of-sequence progress
        - Unjustified duration changes on not-started activities
        - Constraint additions that may mask float

        Args:
            result: The result object to populate.
        """
        self._detect_retroactive_dates(result)
        self._detect_oos_progress(result)
        self._detect_unjustified_duration_changes(result)
        self._detect_constraint_masking(result)
        self._detect_mass_restructuring(result)

    def _detect_retroactive_dates(self, result: ComparisonResult) -> None:
        """Flag activities where actual dates differ between baseline and update.

        If a completed or in-progress activity has a different actual start
        or actual end date in the update, this may indicate retroactive
        editing of progress data.

        Args:
            result: The result object to populate.
        """
        for base_t, upd_t in self._matched:
            # Only flag if the activity was already started in the baseline
            if base_t.act_start_date is None:
                continue

            tid = upd_t.task_code or upd_t.task_id

            # Check if actual start date was changed retroactively
            if (
                base_t.act_start_date is not None
                and upd_t.act_start_date is not None
                and base_t.act_start_date != upd_t.act_start_date
            ):
                result.manipulation_flags.append(
                    ManipulationFlag(
                        task_id=tid,
                        task_name=upd_t.task_name,
                        indicator="retroactive_date",
                        description=(
                            f"Actual start changed from {base_t.act_start_date} "
                            f"to {upd_t.act_start_date}"
                        ),
                    )
                )

            # Check if actual end date was changed retroactively
            if (
                base_t.act_end_date is not None
                and upd_t.act_end_date is not None
                and base_t.act_end_date != upd_t.act_end_date
            ):
                result.manipulation_flags.append(
                    ManipulationFlag(
                        task_id=tid,
                        task_name=upd_t.task_name,
                        indicator="retroactive_date",
                        description=(
                            f"Actual end changed from {base_t.act_end_date} to {upd_t.act_end_date}"
                        ),
                    )
                )

    def _detect_oos_progress(self, result: ComparisonResult) -> None:
        """Detect out-of-sequence progress in the update schedule.

        An activity is out-of-sequence if it has an actual start but at
        least one predecessor is not yet finished.

        Args:
            result: The result object to populate.
        """
        # Build predecessor map using task_code for the update schedule
        upd_id_to_code: dict[str, str] = {
            t.task_id: t.task_code for t in self.update.activities if t.task_code
        }
        pred_map: dict[str, list[str]] = {}  # task_code -> [pred_task_codes]
        for rel in self.update.relationships:
            succ_code = upd_id_to_code.get(rel.task_id, rel.task_id)
            pred_code = upd_id_to_code.get(rel.pred_task_id, rel.pred_task_id)
            pred_map.setdefault(succ_code, []).append(pred_code)

        for task in self.update.activities:
            if task.act_start_date is None:
                continue

            preds = pred_map.get(task.task_code, [])
            for pred_code in preds:
                pred_task = self._upd_tasks.get(pred_code)
                if pred_task is None:
                    continue

                # Predecessor not finished but successor has started
                if (
                    pred_task.status_code.lower() != "tk_complete"
                    and pred_task.act_end_date is None
                ):
                    result.manipulation_flags.append(
                        ManipulationFlag(
                            task_id=task.task_code,
                            task_name=task.task_name,
                            indicator="oos_progress",
                            description=(
                                f"Started but predecessor {pred_code} "
                                f"({pred_task.task_name}) is not complete"
                            ),
                        )
                    )
                    break  # One flag per activity is enough

    def _detect_unjustified_duration_changes(self, result: ComparisonResult) -> None:
        """Flag duration changes on not-started activities.

        If a not-started activity has a different target duration without
        any progress, this may indicate unjustified schedule manipulation.

        Args:
            result: The result object to populate.
        """
        for base_t, upd_t in self._matched:
            tid = upd_t.task_code or upd_t.task_id

            # Only flag not-started activities (case-insensitive)
            if upd_t.status_code.lower() != "tk_notstart":
                continue
            if base_t.status_code.lower() != "tk_notstart":
                continue

            # Check target duration changed
            if base_t.target_drtn_hr_cnt != upd_t.target_drtn_hr_cnt:
                delta = upd_t.target_drtn_hr_cnt - base_t.target_drtn_hr_cnt
                result.manipulation_flags.append(
                    ManipulationFlag(
                        task_id=tid,
                        task_name=upd_t.task_name,
                        indicator="unjustified_duration",
                        description=(
                            f"Duration changed by {delta}h on not-started "
                            f"activity (from {base_t.target_drtn_hr_cnt}h "
                            f"to {upd_t.target_drtn_hr_cnt}h)"
                        ),
                        severity="warning",
                    )
                )

    def _detect_mass_restructuring(self, result: ComparisonResult) -> None:
        """Flag mass code restructuring as a manipulation indicator.

        If more than 10% of matched activities had their codes changed,
        this indicates a mass restructuring that can obscure forensic analysis.

        Args:
            result: The result object to populate.
        """
        if not self._matched:
            return
        pct = len(self._code_changes) / len(self._matched) * 100
        if pct > 10.0:
            result.manipulation_flags.append(
                ManipulationFlag(
                    task_id="SCHEDULE",
                    task_name="Mass Code Restructuring",
                    indicator="mass_code_restructuring",
                    description=(
                        f"{len(self._code_changes)} activities ({pct:.1f}%) had their "
                        f"codes changed. Mass restructuring can obscure schedule changes "
                        f"and complicates forensic analysis."
                    ),
                    severity="warning",
                )
            )

    def _detect_constraint_masking(self, result: ComparisonResult) -> None:
        """Flag new constraints that may mask float consumption.

        Adding constraints to activities can artificially control dates
        and hide deteriorating float.

        Args:
            result: The result object to populate.
        """
        for base_t, upd_t in self._matched:
            tid = upd_t.task_code or upd_t.task_id

            base_cstr = (base_t.cstr_type or "").strip()
            upd_cstr = (upd_t.cstr_type or "").strip()

            # New constraint added where there was none
            if not base_cstr and upd_cstr:
                # Check if float also changed
                old_f = base_t.total_float_hr_cnt
                new_f = upd_t.total_float_hr_cnt
                if old_f is not None and new_f is not None:
                    delta = new_f - old_f
                    if delta < -_FLOAT_THRESHOLD_MINOR:
                        result.manipulation_flags.append(
                            ManipulationFlag(
                                task_id=tid,
                                task_name=upd_t.task_name,
                                indicator="constraint_masking",
                                description=(
                                    f"New constraint {upd_cstr} added "
                                    f"while float deteriorated by {abs(delta)}h"
                                ),
                            )
                        )

    # ------------------------------------------------------------------
    # Critical path comparison
    # ------------------------------------------------------------------

    def _compare_critical_path(self, result: ComparisonResult) -> None:
        """Run CPM on both schedules and compare critical path activity lists.

        Args:
            result: The result object to populate.
        """
        try:
            base_cpm = CPMCalculator(self.baseline).calculate()
            upd_cpm = CPMCalculator(self.update).calculate()
        except Exception:
            logger.warning("CPM calculation failed during comparison")
            return

        if base_cpm.has_cycles or upd_cpm.has_cycles:
            logger.warning("Cannot compare critical paths: schedule has cycles")
            return

        base_cp = set(base_cpm.critical_path)
        upd_cp = set(upd_cpm.critical_path)

        joined = sorted(upd_cp - base_cp)
        left = sorted(base_cp - upd_cp)

        result.activities_joined_cp = joined
        result.activities_left_cp = left
        result.critical_path_changed = bool(joined or left)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _calculate_summary(self, result: ComparisonResult) -> None:
        """Calculate summary metrics.

        Args:
            result: The result object to populate.
        """
        total_baseline = len(self.baseline.activities)
        if total_baseline == 0:
            result.changed_percentage = 0.0
            result.summary = {}
            return

        added = len(result.activities_added)
        deleted = len(result.activities_deleted)
        # Deduplicate: count unique modified task_ids
        modified_ids: set[str] = set()
        for change in result.activity_modifications:
            modified_ids.add(change.task_id)
        for change in result.duration_changes:
            modified_ids.add(change.task_id)

        total_changed = added + deleted + len(modified_ids)
        # Use union of all unique activities across both schedules as denominator
        # This prevents >100% when adds+deletes+mods exceed baseline count
        total_universe = len(
            {t.task_code or t.task_id for t in self.baseline.activities}
            | {t.task_code or t.task_id for t in self.update.activities}
        )
        result.changed_percentage = round(
            min((total_changed / total_universe) * 100, 100.0) if total_universe > 0 else 0.0,
            2,
        )

        # Relationship churn
        total_base_rels = len(self._base_rels)
        rel_changes = (
            len(result.relationships_added)
            + len(result.relationships_deleted)
            + len(result.relationships_modified)
        )
        rel_churn = round((rel_changes / total_base_rels) * 100, 2) if total_base_rels > 0 else 0.0

        result.summary = {
            "baseline_activity_count": total_baseline,
            "update_activity_count": len(self.update.activities),
            "activities_added": added,
            "activities_deleted": deleted,
            "activities_modified": len(modified_ids),
            "total_changed": total_changed,
            "changed_percentage": result.changed_percentage,
            "baseline_relationship_count": total_base_rels,
            "update_relationship_count": len(self._upd_rels),
            "relationships_added": len(result.relationships_added),
            "relationships_deleted": len(result.relationships_deleted),
            "relationships_modified": len(result.relationships_modified),
            "relationship_churn": rel_churn,
            "significant_float_changes": len(result.significant_float_changes),
            "constraint_changes": len(result.constraint_changes),
            "manipulation_flags": len(result.manipulation_flags),
            "critical_path_changed": result.critical_path_changed,
            "activities_joined_cp": len(result.activities_joined_cp),
            "activities_left_cp": len(result.activities_left_cp),
        }
