# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for ``src/analytics/lifecycle_phase.py`` — W3 of Cycle 1 v4.0.

Per ADR-0016 the engine is intentionally lightweight; it ships before
calibration against the 105-XER sandbox (W4 gate). Tests assert:

* the 6-value taxonomy (5 phases + ``unknown``)
* each rule branch fires for a credible synthetic input
* confidence is in the expected band (low / medium / high) — NOT a
  specific float, so threshold tuning post-W4 won't churn this file
* the engine is pure (same input → same output)
* ``unknown`` paths (no project / no data_date / no activities)
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.analytics.lifecycle_phase import (
    ENGINE_NAME,
    RULESET_VERSION,
    infer_lifecycle_phase,
)
from src.analytics.lifecycle_types import (
    LIFECYCLE_PHASES,
    LifecyclePhaseInference,
    confidence_band,
)
from src.parser.models import (
    ActivityCode,
    ParsedSchedule,
    Project,
    Task,
)


# --------------------------------------------------------------------- #
# Helpers                                                               #
# --------------------------------------------------------------------- #


def _project(
    *,
    proj_id: str = "P",
    plan_start: datetime | None = None,
    plan_end: datetime | None = None,
    data_date: datetime | None = None,
) -> Project:
    return Project(
        proj_id=proj_id,
        proj_short_name=f"Project {proj_id}",
        plan_start_date=plan_start,
        plan_end_date=plan_end,
        last_recalc_date=data_date,
    )


def _task(
    task_id: str,
    *,
    proj_id: str = "P",
    phys_complete_pct: float = 0.0,
    target_start: datetime | None = None,
    target_end: datetime | None = None,
) -> Task:
    return Task(
        task_id=task_id,
        proj_id=proj_id,
        task_code=task_id,
        task_name=f"Task {task_id}",
        task_type="TT_Task",
        status_code="TK_NotStart",
        phys_complete_pct=phys_complete_pct,
        target_start_date=target_start,
        target_end_date=target_end,
    )


def _baselined_tasks(n: int, **overrides: object) -> list[Task]:
    """Return n tasks each carrying target_start/target_end (baseline present)."""
    base_target_start = datetime(2026, 1, 1)
    base_target_end = datetime(2027, 1, 1)
    return [
        _task(
            f"T{i:03d}",
            target_start=base_target_start,
            target_end=base_target_end,
            **overrides,  # type: ignore[arg-type]
        )
        for i in range(n)
    ]


# --------------------------------------------------------------------- #
# Phase: unknown                                                        #
# --------------------------------------------------------------------- #


class TestUnknownGuards:
    def test_no_projects_returns_unknown(self) -> None:
        result = infer_lifecycle_phase(ParsedSchedule())
        assert result.phase == "unknown"
        assert result.confidence == 0.0
        assert result.rationale["reason"] == "no_project_record"

    def test_no_data_date_returns_unknown(self) -> None:
        schedule = ParsedSchedule(projects=[_project(data_date=None)])
        result = infer_lifecycle_phase(schedule)
        assert result.phase == "unknown"
        assert result.confidence == 0.0
        assert result.rationale["reason"] == "no_data_date"

    def test_no_activities_returns_unknown(self) -> None:
        schedule = ParsedSchedule(
            projects=[_project(data_date=datetime(2026, 6, 1))],
            activities=[],
        )
        result = infer_lifecycle_phase(schedule)
        assert result.phase == "unknown"
        assert result.confidence == 0.0
        assert result.rationale["reason"] == "no_activities"

    def test_unknown_phase_serialises_with_zero_confidence(self) -> None:
        # Direct construction guard.
        with pytest.raises(ValueError):
            LifecyclePhaseInference(phase="unknown", confidence=0.5)


# --------------------------------------------------------------------- #
# Phase: planning                                                       #
# --------------------------------------------------------------------- #


class TestPlanningRules:
    def test_no_baseline_no_actuals_high_confidence(self) -> None:
        # AACE RP 14R §3 — no baseline + no actuals = clearly planning.
        schedule = ParsedSchedule(
            projects=[
                _project(
                    plan_start=datetime(2026, 1, 1),
                    plan_end=datetime(2027, 1, 1),
                    data_date=datetime(2026, 1, 5),
                )
            ],
            activities=[
                _task(f"T{i}", phys_complete_pct=0.0)  # no target dates
                for i in range(5)
            ],
        )
        result = infer_lifecycle_phase(schedule)
        assert result.phase == "planning"
        assert confidence_band(result.confidence) == "high"
        assert result.rationale["rule"] == "no_baseline_no_actuals"

    def test_at_plan_start_with_baseline_returns_planning(self) -> None:
        plan_start = datetime(2026, 1, 1)
        schedule = ParsedSchedule(
            projects=[
                _project(
                    plan_start=plan_start,
                    plan_end=datetime(2027, 1, 1),
                    data_date=plan_start,
                )
            ],
            activities=_baselined_tasks(5),
        )
        result = infer_lifecycle_phase(schedule)
        assert result.phase == "planning"
        assert confidence_band(result.confidence) == "high"
        assert result.rationale["rule"] == "pre_or_at_plan_start"


# --------------------------------------------------------------------- #
# Phase: design                                                         #
# --------------------------------------------------------------------- #


class TestDesignRules:
    def test_early_elapsed_low_actuals_no_procurement(self) -> None:
        plan_start = datetime(2026, 1, 1)
        plan_end = datetime(2027, 1, 1)  # 1-year project
        # ~10% elapsed
        data_date = plan_start + timedelta(days=36)
        schedule = ParsedSchedule(
            projects=[_project(plan_start=plan_start, plan_end=plan_end, data_date=data_date)],
            activities=_baselined_tasks(5, phys_complete_pct=2.0),
        )
        result = infer_lifecycle_phase(schedule)
        assert result.phase == "design"
        assert confidence_band(result.confidence) in {"medium", "high"}
        assert result.rationale["rule"] == "early_elapsed_low_actuals_no_procurement"


# --------------------------------------------------------------------- #
# Phase: procurement                                                    #
# --------------------------------------------------------------------- #


class TestProcurementRules:
    def test_procurement_codes_with_low_actuals(self) -> None:
        # Procurement phase: baseline exists, very few activities have
        # actually started (started_pct < 25%), and the schedule carries
        # procurement-flavoured activity codes. Phys=0.0 across the
        # project models "we have a baseline + a procurement WBS but
        # crews haven't broken ground yet."
        plan_start = datetime(2026, 1, 1)
        plan_end = datetime(2027, 1, 1)
        data_date = plan_start + timedelta(days=20)
        schedule = ParsedSchedule(
            projects=[_project(plan_start=plan_start, plan_end=plan_end, data_date=data_date)],
            activities=_baselined_tasks(5, phys_complete_pct=0.0),
            activity_codes=[
                ActivityCode(
                    actv_code_id="AC1",
                    actv_code_name="PROCUREMENT — Long Lead",
                    short_name="LL",
                ),
            ],
        )
        result = infer_lifecycle_phase(schedule)
        assert result.phase == "procurement"
        assert confidence_band(result.confidence) in {"medium", "high"}
        assert result.rationale["has_procurement_codes"] is True
        assert result.rationale["rule"] == "procurement_codes_low_actuals"


# --------------------------------------------------------------------- #
# Phase: construction                                                   #
# --------------------------------------------------------------------- #


class TestConstructionRules:
    def test_meaningful_actuals_mid_progress(self) -> None:
        plan_start = datetime(2026, 1, 1)
        plan_end = datetime(2027, 1, 1)
        # ~50% elapsed
        data_date = plan_start + timedelta(days=183)
        schedule = ParsedSchedule(
            projects=[_project(plan_start=plan_start, plan_end=plan_end, data_date=data_date)],
            activities=_baselined_tasks(10, phys_complete_pct=50.0),
        )
        result = infer_lifecycle_phase(schedule)
        assert result.phase == "construction"
        assert confidence_band(result.confidence) in {"medium", "high"}
        assert result.rationale["rule"] == "meaningful_actuals_mid_progress"

    def test_construction_confidence_peaks_around_50_phys(self) -> None:
        """Sharper signal in the middle of the construction band is
        an explicit modelling choice — pin it as a regression."""
        plan_start = datetime(2026, 1, 1)
        plan_end = datetime(2027, 1, 1)
        data_date = plan_start + timedelta(days=183)

        def _build(phys: float) -> LifecyclePhaseInference:
            return infer_lifecycle_phase(
                ParsedSchedule(
                    projects=[
                        _project(
                            plan_start=plan_start,
                            plan_end=plan_end,
                            data_date=data_date,
                        )
                    ],
                    activities=_baselined_tasks(10, phys_complete_pct=phys),
                )
            )

        center = _build(50.0)
        edge_low = _build(10.0)
        edge_high = _build(85.0)
        assert center.phase == "construction"
        assert edge_low.phase == "construction"
        assert edge_high.phase == "construction"
        # Center should never be lower-confidence than the band edges.
        assert center.confidence >= edge_low.confidence
        assert center.confidence >= edge_high.confidence


# --------------------------------------------------------------------- #
# Phase: closeout                                                       #
# --------------------------------------------------------------------- #


class TestCloseoutRules:
    def test_majority_complete_late_in_baseline(self) -> None:
        plan_start = datetime(2026, 1, 1)
        plan_end = datetime(2027, 1, 1)
        # 99% elapsed
        data_date = plan_start + timedelta(days=362)
        schedule = ParsedSchedule(
            projects=[_project(plan_start=plan_start, plan_end=plan_end, data_date=data_date)],
            activities=_baselined_tasks(10, phys_complete_pct=100.0),
        )
        result = infer_lifecycle_phase(schedule)
        assert result.phase == "closeout"
        assert confidence_band(result.confidence) == "high"
        assert result.rationale["rule"] == "majority_complete_late_in_baseline"

    def test_past_plan_end_high_progress(self) -> None:
        plan_start = datetime(2026, 1, 1)
        plan_end = datetime(2027, 1, 1)
        # past plan_end
        data_date = plan_end + timedelta(days=30)
        schedule = ParsedSchedule(
            projects=[_project(plan_start=plan_start, plan_end=plan_end, data_date=data_date)],
            activities=_baselined_tasks(10, phys_complete_pct=92.0),
        )
        result = infer_lifecycle_phase(schedule)
        assert result.phase == "closeout"
        # Either of the two closeout rules is acceptable here.
        assert result.rationale["rule"] in {
            "past_plan_end_high_progress",
            "majority_complete_late_in_baseline",
        }


# --------------------------------------------------------------------- #
# Determinism + pure function discipline                                 #
# --------------------------------------------------------------------- #


class TestDeterminism:
    def test_same_input_same_output(self) -> None:
        plan_start = datetime(2026, 1, 1)
        plan_end = datetime(2027, 1, 1)
        data_date = plan_start + timedelta(days=183)
        schedule = ParsedSchedule(
            projects=[_project(plan_start=plan_start, plan_end=plan_end, data_date=data_date)],
            activities=_baselined_tasks(8, phys_complete_pct=40.0),
        )
        a = infer_lifecycle_phase(schedule)
        b = infer_lifecycle_phase(schedule)
        assert a.phase == b.phase
        assert a.confidence == b.confidence
        assert a.rationale == b.rationale

    def test_engine_metadata_constants(self) -> None:
        assert ENGINE_NAME == "lifecycle_phase"
        assert RULESET_VERSION.startswith("lifecycle_phase-v1")
        # Ruleset version must be ASCII safe and short — survives canonical_hash.
        assert RULESET_VERSION.isascii()


# --------------------------------------------------------------------- #
# Taxonomy guard                                                        #
# --------------------------------------------------------------------- #


class TestTaxonomyGuard:
    def test_5_phases_plus_unknown(self) -> None:
        assert set(LIFECYCLE_PHASES) == {
            "planning",
            "design",
            "procurement",
            "construction",
            "closeout",
            "unknown",
        }

    def test_engine_only_emits_taxonomy_phases(self) -> None:
        plan_start = datetime(2026, 1, 1)
        plan_end = datetime(2027, 1, 1)

        scenarios = [
            # (phys, days_elapsed) — span the rule cascade
            (0.0, 0),
            (1.0, 30),
            (50.0, 183),
            (95.0, 362),
            (98.0, 400),
        ]
        for phys, days in scenarios:
            schedule = ParsedSchedule(
                projects=[
                    _project(
                        plan_start=plan_start,
                        plan_end=plan_end,
                        data_date=plan_start + timedelta(days=days),
                    )
                ],
                activities=_baselined_tasks(5, phys_complete_pct=phys),
            )
            result = infer_lifecycle_phase(schedule)
            assert result.phase in LIFECYCLE_PHASES
