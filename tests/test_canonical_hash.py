# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the forensic canonical-hash helper (ADR-0014).

These tests are a forensic contract. Relative tests assert determinism and
project-scoping properties; the byte-exact pin asserts that the canonical-JSON
algorithm itself has not drifted. Any change to ``src/database/canonical_hash.py``
that shifts the pin requires a superseding ADR-0015 plus a backfill worker.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime

import pytest

from src.database.canonical_hash import compute_input_hash
from src.parser.models import (
    ActivityCode,
    ActivityCodeType,
    Calendar,
    ParsedSchedule,
    Project,
    Relationship,
    Resource,
    Task,
    TaskActivityCode,
    TaskFinancial,
    TaskResource,
    WBS,
)


def _minimal_schedule(proj_id: str = "P1") -> ParsedSchedule:
    """Build a minimal ParsedSchedule with one project, one task, one calendar."""
    return ParsedSchedule(
        projects=[Project(proj_id=proj_id, proj_short_name=f"Project {proj_id}")],
        calendars=[Calendar(clndr_id="C1", clndr_name="Standard")],
        activities=[
            Task(
                task_id="T1",
                proj_id=proj_id,
                clndr_id="C1",
                task_code="A0001",
                task_name="Alpha",
                target_drtn_hr_cnt=80.0,
            )
        ],
        relationships=[],
    )


class TestDeterminism:
    """Same input → same hash."""

    def test_same_schedule_twice(self) -> None:
        s = _minimal_schedule()
        assert compute_input_hash(s, "P1") == compute_input_hash(s, "P1")

    def test_structurally_equal_schedules(self) -> None:
        a = _minimal_schedule()
        b = _minimal_schedule()
        assert compute_input_hash(a, "P1") == compute_input_hash(b, "P1")

    def test_hex_digest_shape(self) -> None:
        digest = compute_input_hash(_minimal_schedule(), "P1")
        assert len(digest) == 64
        assert digest == digest.lower()
        assert all(c in "0123456789abcdef" for c in digest)


class TestProjectScoping:
    """Different project_id on the same XER → different hash (multi-project stability)."""

    def test_different_project_id_same_schedule_different_hash(self) -> None:
        schedule = ParsedSchedule(
            projects=[
                Project(proj_id="P1", proj_short_name="Project 1"),
                Project(proj_id="P2", proj_short_name="Project 2"),
            ],
            activities=[
                Task(task_id="T1", proj_id="P1", task_name="Alpha"),
                Task(task_id="T2", proj_id="P2", task_name="Beta"),
            ],
        )
        h1 = compute_input_hash(schedule, "P1")
        h2 = compute_input_hash(schedule, "P2")
        assert h1 != h2

    def test_adding_unrelated_project_does_not_change_hash(self) -> None:
        """P1's hash must not shift when P2 is added/removed from the same XER.

        This is the multi-project stability property from ADR-0014 and resolves
        devils-advocate P1#7 (multi-project XER task_id collision).
        """
        single = _minimal_schedule(proj_id="P1")
        multi = ParsedSchedule(
            projects=[
                *single.projects,
                Project(proj_id="P2", proj_short_name="Other"),
            ],
            calendars=single.calendars,
            activities=[
                *single.activities,
                Task(task_id="T1", proj_id="P2", task_name="Other-alpha"),
            ],
        )
        assert compute_input_hash(single, "P1") == compute_input_hash(multi, "P1")

    def test_task_id_collision_across_projects_isolated(self) -> None:
        """Two projects with colliding task_id='T1' hash independently."""
        schedule = ParsedSchedule(
            projects=[
                Project(proj_id="P1"),
                Project(proj_id="P2"),
            ],
            activities=[
                Task(task_id="T1", proj_id="P1", task_name="Alpha-P1"),
                Task(task_id="T1", proj_id="P2", task_name="Alpha-P2"),
            ],
        )
        assert compute_input_hash(schedule, "P1") != compute_input_hash(schedule, "P2")


class TestContentSensitivity:
    """Any meaningful change in project-scoped content → different hash."""

    def test_task_name_change(self) -> None:
        a = _minimal_schedule()
        b = _minimal_schedule()
        b.activities[0].task_name = "Alpha-renamed"
        assert compute_input_hash(a, "P1") != compute_input_hash(b, "P1")

    def test_task_duration_change(self) -> None:
        a = _minimal_schedule()
        b = _minimal_schedule()
        b.activities[0].target_drtn_hr_cnt = 120.0
        assert compute_input_hash(a, "P1") != compute_input_hash(b, "P1")

    def test_adding_relationship(self) -> None:
        a = _minimal_schedule()
        a.activities.append(Task(task_id="T2", proj_id="P1", task_name="Beta"))
        b = ParsedSchedule(**a.model_dump())
        b.relationships.append(Relationship(task_id="T2", pred_task_id="T1", proj_id="P1"))
        assert compute_input_hash(a, "P1") != compute_input_hash(b, "P1")

    def test_adding_wbs_node(self) -> None:
        a = _minimal_schedule()
        b = _minimal_schedule()
        b.wbs_nodes.append(WBS(wbs_id="W1", proj_id="P1", wbs_name="Phase 1"))
        assert compute_input_hash(a, "P1") != compute_input_hash(b, "P1")

    def test_datetime_field_change(self) -> None:
        a = _minimal_schedule()
        b = _minimal_schedule()
        b.activities[0].target_start_date = datetime(2026, 4, 1, 8, 0, 0)
        assert compute_input_hash(a, "P1") != compute_input_hash(b, "P1")


class TestChainFilters:
    """FK-chain scoping: referenced-only inclusion for tables lacking proj_id."""

    def test_unreferenced_calendar_excluded(self) -> None:
        """A calendar not referenced by any of the project's activities must not
        influence the project's hash."""
        base = _minimal_schedule()
        with_extra_cal = _minimal_schedule()
        with_extra_cal.calendars.append(Calendar(clndr_id="C_OTHER", clndr_name="Unreferenced"))
        assert compute_input_hash(base, "P1") == compute_input_hash(with_extra_cal, "P1")

    def test_referenced_calendar_change_detected(self) -> None:
        """Changing the referenced calendar's data changes the hash."""
        a = _minimal_schedule()
        b = _minimal_schedule()
        b.calendars[0].clndr_data = "CUSTOM_WORKWEEK"
        assert compute_input_hash(a, "P1") != compute_input_hash(b, "P1")

    def test_unreferenced_resource_excluded(self) -> None:
        base = _minimal_schedule()
        with_extra = _minimal_schedule()
        with_extra.resources.append(Resource(rsrc_id="R_OTHER", rsrc_name="Unused"))
        assert compute_input_hash(base, "P1") == compute_input_hash(with_extra, "P1")

    def test_referenced_resource_included(self) -> None:
        with_res = _minimal_schedule()
        with_res.resources.append(Resource(rsrc_id="R1", rsrc_name="Labor"))
        with_res.task_resources.append(
            TaskResource(taskrsrc_id="TR1", task_id="T1", rsrc_id="R1", proj_id="P1")
        )
        base = _minimal_schedule()
        assert compute_input_hash(base, "P1") != compute_input_hash(with_res, "P1")

    def test_task_activity_code_chain_filter(self) -> None:
        """task_activity_codes included only for tasks in this project."""
        base = _minimal_schedule()
        with_tac = _minimal_schedule()
        with_tac.task_activity_codes.append(TaskActivityCode(task_id="T1", actv_code_id="AC1"))
        # task_id T1 belongs to P1, so this TAC should be included → hash differs
        assert compute_input_hash(base, "P1") != compute_input_hash(with_tac, "P1")

    def test_other_project_task_activity_code_excluded(self) -> None:
        """task_activity_codes whose task_id is NOT in this project must not count."""
        single = _minimal_schedule()
        multi = _minimal_schedule()
        # Add a different project's task and its TAC — must not influence P1's hash.
        multi.projects.append(Project(proj_id="P2"))
        multi.activities.append(Task(task_id="T99", proj_id="P2", task_name="P2-alpha"))
        multi.task_activity_codes.append(TaskActivityCode(task_id="T99", actv_code_id="AC_P2"))
        assert compute_input_hash(single, "P1") == compute_input_hash(multi, "P1")

    def test_task_financial_chain_filter_other_project(self) -> None:
        single = _minimal_schedule()
        multi = _minimal_schedule()
        multi.projects.append(Project(proj_id="P2"))
        multi.activities.append(Task(task_id="T99", proj_id="P2"))
        multi.task_financials.append(TaskFinancial(task_id="T99", target_cost=1000.0))
        assert compute_input_hash(single, "P1") == compute_input_hash(multi, "P1")

    def test_activity_code_chain_via_type(self) -> None:
        base = _minimal_schedule()
        with_codes = _minimal_schedule()
        with_codes.activity_code_types.append(
            ActivityCodeType(actv_code_type_id="ACT1", actv_code_type="Phase", proj_id="P1")
        )
        with_codes.activity_codes.append(
            ActivityCode(actv_code_id="AC1", actv_code_type_id="ACT1", actv_code_name="Design")
        )
        # orphan code — wrong type_id, not referenced
        with_codes.activity_codes.append(
            ActivityCode(actv_code_id="AC_ORPHAN", actv_code_type_id="ACT_OTHER")
        )
        with_orphan_only = _minimal_schedule()
        with_orphan_only.activity_codes.append(
            ActivityCode(actv_code_id="AC_ORPHAN", actv_code_type_id="ACT_OTHER")
        )
        assert compute_input_hash(base, "P1") == compute_input_hash(with_orphan_only, "P1")
        assert compute_input_hash(base, "P1") != compute_input_hash(with_codes, "P1")


class TestCanonicalJsonRules:
    """ADR-0014 canonical-JSON rules enforced."""

    def test_nan_raises(self) -> None:
        s = _minimal_schedule()
        s.activities[0].target_drtn_hr_cnt = float("nan")
        with pytest.raises(ValueError):
            compute_input_hash(s, "P1")

    def test_positive_inf_raises(self) -> None:
        s = _minimal_schedule()
        s.activities[0].target_drtn_hr_cnt = float("inf")
        with pytest.raises(ValueError):
            compute_input_hash(s, "P1")

    def test_negative_inf_raises(self) -> None:
        s = _minimal_schedule()
        s.activities[0].target_drtn_hr_cnt = float("-inf")
        with pytest.raises(ValueError):
            compute_input_hash(s, "P1")

    def test_naive_datetime_serialized_without_tz(self) -> None:
        """XER datetimes are naive local-project; canonical form preserves naivete."""
        s = _minimal_schedule()
        s.activities[0].target_start_date = datetime(2026, 4, 18, 12, 34, 56, 789012)
        h_naive = compute_input_hash(s, "P1")
        # Changing microseconds changes the hash — confirms microsecond precision captured.
        s.activities[0].target_start_date = datetime(2026, 4, 18, 12, 34, 56, 789013)
        assert compute_input_hash(s, "P1") != h_naive

    def test_accented_strings_roundtrip(self) -> None:
        """PT-BR accents must hash deterministically (ensure_ascii=False path)."""
        a = _minimal_schedule()
        a.projects[0].proj_short_name = "Projeto Ação"
        b = _minimal_schedule()
        b.projects[0].proj_short_name = "Projeto Ação"
        assert compute_input_hash(a, "P1") == compute_input_hash(b, "P1")

    def test_nfc_nfd_equivalence(self) -> None:
        """Strings that render identically but differ in Unicode normalization form
        must hash identically. Windows tools emit NFC by default; macOS tools
        often emit NFD. Silent divergence would produce two artifacts for one
        forensic schedule — exactly what ADR-0014 forbids.
        """
        nfc = unicodedata.normalize("NFC", "Projeto Ação — Etapa 1")
        nfd = unicodedata.normalize("NFD", "Projeto Ação — Etapa 1")
        assert nfc != nfd, "sanity: NFC and NFD byte-representations must differ"
        a = _minimal_schedule()
        a.projects[0].proj_short_name = nfc
        b = _minimal_schedule()
        b.projects[0].proj_short_name = nfd
        assert compute_input_hash(a, "P1") == compute_input_hash(b, "P1")

    def test_nfc_normalization_applied_in_deep_field(self) -> None:
        """NFC normalization must reach nested fields (here: task_name deep inside
        the activities[] array)."""
        nfc = unicodedata.normalize("NFC", "Construção — Fase 2")
        nfd = unicodedata.normalize("NFD", "Construção — Fase 2")
        a = _minimal_schedule()
        a.activities[0].task_name = nfc
        b = _minimal_schedule()
        b.activities[0].task_name = nfd
        assert compute_input_hash(a, "P1") == compute_input_hash(b, "P1")


def _rich_schedule() -> ParsedSchedule:
    """Fixture exercising every ParsedSchedule field-type consumed by _project_scope.

    Includes: multiple projects (to exercise slicing), activities with
    ``Optional[datetime]`` fields set, WBS, a relationship, a TaskResource→Resource
    chain, an ActivityCodeType→ActivityCode chain, a TaskActivityCode, and a
    TaskFinancial. This is the surface most likely to catch a Pydantic 2.x
    serialization drift that the minimal fixture would miss.
    """
    return ParsedSchedule(
        projects=[
            Project(
                proj_id="P1",
                proj_short_name="Rich P1",
                plan_start_date=datetime(2026, 1, 1, 8, 0, 0),
                plan_end_date=datetime(2026, 12, 31, 17, 0, 0),
            ),
            Project(proj_id="P2", proj_short_name="Other"),
        ],
        calendars=[
            Calendar(clndr_id="C1", clndr_name="Standard", day_hr_cnt=8.0),
            Calendar(clndr_id="C_OTHER", clndr_name="Unused"),
        ],
        wbs_nodes=[
            WBS(wbs_id="W1", proj_id="P1", wbs_name="Phase 1", seq_num=1),
            WBS(wbs_id="W2", proj_id="P1", wbs_name="Phase 2", seq_num=2),
        ],
        activities=[
            Task(
                task_id="T1",
                proj_id="P1",
                wbs_id="W1",
                clndr_id="C1",
                task_code="A0001",
                task_name="Design",
                target_drtn_hr_cnt=80.0,
                target_start_date=datetime(2026, 1, 15, 8, 0, 0),
                target_end_date=datetime(2026, 2, 10, 17, 0, 0),
            ),
            Task(
                task_id="T2",
                proj_id="P1",
                wbs_id="W2",
                clndr_id="C1",
                task_code="A0002",
                task_name="Construct",
                target_drtn_hr_cnt=120.0,
            ),
        ],
        relationships=[
            Relationship(
                task_pred_id="TP1",
                task_id="T2",
                pred_task_id="T1",
                proj_id="P1",
                pred_type="PR_FS",
                lag_hr_cnt=8.0,
            )
        ],
        resources=[
            Resource(rsrc_id="R1", rsrc_name="Engineer", rsrc_type="RT_Labor"),
            Resource(rsrc_id="R_OTHER", rsrc_name="Unused"),
        ],
        task_resources=[
            TaskResource(
                taskrsrc_id="TR1",
                task_id="T1",
                rsrc_id="R1",
                proj_id="P1",
                target_qty=40.0,
                target_cost=4000.0,
            )
        ],
        activity_code_types=[
            ActivityCodeType(actv_code_type_id="ACT1", actv_code_type="Phase", proj_id="P1")
        ],
        activity_codes=[
            ActivityCode(actv_code_id="AC1", actv_code_type_id="ACT1", actv_code_name="Design")
        ],
        task_activity_codes=[TaskActivityCode(task_id="T1", actv_code_id="AC1")],
        task_financials=[TaskFinancial(task_id="T1", target_cost=4000.0, act_cost=2000.0)],
    )


class TestByteExactPin:
    """Regression pin for the canonical-hash algorithm (ADR-0014 forensic contract).

    This test locks the hash of two fixtures:

    - ``_minimal_schedule``: baseline one-project, one-task, one-calendar fixture.
    - ``_rich_schedule``: exercises the full scoping surface (multi-project,
      activities-with-datetimes, WBS, relationship, resource chain, activity-code
      chain, task-activity-code, task-financial). The rich pin is the one most
      likely to move on a Pydantic 2.x minor-version drift affecting
      ``Optional[datetime]`` serialization or nested-BaseModel ordering.

    Any shift in either digest is a forensic-breaking change and requires a
    superseding ADR-0015 + full-table backfill worker before merging.
    """

    # Locked 2026-04-18 against the ADR-0014 implementation (post-NFC normalization).
    EXPECTED_PIN_MINIMAL: str = "3ecdacd40033f718762e2e11615ffa762c9fd02ac199ee829a6901734257d80d"
    EXPECTED_PIN_RICH: str = "145e31adc6e6143290a0edb996a26e76ccd08fb312c96389bab50f9ac3e64fc3"

    def test_minimal_pin_holds(self) -> None:
        s = _minimal_schedule()
        assert compute_input_hash(s, "P1") == self.EXPECTED_PIN_MINIMAL

    def test_rich_pin_holds(self) -> None:
        """Assert the rich-fixture digest matches the locked value."""
        s = _rich_schedule()
        assert compute_input_hash(s, "P1") == self.EXPECTED_PIN_RICH
