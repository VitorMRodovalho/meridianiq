# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the XER validator module."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.parser import XERReader, ParsedSchedule, XERValidator, ValidationResult

SAMPLE_XER = Path(__file__).parent / "fixtures" / "sample.xer"


@pytest.fixture
def schedule() -> ParsedSchedule:
    reader = XERReader(SAMPLE_XER)
    return reader.parse()


@pytest.fixture
def result(schedule: ParsedSchedule) -> ValidationResult:
    validator = XERValidator(schedule)
    return validator.validate()


class TestOpenEndsDetected:
    """Verify that open-start and open-finish activities are flagged."""

    def test_open_starts_exist(self, result: ValidationResult) -> None:
        open_start_issues = [
            i for i in result.issues
            if "Open start" in i.message
        ]
        assert len(open_start_issues) > 0

    def test_open_finishes_exist(self, result: ValidationResult) -> None:
        open_finish_issues = [
            i for i in result.issues
            if "Open finish" in i.message
        ]
        assert len(open_finish_issues) > 0

    def test_open_end_counts(self, result: ValidationResult) -> None:
        assert result.open_start_count > 0
        assert result.open_finish_count > 0


class TestConstraintsDetected:
    """Verify constrained activities are flagged."""

    def test_constraints_found(self, result: ValidationResult) -> None:
        constraint_issues = [
            i for i in result.issues
            if "Constraint" in i.message
        ]
        assert len(constraint_issues) >= 2  # T-026, T-028

    def test_constrained_count(self, result: ValidationResult) -> None:
        assert result.constrained_count >= 2


class TestActivityCounts:
    """Verify status and type counts in summary."""

    def test_activity_count(self, result: ValidationResult) -> None:
        assert result.activity_count == 30

    def test_relationship_count(self, result: ValidationResult) -> None:
        assert result.relationship_count == 40

    def test_status_counts_in_summary(self, result: ValidationResult) -> None:
        sc = result.summary["status_counts"]
        assert sc["TK_Complete"] == 15
        assert sc["TK_Active"] == 5
        assert sc["TK_NotStart"] == 10

    def test_type_counts_in_summary(self, result: ValidationResult) -> None:
        tc = result.summary["type_counts"]
        assert tc["TT_Task"] == 24
        assert tc["TT_mile"] == 3
        assert tc["TT_finmile"] == 2
        assert tc["TT_LOE"] == 1


class TestRelationshipCounts:
    """Verify relationship type counts in summary."""

    def test_relationship_types_in_summary(self, result: ValidationResult) -> None:
        rt = result.summary["relationship_types"]
        assert rt["PR_FS"] == 35
        assert rt["PR_SS"] == 2
        assert rt["PR_FF"] == 3


class TestEmptyScheduleValidation:
    """Verify validator handles an empty schedule."""

    def test_empty_schedule_invalid(self) -> None:
        schedule = ParsedSchedule()
        validator = XERValidator(schedule)
        result = validator.validate()
        assert result.is_valid is False
        error_msgs = [i.message for i in result.issues if i.severity == "error"]
        assert any("PROJECT" in m for m in error_msgs)
        assert any("TASK" in m for m in error_msgs)
