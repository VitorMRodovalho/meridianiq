# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for SupabaseStore schedule persistence (persist + reconstruct).

Uses mock Supabase client to test the round-trip:
  ParsedSchedule -> _persist_schedule_data -> DB rows -> _reconstruct_from_db -> ParsedSchedule

Verifies that all 13 entity types survive the persist/reconstruct cycle.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

os.environ["ENVIRONMENT"] = "development"

from src.database.store import SupabaseStore, _parse_dt
from src.parser.models import (
    ActivityCode,
    ActivityCodeType,
    Calendar,
    FinancialPeriod,
    ParsedSchedule,
    Project,
    Relationship,
    Resource,
    Task,
    TaskActivityCode,
    TaskFinancial,
    TaskResource,
    UDFType,
    UDFValue,
    WBS,
)


# ------------------------------------------------------------------ #
# Fixture: rich ParsedSchedule with all 13 entity types              #
# ------------------------------------------------------------------ #


def _make_rich_schedule() -> ParsedSchedule:
    """Build a ParsedSchedule with all entity types populated."""
    return ParsedSchedule(
        projects=[
            Project(
                proj_id="P1",
                proj_short_name="RichProj",
                last_recalc_date=datetime(2026, 1, 15),
                plan_start_date=datetime(2026, 1, 1),
                plan_end_date=datetime(2026, 12, 31),
            )
        ],
        calendars=[
            Calendar(
                clndr_id="C1",
                clndr_name="5-Day Week",
                day_hr_cnt=8.0,
                week_hr_cnt=40.0,
                clndr_type="CT_Week",
                default_flag="Y",
                clndr_data="(0||1||2||3||4)()(5||6)()",
            )
        ],
        wbs_nodes=[
            WBS(
                wbs_id="W1",
                proj_id="P1",
                parent_wbs_id="",
                wbs_short_name="Root",
                wbs_name="Project Root",
                seq_num=1,
                proj_node_flag="Y",
            ),
            WBS(
                wbs_id="W2",
                proj_id="P1",
                parent_wbs_id="W1",
                wbs_short_name="Phase1",
                wbs_name="Phase 1 - Design",
                seq_num=2,
            ),
        ],
        activities=[
            Task(
                task_id="T1",
                proj_id="P1",
                wbs_id="W2",
                clndr_id="C1",
                task_code="A0010",
                task_name="Design Review",
                task_type="TT_Task",
                status_code="TK_Active",
                total_float_hr_cnt=0.0,
                free_float_hr_cnt=0.0,
                remain_drtn_hr_cnt=40.0,
                target_drtn_hr_cnt=80.0,
                act_start_date=datetime(2026, 2, 1),
                early_start_date=datetime(2026, 2, 1),
                early_end_date=datetime(2026, 2, 14),
                late_start_date=datetime(2026, 2, 1),
                late_end_date=datetime(2026, 2, 14),
                target_start_date=datetime(2026, 1, 15),
                target_end_date=datetime(2026, 2, 10),
                restart_date=datetime(2026, 2, 5),
                phys_complete_pct=50.0,
                complete_pct_type="CP_Phys",
                duration_type="DT_FixedDrtn",
                cstr_type="CS_ALAP",
                float_path=1,
                float_path_order=10,
                driving_path_flag="Y",
                priority_type="PT_Top",
                act_work_qty=20.0,
                remain_work_qty=20.0,
                target_work_qty=40.0,
                task_id_key="P1-T1",
            ),
            Task(
                task_id="T2",
                proj_id="P1",
                wbs_id="W2",
                clndr_id="C1",
                task_code="A0020",
                task_name="Construction",
                task_type="TT_Task",
                status_code="TK_NotStart",
                total_float_hr_cnt=16.0,
                target_drtn_hr_cnt=120.0,
                remain_drtn_hr_cnt=120.0,
                early_start_date=datetime(2026, 2, 15),
                early_end_date=datetime(2026, 3, 31),
                target_start_date=datetime(2026, 2, 15),
                target_end_date=datetime(2026, 3, 31),
            ),
        ],
        relationships=[
            Relationship(
                task_pred_id="TP1",
                task_id="T2",
                pred_task_id="T1",
                pred_type="PR_FS",
                lag_hr_cnt=0.0,
            )
        ],
        resources=[Resource(rsrc_id="R1", rsrc_name="Engineer", rsrc_type="RT_Labor")],
        task_resources=[
            TaskResource(
                taskrsrc_id="TR1",
                task_id="T1",
                rsrc_id="R1",
                proj_id="P1",
                target_qty=40.0,
                act_reg_qty=20.0,
                remain_qty=20.0,
                target_cost=4000.0,
                act_reg_cost=2000.0,
                remain_cost=2000.0,
            )
        ],
        activity_code_types=[
            ActivityCodeType(
                actv_code_type_id="ACT1",
                actv_code_type="Phase",
                proj_id="P1",
            )
        ],
        activity_codes=[
            ActivityCode(
                actv_code_id="AC1",
                actv_code_type_id="ACT1",
                actv_code_name="Design",
                short_name="DES",
            )
        ],
        task_activity_codes=[TaskActivityCode(task_id="T1", actv_code_id="AC1")],
        udf_types=[
            UDFType(
                udf_type_id="UDF1",
                table_name="TASK",
                udf_type_label="Risk Level",
            )
        ],
        udf_values=[
            UDFValue(
                udf_type_id="UDF1",
                fk_id="T1",
                udf_text="High",
                udf_number=3.0,
            )
        ],
        financial_periods=[
            FinancialPeriod(
                fin_dates_id="FP1",
                fin_dates_name="Jan 2026",
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 1, 31),
            )
        ],
        task_financials=[
            TaskFinancial(
                task_id="T1",
                fin_dates_id="FP1",
                target_cost=4000.0,
                act_cost=2000.0,
            )
        ],
    )


# ------------------------------------------------------------------ #
# Mock SupabaseStore that captures inserts in memory                  #
# ------------------------------------------------------------------ #


class _MockTableQuery:
    """Minimal mock for Supabase table().select().eq().limit().execute() chain."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def select(self, columns: str = "*") -> "_MockTableQuery":
        return self

    def eq(self, col: str, val: Any) -> "_MockTableQuery":
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def limit(self, n: int) -> "_MockTableQuery":
        self._rows = self._rows[:n]
        return self

    def range(self, start: int, end: int) -> "_MockTableQuery":
        self._rows = self._rows[start : end + 1]
        return self

    def execute(self) -> Any:
        result = MagicMock()
        result.data = self._rows
        return result


class _MockClient:
    """Minimal mock Supabase client with table() method."""

    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self._tables = tables

    def table(self, name: str) -> _MockTableQuery:
        return _MockTableQuery(list(self._tables.get(name, [])))


class MockSupabaseStore(SupabaseStore):
    """SupabaseStore with mocked Supabase client that stores data in-memory."""

    def __init__(self) -> None:
        # Skip parent __init__ (would try to connect to Supabase)
        self._tables: dict[str, list[dict[str, Any]]] = {}
        self._analyses: dict[str, dict[str, Any]] = {}
        self._comparisons: dict[str, dict[str, Any]] = {}
        # Provide a mock _client for _reconstruct_from_db's probe query
        self._client = _MockClient(self._tables)  # type: ignore[assignment]

    def _insert(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        if table not in self._tables:
            self._tables[table] = []
        row_id = data.get("id", f"uuid-{len(self._tables[table]) + 1}")
        row = {**data, "id": row_id}
        self._tables[table].append(row)
        return row

    def _batch_insert(self, table: str, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self._insert(table, row)

    def _select(
        self,
        table: str,
        filters: dict[str, Any] | None = None,
        columns: str = "*",
    ) -> list[dict[str, Any]]:
        rows = self._tables.get(table, [])
        if filters:
            for col, val in filters.items():
                rows = [r for r in rows if r.get(col) == val]
        return rows

    def _select_all(
        self,
        table: str,
        project_id: str,
        columns: str = "*",
    ) -> list[dict[str, Any]]:
        return self._select(table, {"project_id": project_id}, columns)


# ------------------------------------------------------------------ #
# Tests: _persist_schedule_data                                      #
# ------------------------------------------------------------------ #


class TestPersistScheduleData:
    """Verify _persist_schedule_data writes all 13 entity types."""

    def test_all_tables_populated(self) -> None:
        store = MockSupabaseStore()
        schedule = _make_rich_schedule()
        store._persist_schedule_data("proj-001", schedule)

        assert len(store._tables.get("wbs_elements", [])) == 2
        assert len(store._tables.get("activities", [])) == 2
        assert len(store._tables.get("predecessors", [])) == 1
        assert len(store._tables.get("calendars", [])) == 1
        assert len(store._tables.get("resources", [])) == 1
        assert len(store._tables.get("resource_assignments", [])) == 1
        assert len(store._tables.get("activity_code_types", [])) == 1
        assert len(store._tables.get("activity_codes", [])) == 1
        assert len(store._tables.get("task_activity_codes", [])) == 1
        assert len(store._tables.get("udf_types", [])) == 1
        assert len(store._tables.get("udf_values", [])) == 1
        assert len(store._tables.get("financial_periods", [])) == 1
        assert len(store._tables.get("task_financials", [])) == 1

    def test_activity_extra_data_populated(self) -> None:
        store = MockSupabaseStore()
        schedule = _make_rich_schedule()
        store._persist_schedule_data("proj-001", schedule)

        act_rows = store._tables["activities"]
        t1 = next(r for r in act_rows if r["task_id"] == "T1")
        extra = t1["extra_data"]
        assert extra["complete_pct_type"] == "CP_Phys"
        assert extra["duration_type"] == "DT_FixedDrtn"
        assert extra["float_path"] == 1
        assert extra["driving_path_flag"] == "Y"
        assert extra["task_id_key"] == "P1-T1"
        assert extra["act_work_qty"] == 20.0

    def test_project_id_set_on_all_rows(self) -> None:
        store = MockSupabaseStore()
        store._persist_schedule_data("proj-xyz", _make_rich_schedule())

        for table_name, rows in store._tables.items():
            for row in rows:
                assert row.get("project_id") == "proj-xyz", f"Missing project_id in {table_name}"

    def test_empty_schedule_inserts_nothing(self) -> None:
        store = MockSupabaseStore()
        store._persist_schedule_data("proj-empty", ParsedSchedule())
        # Only empty lists — no rows inserted
        for rows in store._tables.values():
            assert len(rows) == 0

    def test_persistence_failure_does_not_raise(self) -> None:
        """_persist_schedule_data should log warning, not raise."""
        store = MockSupabaseStore()

        def exploding_insert(table: str, rows: list[dict]) -> None:
            raise RuntimeError("DB connection lost")

        store._batch_insert = exploding_insert  # type: ignore[assignment]
        # Should NOT raise
        store._persist_schedule_data("proj-fail", _make_rich_schedule())


# ------------------------------------------------------------------ #
# Tests: _reconstruct_from_db                                        #
# ------------------------------------------------------------------ #


class TestReconstructFromDb:
    """Verify _reconstruct_from_db rebuilds ParsedSchedule from DB rows."""

    def _persist_and_reconstruct(self) -> tuple[ParsedSchedule, ParsedSchedule | None]:
        """Helper: persist a rich schedule, then reconstruct it."""
        store = MockSupabaseStore()
        original = _make_rich_schedule()

        # Insert project metadata (mimicking save_project)
        store._insert(
            "projects",
            {
                "id": "proj-001",
                "project_name": "RichProj",
                "data_date": "2026-01-15T00:00:00",
                "activity_count": 2,
            },
        )
        # Persist schedule data
        store._persist_schedule_data("proj-001", original)

        # Reconstruct
        reconstructed = store._reconstruct_from_db("proj-001")
        return original, reconstructed

    def test_reconstruction_returns_schedule(self) -> None:
        _, reconstructed = self._persist_and_reconstruct()
        assert reconstructed is not None
        assert isinstance(reconstructed, ParsedSchedule)

    def test_activity_count_matches(self) -> None:
        original, reconstructed = self._persist_and_reconstruct()
        assert reconstructed is not None
        assert len(reconstructed.activities) == len(original.activities)

    def test_wbs_count_matches(self) -> None:
        original, reconstructed = self._persist_and_reconstruct()
        assert reconstructed is not None
        assert len(reconstructed.wbs_nodes) == len(original.wbs_nodes)

    def test_relationship_count_matches(self) -> None:
        original, reconstructed = self._persist_and_reconstruct()
        assert reconstructed is not None
        assert len(reconstructed.relationships) == len(original.relationships)

    def test_calendar_clndr_data_preserved(self) -> None:
        _, reconstructed = self._persist_and_reconstruct()
        assert reconstructed is not None
        cal = reconstructed.calendars[0]
        assert cal.clndr_data == "(0||1||2||3||4)()(5||6)()"

    def test_activity_extra_fields_preserved(self) -> None:
        _, reconstructed = self._persist_and_reconstruct()
        assert reconstructed is not None
        t1 = next(a for a in reconstructed.activities if a.task_id == "T1")
        assert t1.complete_pct_type == "CP_Phys"
        assert t1.duration_type == "DT_FixedDrtn"
        assert t1.float_path == 1
        assert t1.float_path_order == 10
        assert t1.driving_path_flag == "Y"
        assert t1.act_work_qty == 20.0
        assert t1.task_id_key == "P1-T1"

    def test_activity_dates_preserved(self) -> None:
        _, reconstructed = self._persist_and_reconstruct()
        assert reconstructed is not None
        t1 = next(a for a in reconstructed.activities if a.task_id == "T1")
        assert t1.act_start_date == datetime(2026, 2, 1)
        assert t1.early_start_date == datetime(2026, 2, 1)
        assert t1.target_start_date == datetime(2026, 1, 15)

    def test_resource_assignments_preserved(self) -> None:
        _, reconstructed = self._persist_and_reconstruct()
        assert reconstructed is not None
        assert len(reconstructed.task_resources) == 1
        tr = reconstructed.task_resources[0]
        assert tr.taskrsrc_id == "TR1"
        assert tr.target_cost == 4000.0
        assert tr.act_reg_cost == 2000.0

    def test_activity_codes_preserved(self) -> None:
        _, reconstructed = self._persist_and_reconstruct()
        assert reconstructed is not None
        assert len(reconstructed.activity_code_types) == 1
        assert len(reconstructed.activity_codes) == 1
        assert len(reconstructed.task_activity_codes) == 1
        assert reconstructed.activity_codes[0].actv_code_name == "Design"

    def test_udf_preserved(self) -> None:
        _, reconstructed = self._persist_and_reconstruct()
        assert reconstructed is not None
        assert len(reconstructed.udf_types) == 1
        assert len(reconstructed.udf_values) == 1
        assert reconstructed.udf_values[0].udf_text == "High"

    def test_financials_preserved(self) -> None:
        _, reconstructed = self._persist_and_reconstruct()
        assert reconstructed is not None
        assert len(reconstructed.financial_periods) == 1
        assert len(reconstructed.task_financials) == 1
        assert reconstructed.task_financials[0].target_cost == 4000.0

    def test_nonexistent_project_returns_none(self) -> None:
        store = MockSupabaseStore()
        assert store._reconstruct_from_db("proj-missing") is None

    def test_project_name_preserved(self) -> None:
        _, reconstructed = self._persist_and_reconstruct()
        assert reconstructed is not None
        assert reconstructed.projects[0].proj_short_name == "RichProj"


# ------------------------------------------------------------------ #
# Tests: _parse_dt helper                                            #
# ------------------------------------------------------------------ #


class TestParseDt:
    """Test the _parse_dt module-level helper."""

    def test_none_returns_none(self) -> None:
        assert _parse_dt(None) is None

    def test_datetime_passthrough(self) -> None:
        dt = datetime(2026, 1, 1, 12, 0)
        assert _parse_dt(dt) is dt

    def test_iso_string(self) -> None:
        result = _parse_dt("2026-03-15T10:30:00")
        assert result == datetime(2026, 3, 15, 10, 30)

    def test_invalid_string_returns_none(self) -> None:
        assert _parse_dt("not-a-date") is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_dt("") is None


# ------------------------------------------------------------------ #
# Tests: Round-trip equivalence for analysis engines                  #
# ------------------------------------------------------------------ #


class TestRoundTripAnalysis:
    """Verify that a reconstructed schedule produces identical analysis results."""

    def _get_pair(self) -> tuple[ParsedSchedule, ParsedSchedule]:
        """Return (original, reconstructed) schedule pair."""
        store = MockSupabaseStore()
        original = _make_rich_schedule()
        store._insert(
            "projects",
            {
                "id": "proj-rt",
                "project_name": "RichProj",
                "data_date": "2026-01-15T00:00:00",
                "activity_count": 2,
            },
        )
        store._persist_schedule_data("proj-rt", original)
        reconstructed = store._reconstruct_from_db("proj-rt")
        assert reconstructed is not None
        return original, reconstructed

    def test_same_activity_ids(self) -> None:
        orig, recon = self._get_pair()
        orig_ids = {a.task_id for a in orig.activities}
        recon_ids = {a.task_id for a in recon.activities}
        assert orig_ids == recon_ids

    def test_same_relationship_structure(self) -> None:
        orig, recon = self._get_pair()
        orig_rels = {(r.task_id, r.pred_task_id, r.pred_type) for r in orig.relationships}
        recon_rels = {(r.task_id, r.pred_task_id, r.pred_type) for r in recon.relationships}
        assert orig_rels == recon_rels

    def test_same_wbs_hierarchy(self) -> None:
        orig, recon = self._get_pair()
        orig_wbs = {(w.wbs_id, w.parent_wbs_id, w.wbs_name) for w in orig.wbs_nodes}
        recon_wbs = {(w.wbs_id, w.parent_wbs_id, w.wbs_name) for w in recon.wbs_nodes}
        assert orig_wbs == recon_wbs

    def test_same_calendar_data(self) -> None:
        orig, recon = self._get_pair()
        assert len(orig.calendars) == len(recon.calendars)
        for o, r in zip(orig.calendars, recon.calendars):
            assert o.clndr_id == r.clndr_id
            assert o.day_hr_cnt == r.day_hr_cnt
            assert o.clndr_data == r.clndr_data


# ------------------------------------------------------------------ #
# Tests: SupabaseStore.get_cost_snapshot rehydration (Wave 5)        #
# ------------------------------------------------------------------ #


class TestCostSnapshotRehydration:
    """Verify save_cost_upload + get_cost_snapshot round-trip on Supabase backend."""

    def _snapshot(self) -> Any:
        from src.analytics.cost_integration import CBSElement, CostIntegrationResult

        return CostIntegrationResult(
            cbs_elements=[
                CBSElement(
                    cbs_code="C.SP.100",
                    cbs_level1="Construction",
                    cbs_level2="Structural",
                    scope="Foundations",
                    estimate=1_000_000.0,
                    contingency=250_000.0,
                    escalation=50_000.0,
                    budget=1_300_000.0,
                ),
                CBSElement(
                    cbs_code="C.EN.200",
                    cbs_level1="Engineering",
                    scope="Design",
                    estimate=500_000.0,
                    contingency=125_000.0,
                    escalation=25_000.0,
                    budget=650_000.0,
                ),
            ],
            total_budget=1_500_000.0,
            total_contingency=375_000.0,
            total_escalation=75_000.0,
            program_total=1_950_000.0,
            budget_date="2026-04-01",
        )

    def test_round_trip_preserves_budgets(self) -> None:
        store = MockSupabaseStore()
        original = self._snapshot()

        snapshot_id = store.save_cost_upload(
            project_id="p-rehydrate", result=original, source_name="Q2 Budget"
        )
        assert snapshot_id, "snapshot_id should be non-empty after save"

        recovered = store.get_cost_snapshot("p-rehydrate", snapshot_id)
        assert recovered is not None, "snapshot should rehydrate"

        assert len(recovered.cbs_elements) == 2
        codes = {e.cbs_code for e in recovered.cbs_elements}
        assert codes == {"C.SP.100", "C.EN.200"}

        by_code = {e.cbs_code: e for e in recovered.cbs_elements}
        assert by_code["C.SP.100"].estimate == 1_000_000.0
        assert by_code["C.SP.100"].contingency == 250_000.0
        assert by_code["C.SP.100"].escalation == 50_000.0
        assert by_code["C.SP.100"].budget == 1_300_000.0

    def test_round_trip_preserves_totals(self) -> None:
        store = MockSupabaseStore()
        original = self._snapshot()
        snapshot_id = store.save_cost_upload(
            project_id="p-totals", result=original, source_name="v1"
        )

        recovered = store.get_cost_snapshot("p-totals", snapshot_id)
        assert recovered is not None
        assert recovered.total_budget == 1_500_000.0
        assert recovered.total_contingency == 375_000.0
        assert recovered.total_escalation == 75_000.0
        assert recovered.budget_date == "2026-04-01"

    def test_missing_snapshot_returns_none(self) -> None:
        store = MockSupabaseStore()
        assert store.get_cost_snapshot("p-any", "nonexistent-snap-id") is None

    def test_wrong_project_id_returns_none(self) -> None:
        store = MockSupabaseStore()
        original = self._snapshot()
        snapshot_id = store.save_cost_upload(
            project_id="p-owner", result=original, source_name="v1"
        )
        assert store.get_cost_snapshot("p-other", snapshot_id) is None

    def test_compare_works_end_to_end_on_supabase(self) -> None:
        """Wave 1's compare_cost_snapshots should work through rehydration."""
        from src.analytics.cost_integration import (
            CBSElement,
            CostIntegrationResult,
            compare_cost_snapshots,
        )

        store = MockSupabaseStore()

        a = CostIntegrationResult(
            cbs_elements=[
                CBSElement(cbs_code="C.A.1", cbs_level1="Con", estimate=1000, budget=1200)
            ],
            total_budget=1_000_000,
            total_contingency=0,
            total_escalation=0,
        )
        b = CostIntegrationResult(
            cbs_elements=[
                CBSElement(cbs_code="C.A.1", cbs_level1="Con", estimate=1500, budget=1800)
            ],
            total_budget=1_500_000,
            total_contingency=0,
            total_escalation=0,
        )

        id_a = store.save_cost_upload(project_id="p-cmp", result=a, source_name="A")
        id_b = store.save_cost_upload(project_id="p-cmp", result=b, source_name="B")

        reh_a = store.get_cost_snapshot("p-cmp", id_a)
        reh_b = store.get_cost_snapshot("p-cmp", id_b)
        assert reh_a is not None and reh_b is not None

        result = compare_cost_snapshots(reh_a, reh_b, snapshot_a_id=id_a, snapshot_b_id=id_b)
        # Rehydrated totals are the sum of element estimates — not the input
        # ``total_budget`` (which is not persisted directly). Delta = 1500 - 1000.
        assert result.total_budget_delta == 500
        assert result.changed_count == 1
        assert result.budget_variance_pct == 50.0
