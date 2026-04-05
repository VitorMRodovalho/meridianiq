# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the XER writer — round-trip and generation export."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.export.xer_writer import XERWriter
from src.parser.models import (
    Calendar,
    ParsedSchedule,
    Project,
    Relationship,
    Task,
)
from src.parser.xer_reader import XERReader

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def real_schedule() -> ParsedSchedule:
    return XERReader(FIXTURES / "sample.xer").parse()


def _make_schedule() -> ParsedSchedule:
    return ParsedSchedule(
        projects=[
            Project(
                proj_id="P1",
                proj_short_name="Test Export",
                plan_start_date=datetime(2025, 1, 1),
                sum_data_date=datetime(2025, 3, 1),
                last_recalc_date=datetime(2025, 3, 1),
            )
        ],
        calendars=[Calendar(clndr_id="CAL1", day_hr_cnt=8.0, week_hr_cnt=40.0)],
        activities=[
            Task(
                task_id="1",
                task_code="A",
                task_name="Foundation",
                status_code="TK_Active",
                remain_drtn_hr_cnt=80.0,
                target_drtn_hr_cnt=80.0,
                total_float_hr_cnt=0.0,
                clndr_id="CAL1",
                act_start_date=datetime(2025, 1, 1),
            ),
            Task(
                task_id="2",
                task_code="B",
                task_name="Structure",
                status_code="TK_NotStart",
                remain_drtn_hr_cnt=160.0,
                target_drtn_hr_cnt=160.0,
                total_float_hr_cnt=40.0,
                clndr_id="CAL1",
            ),
        ],
        relationships=[
            Relationship(task_id="2", pred_task_id="1", pred_type="PR_FS"),
        ],
    )


class TestXERWriter:
    def test_write_returns_string(self) -> None:
        schedule = _make_schedule()
        writer = XERWriter(schedule)
        content = writer.write()
        assert isinstance(content, str)
        assert len(content) > 0

    def test_has_header(self) -> None:
        schedule = _make_schedule()
        content = XERWriter(schedule).write()
        assert content.startswith("ERMHDR")

    def test_has_end_marker(self) -> None:
        schedule = _make_schedule()
        content = XERWriter(schedule).write()
        assert content.strip().endswith("%E")

    def test_has_project_table(self) -> None:
        schedule = _make_schedule()
        content = XERWriter(schedule).write()
        assert "%T\tPROJECT" in content
        assert "%F\t" in content
        assert "Test Export" in content

    def test_has_task_table(self) -> None:
        schedule = _make_schedule()
        content = XERWriter(schedule).write()
        assert "%T\tTASK" in content
        assert "Foundation" in content
        assert "Structure" in content

    def test_has_relationship_table(self) -> None:
        schedule = _make_schedule()
        content = XERWriter(schedule).write()
        assert "%T\tTASKPRED" in content

    def test_has_calendar_table(self) -> None:
        schedule = _make_schedule()
        content = XERWriter(schedule).write()
        assert "%T\tCALENDAR" in content

    def test_dates_formatted(self) -> None:
        schedule = _make_schedule()
        content = XERWriter(schedule).write()
        assert "2025-01-01" in content

    def test_empty_schedule(self) -> None:
        schedule = ParsedSchedule()
        content = XERWriter(schedule).write()
        assert "ERMHDR" in content
        assert "%E" in content


class TestRoundTrip:
    def test_round_trip_activity_count(self, real_schedule: ParsedSchedule) -> None:
        """Write then re-parse should preserve activity count."""
        content = XERWriter(real_schedule).write()
        # Write to temp and re-parse
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xer", delete=False) as f:
            f.write(content)
            f.flush()
            reparsed = XERReader(f.name).parse()
        assert len(reparsed.activities) == len(real_schedule.activities)

    def test_round_trip_project_name(self, real_schedule: ParsedSchedule) -> None:
        content = XERWriter(real_schedule).write()
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xer", delete=False) as f:
            f.write(content)
            f.flush()
            reparsed = XERReader(f.name).parse()
        assert reparsed.projects[0].proj_short_name == real_schedule.projects[0].proj_short_name

    def test_round_trip_relationship_count(self, real_schedule: ParsedSchedule) -> None:
        content = XERWriter(real_schedule).write()
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xer", delete=False) as f:
            f.write(content)
            f.flush()
            reparsed = XERReader(f.name).parse()
        assert len(reparsed.relationships) == len(real_schedule.relationships)

    def test_round_trip_cpm_consistent(self, real_schedule: ParsedSchedule) -> None:
        """CPM on round-tripped schedule should match original."""
        from src.analytics.cpm import CPMCalculator

        orig_cpm = CPMCalculator(real_schedule).calculate()

        content = XERWriter(real_schedule).write()
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xer", delete=False) as f:
            f.write(content)
            f.flush()
            reparsed = XERReader(f.name).parse()

        new_cpm = CPMCalculator(reparsed).calculate()
        # Duration should be within 1% (float precision)
        if orig_cpm.project_duration > 0:
            diff_pct = (
                abs(new_cpm.project_duration - orig_cpm.project_duration)
                / orig_cpm.project_duration
            )
            assert diff_pct < 0.01


class TestGeneratedScheduleExport:
    def test_export_generated_schedule(self) -> None:
        """Generated schedules should be exportable to XER."""
        from src.analytics.schedule_generation import GenerationInput, generate_schedule

        gen = generate_schedule(GenerationInput(project_type="commercial"))
        content = XERWriter(gen.parsed_schedule).write()
        assert "%T\tTASK" in content
        assert len(content) > 100

    def test_generated_round_trip(self) -> None:
        """Generated → XER → parse → CPM should work."""
        from src.analytics.cpm import CPMCalculator
        from src.analytics.schedule_generation import GenerationInput, generate_schedule

        gen = generate_schedule(GenerationInput(project_type="industrial"))
        content = XERWriter(gen.parsed_schedule).write()

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xer", delete=False) as f:
            f.write(content)
            f.flush()
            reparsed = XERReader(f.name).parse()

        cpm = CPMCalculator(reparsed).calculate()
        assert not cpm.has_cycles
        assert cpm.project_duration > 0
