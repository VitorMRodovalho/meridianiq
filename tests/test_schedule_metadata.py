"""Tests for schedule metadata intelligence extraction."""

from __future__ import annotations

from datetime import datetime

from src.analytics.schedule_metadata import extract_metadata


class TestFilenameExtraction:
    """Extract update/revision/type from filename patterns."""

    def test_mps_standard(self) -> None:
        meta = extract_metadata("FDTP - MPS UP 08 Rev 00.xer")
        assert meta.update_number == 8
        assert meta.revision_number == 0
        assert meta.schedule_type == "mps"
        assert meta.is_draft is True
        assert meta.schedule_prefix == "FDTP"

    def test_mps_final_revision(self) -> None:
        meta = extract_metadata("FDTP - MPS UP 04 Rev 01 (FINAL).xer")
        assert meta.update_number == 4
        assert meta.revision_number == 1
        assert meta.is_final is True
        assert meta.is_draft is False

    def test_mps_prefix_change(self) -> None:
        meta = extract_metadata("BPTR - MPS UP 14 Rev 00.xer")
        assert meta.schedule_prefix == "BPTR"
        assert meta.update_number == 14
        assert meta.schedule_type == "mps"

    def test_draft_mps(self) -> None:
        meta = extract_metadata("FDTP- Draft MPS 01 Oct 24 Rev 00.xer")
        assert meta.is_draft is True
        assert meta.schedule_type == "mps"

    def test_ims_phase_pattern(self) -> None:
        meta = extract_metadata("BPT- Phase-1UP 06.xer")
        assert meta.update_number == 6
        assert meta.schedule_type == "ims"
        assert meta.schedule_prefix == "BPT"

    def test_ims_with_revision(self) -> None:
        meta = extract_metadata("BPT- Phase-1UP 01R1.xer")
        assert meta.update_number == 1
        assert meta.revision_number == 1

    def test_baseline_detection_from_name(self) -> None:
        meta = extract_metadata("BPT- Phase-1BL-2_Aug 2022MUDR2.xer")
        assert meta.is_baseline is True
        assert meta.schedule_type == "baseline"

    def test_baseline_bl4(self) -> None:
        meta = extract_metadata("BPT- Phase-1BL-4.xer")
        assert meta.is_baseline is True

    def test_cmar_gmp_pattern(self) -> None:
        meta = extract_metadata("23085Y1-FDT-GMP1-001.xer")
        assert meta.schedule_type == "cmar"

    def test_no_update_number(self) -> None:
        meta = extract_metadata("random_schedule.xer")
        assert meta.update_number is None
        assert meta.revision_number is None

    def test_data_date_extraction(self) -> None:
        dt = datetime(2025, 8, 1)
        meta = extract_metadata("test.xer", data_date=dt)
        assert meta.data_date == "2025-08-01"


class TestBaselineDetection:
    """Detect baseline dates from activity data."""

    def test_activities_with_baseline(self) -> None:
        class FakeAct:
            target_start_date = datetime(2025, 1, 1)

        meta = extract_metadata("test.xer", activities=[FakeAct(), FakeAct()])
        assert meta.has_baseline_dates is True
        assert meta.baseline_coverage_pct == 100.0

    def test_activities_partial_baseline(self) -> None:
        class WithBL:
            target_start_date = datetime(2025, 1, 1)

        class WithoutBL:
            target_start_date = None

        meta = extract_metadata(
            "test.xer", activities=[WithBL(), WithoutBL(), WithoutBL(), WithoutBL()]
        )
        assert meta.has_baseline_dates is True
        assert meta.baseline_coverage_pct == 25.0

    def test_no_baseline_dates(self) -> None:
        class NoBL:
            target_start_date = None

        meta = extract_metadata("test.xer", activities=[NoBL()])
        assert meta.has_baseline_dates is False
        assert meta.baseline_coverage_pct == 0.0


class TestScheduleOptions:
    """Extract scheduling options from raw XER tables."""

    def test_retained_logic(self) -> None:
        raw = {"SCHEDOPTIONS": [{"sched_retained_logic": "Y", "sched_progress_override": "N"}]}
        meta = extract_metadata("test.xer", raw_tables=raw)
        assert meta.retained_logic is True
        assert meta.progress_override is False

    def test_progress_override(self) -> None:
        raw = {"SCHEDOPTIONS": [{"sched_progress_override": "Y"}]}
        meta = extract_metadata("test.xer", raw_tables=raw)
        assert meta.progress_override is True

    def test_multiple_float_paths(self) -> None:
        raw = {"SCHEDOPTIONS": [{"enable_multiple_longest_path_calc": "Y"}]}
        meta = extract_metadata("test.xer", raw_tables=raw)
        assert meta.multiple_float_paths is True


class TestTags:
    """Verify tag generation."""

    def test_full_tags(self) -> None:
        class FakeAct:
            target_start_date = datetime(2025, 1, 1)

        raw = {"SCHEDOPTIONS": [{"sched_retained_logic": "Y"}]}
        meta = extract_metadata(
            "FDTP - MPS UP 08 Rev 00.xer",
            activities=[FakeAct()],
            raw_tables=raw,
        )
        assert "MPS" in meta.tags
        assert "UP#08" in meta.tags
        assert "Rev00" in meta.tags
        assert "DRAFT" in meta.tags
        assert "HAS_BL_DATES" in meta.tags
        assert "RETAINED_LOGIC" in meta.tags

    def test_final_tags(self) -> None:
        meta = extract_metadata("FDTP - MPS UP 04 Rev 01 (FINAL).xer")
        assert "FINAL" in meta.tags
        assert "DRAFT" not in meta.tags

    def test_baseline_tag(self) -> None:
        meta = extract_metadata("BPT- Phase-1BL-4.xer")
        assert "BASELINE" in meta.tags

    def test_project_name_fallback(self) -> None:
        meta = extract_metadata("file.xer", project_name="BPTR - MPS UP 18 Rev 00")
        assert meta.update_number == 18
        assert meta.schedule_type == "mps"
