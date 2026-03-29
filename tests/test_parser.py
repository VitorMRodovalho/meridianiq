# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the XER parser module."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.parser import XERReader, ParsedSchedule

SAMPLE_XER = Path(__file__).parent / "fixtures" / "sample.xer"


@pytest.fixture
def schedule() -> ParsedSchedule:
    """Parse the sample XER once for reuse across tests."""
    reader = XERReader(SAMPLE_XER)
    return reader.parse()


class TestParseValidXER:
    """Tests against the generated sample.xer fixture."""

    def test_parse_returns_schedule(self, schedule: ParsedSchedule) -> None:
        assert isinstance(schedule, ParsedSchedule)

    def test_activity_count(self, schedule: ParsedSchedule) -> None:
        assert len(schedule.activities) == 30

    def test_relationship_count(self, schedule: ParsedSchedule) -> None:
        assert len(schedule.relationships) == 40

    def test_wbs_count(self, schedule: ParsedSchedule) -> None:
        assert len(schedule.wbs_nodes) == 10

    def test_calendar_count(self, schedule: ParsedSchedule) -> None:
        assert len(schedule.calendars) == 2

    def test_resource_count(self, schedule: ParsedSchedule) -> None:
        assert len(schedule.resources) == 3

    def test_task_resource_count(self, schedule: ParsedSchedule) -> None:
        assert len(schedule.task_resources) == 10

    def test_project_count(self, schedule: ParsedSchedule) -> None:
        assert len(schedule.projects) == 1


class TestParseHeader:
    """Tests for ERMHDR parsing."""

    def test_header_version(self, schedule: ParsedSchedule) -> None:
        assert schedule.header.version == "22.0"

    def test_header_date_format(self, schedule: ParsedSchedule) -> None:
        assert schedule.header.date_format == "yyyy-mm-dd"

    def test_header_currency(self, schedule: ParsedSchedule) -> None:
        assert schedule.header.currency_name == "USD"

    def test_header_user(self, schedule: ParsedSchedule) -> None:
        assert schedule.header.user_name == "admin"


class TestParseProjects:
    """Tests for PROJECT table parsing."""

    def test_project_id(self, schedule: ParsedSchedule) -> None:
        proj = schedule.projects[0]
        assert proj.proj_id == "PROJ-001"

    def test_project_short_name(self, schedule: ParsedSchedule) -> None:
        proj = schedule.projects[0]
        assert proj.proj_short_name == "Sample Construction"

    def test_project_data_date(self, schedule: ParsedSchedule) -> None:
        proj = schedule.projects[0]
        assert proj.last_recalc_date is not None
        assert proj.last_recalc_date.year == 2024
        assert proj.last_recalc_date.month == 6
        assert proj.last_recalc_date.day == 1

    def test_project_plan_dates(self, schedule: ParsedSchedule) -> None:
        proj = schedule.projects[0]
        assert proj.plan_start_date is not None
        assert proj.plan_end_date is not None


class TestParseActivities:
    """Tests for TASK table parsing."""

    def test_activity_types(self, schedule: ParsedSchedule) -> None:
        type_counts: dict[str, int] = {}
        for t in schedule.activities:
            type_counts[t.task_type] = type_counts.get(t.task_type, 0) + 1
        assert type_counts["TT_Task"] == 24
        assert type_counts["TT_mile"] == 3
        assert type_counts["TT_finmile"] == 2
        assert type_counts["TT_LOE"] == 1

    def test_activity_statuses(self, schedule: ParsedSchedule) -> None:
        status_counts: dict[str, int] = {}
        for t in schedule.activities:
            status_counts[t.status_code] = status_counts.get(t.status_code, 0) + 1
        assert status_counts["TK_Complete"] == 15
        assert status_counts["TK_Active"] == 5
        assert status_counts["TK_NotStart"] == 10

    def test_first_activity_fields(self, schedule: ParsedSchedule) -> None:
        t = schedule.activities[0]
        assert t.task_id == "T-001"
        assert t.task_code == "A1000"
        assert t.task_name == "Project Start"
        assert t.task_type == "TT_mile"
        assert t.status_code == "TK_Complete"
        assert t.phys_complete_pct == 100.0

    def test_activity_dates_parsed(self, schedule: ParsedSchedule) -> None:
        t = schedule.activities[0]
        assert t.act_start_date is not None
        assert isinstance(t.act_start_date, datetime)

    def test_float_values_parsed(self, schedule: ParsedSchedule) -> None:
        # T-004 has total_float_hr_cnt = 40
        t004 = next(t for t in schedule.activities if t.task_id == "T-004")
        assert t004.total_float_hr_cnt == 40.0

    def test_constraint_fields(self, schedule: ParsedSchedule) -> None:
        # T-026 has CS_MSO constraint
        t026 = next(t for t in schedule.activities if t.task_id == "T-026")
        assert t026.cstr_type == "CS_MSO"
        assert t026.cstr_date is not None


class TestParseRelationships:
    """Tests for TASKPRED table parsing."""

    def test_relationship_types(self, schedule: ParsedSchedule) -> None:
        type_counts: dict[str, int] = {}
        for r in schedule.relationships:
            type_counts[r.pred_type] = type_counts.get(r.pred_type, 0) + 1
        assert type_counts["PR_FS"] == 35
        assert type_counts["PR_SS"] == 2
        assert type_counts["PR_FF"] == 3

    def test_relationship_fields(self, schedule: ParsedSchedule) -> None:
        rel = schedule.relationships[0]
        assert rel.task_pred_id == "TP-001"
        assert rel.task_id == "T-002"  # successor
        assert rel.pred_task_id == "T-001"  # predecessor
        assert rel.pred_type == "PR_FS"
        assert rel.lag_hr_cnt == 0.0


class TestParseWBSHierarchy:
    """Tests for PROJWBS table parsing."""

    def test_root_node(self, schedule: ParsedSchedule) -> None:
        root = next(w for w in schedule.wbs_nodes if w.proj_node_flag == "Y")
        assert root.wbs_id == "WBS-001"
        assert root.wbs_short_name == "PROJ"

    def test_child_nodes(self, schedule: ParsedSchedule) -> None:
        children = [w for w in schedule.wbs_nodes if w.parent_wbs_id == "WBS-001"]
        assert len(children) == 5

    def test_grandchild_nodes(self, schedule: ParsedSchedule) -> None:
        grandchildren = [w for w in schedule.wbs_nodes if w.parent_wbs_id == "WBS-020"]
        assert len(grandchildren) == 2  # EXCAV, CONC


class TestCompositeKeys:
    """Tests for multi-project composite key generation."""

    def test_composite_key_format(self, schedule: ParsedSchedule) -> None:
        t = schedule.activities[0]
        assert t.task_id_key == "PROJ-001.T-001"

    def test_all_activities_have_keys(self, schedule: ParsedSchedule) -> None:
        for t in schedule.activities:
            assert t.task_id_key
            assert "." in t.task_id_key


class TestMissingOptionalTable:
    """Test that the parser handles missing optional tables gracefully."""

    def test_parse_minimal_xer(self) -> None:
        """An XER with only a header and PROJECT table should parse."""
        content = (
            "ERMHDR\t22.0\tyyyy-mm-dd\tUSD\ttest.xer\tadmin\t2024-01-01\n"
            "%T\tPROJECT\n"
            "%F\tproj_id\tproj_short_name\n"
            "%R\tP1\tTest Project\n"
            "%E\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xer", delete=False) as f:
            f.write(content)
            f.flush()
            reader = XERReader(f.name)
            schedule = reader.parse()

        assert len(schedule.projects) == 1
        assert len(schedule.activities) == 0
        assert len(schedule.resources) == 0
        assert len(schedule.relationships) == 0


class TestEmptyFile:
    """Test that the parser handles empty or invalid files."""

    def test_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xer", delete=False) as f:
            f.write("")
            f.flush()
            reader = XERReader(f.name)
            schedule = reader.parse()

        assert len(schedule.activities) == 0
        assert len(schedule.projects) == 0

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            XERReader("/nonexistent/file.xer")

    def test_header_only(self) -> None:
        content = "ERMHDR\t22.0\tyyyy-mm-dd\tUSD\n%E\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xer", delete=False) as f:
            f.write(content)
            f.flush()
            reader = XERReader(f.name)
            schedule = reader.parse()

        assert schedule.header.version == "22.0"
        assert len(schedule.activities) == 0


class TestDateParsing:
    """Tests for various date format handling."""

    def test_yyyy_mm_dd_hhmm(self, schedule: ParsedSchedule) -> None:
        """Standard P6 format: 2024-01-02 08:00."""
        t = schedule.activities[0]
        assert t.act_start_date is not None
        assert t.act_start_date == datetime(2024, 1, 2, 8, 0)

    def test_none_for_empty_dates(self, schedule: ParsedSchedule) -> None:
        """Not-started activities should have None for actual dates."""
        t021 = next(t for t in schedule.activities if t.task_id == "T-021")
        assert t021.act_start_date is None
        assert t021.act_end_date is None

    def test_alternative_date_format(self) -> None:
        """Test that mm/dd/yyyy format is also supported."""
        content = (
            "ERMHDR\t22.0\n"
            "%T\tPROJECT\n"
            "%F\tproj_id\tproj_short_name\tplan_start_date\n"
            "%R\tP1\tTest\t01/15/2024 08:00\n"
            "%E\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xer", delete=False) as f:
            f.write(content)
            f.flush()
            reader = XERReader(f.name)
            schedule = reader.parse()

        assert schedule.projects[0].plan_start_date == datetime(2024, 1, 15, 8, 0)


class TestUnmappedTables:
    """Test that unrecognised tables are stored in raw_tables."""

    def test_unmapped_table_captured(self) -> None:
        content = "ERMHDR\t22.0\n%T\tCUSTOMTABLE\n%F\tcol_a\tcol_b\n%R\tval1\tval2\n%E\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xer", delete=False) as f:
            f.write(content)
            f.flush()
            reader = XERReader(f.name)
            schedule = reader.parse()

        assert "CUSTOMTABLE" in schedule.raw_tables
        assert len(schedule.raw_tables["CUSTOMTABLE"]) == 1
        assert schedule.raw_tables["CUSTOMTABLE"][0]["col_a"] == "val1"
        assert "CUSTOMTABLE" in schedule.unmapped_tables
