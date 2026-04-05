# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Custom MIT-licensed Oracle P6 XER file parser.

Reads Oracle Primavera P6 XER export files and converts them into typed
Python objects using Pydantic models.  The parser handles encoding
detection, date format variations, and gracefully skips malformed rows.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import (
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
    XERHeader,
)

logger = logging.getLogger(__name__)

# Map XER table names to (model class, ParsedSchedule field name)
TABLE_MAP: dict[str, tuple[type[Any], str]] = {
    "PROJECT": (Project, "projects"),
    "CALENDAR": (Calendar, "calendars"),
    "PROJWBS": (WBS, "wbs_nodes"),
    "TASK": (Task, "activities"),
    "TASKPRED": (Relationship, "relationships"),
    "RSRC": (Resource, "resources"),
    "TASKRSRC": (TaskResource, "task_resources"),
    "ACTVCODE": (ActivityCode, "activity_codes"),
    "ACTVTYPE": (ActivityCodeType, "activity_code_types"),
    "TASKACTV": (TaskActivityCode, "task_activity_codes"),
    "UDFTYPE": (UDFType, "udf_types"),
    "UDFVALUE": (UDFValue, "udf_values"),
    "FINDATES": (FinancialPeriod, "financial_periods"),
    "TASKFIN": (TaskFinancial, "task_financials"),
}

ENCODINGS: list[str] = ["utf-8", "windows-1252", "latin-1", "iso-8859-1"]

# Common P6 date formats ordered from most to least common
DATE_FORMATS: list[str] = [
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
    "%d-%b-%y %H:%M",
    "%d-%b-%Y %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
]

# Fields in models that hold datetime values
_DATE_FIELD_NAMES: set[str] = {
    "last_recalc_date",
    "plan_start_date",
    "plan_end_date",
    "scd_end_date",
    "sum_data_date",
    "last_tasksum_date",
    "fcst_start_date",
    "act_start_date",
    "act_end_date",
    "early_start_date",
    "early_end_date",
    "late_start_date",
    "late_end_date",
    "target_start_date",
    "target_end_date",
    "restart_date",
    "reend_date",
    "cstr_date",
    "cstr_date2",
    "start_date",
    "end_date",
    "udf_date",
}

# Fields that hold float values
_FLOAT_FIELD_NAMES: set[str] = {
    "day_hr_cnt",
    "week_hr_cnt",
    "total_float_hr_cnt",
    "free_float_hr_cnt",
    "remain_drtn_hr_cnt",
    "target_drtn_hr_cnt",
    "phys_complete_pct",
    "act_work_qty",
    "remain_work_qty",
    "target_work_qty",
    "act_equip_qty",
    "remain_equip_qty",
    "target_equip_qty",
    "lag_hr_cnt",
    "target_qty",
    "act_reg_qty",
    "remain_qty",
    "target_cost",
    "act_reg_cost",
    "remain_cost",
    "act_cost",
    "udf_number",
}

# Fields that hold int values
_INT_FIELD_NAMES: set[str] = {
    "seq_num",
    "float_path",
    "float_path_order",
}


class XERReader:
    """Parse Oracle P6 XER files into structured Python objects.

    Usage::

        reader = XERReader("schedule.xer")
        schedule = reader.parse()
        print(schedule.projects[0].proj_short_name)
    """

    def __init__(self, file_path: str | Path) -> None:
        """Initialise the reader with a path to an XER file.

        Args:
            file_path: Path to the .xer file.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"XER file not found: {self.file_path}")
        self._encoding: str = "utf-8"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self) -> ParsedSchedule:
        """Parse the XER file and return a ``ParsedSchedule`` object.

        Returns:
            A fully populated ``ParsedSchedule`` with all recognised tables
            mapped to Pydantic models and unrecognised tables stored in
            ``raw_tables``.
        """
        lines = self._read_lines()
        schedule = ParsedSchedule()

        current_table: str | None = None
        current_fields: list[str] = []

        for line_num, line in enumerate(lines, 1):
            line = line.rstrip("\n\r")
            if not line:
                continue

            parts = line.split("\t")
            record_type = parts[0] if parts else ""

            if record_type == "ERMHDR":
                schedule.header = self._parse_header(parts)
            elif record_type == "%T":
                current_table = parts[1].strip() if len(parts) > 1 else None
            elif record_type == "%F":
                current_fields = [f.strip() for f in parts[1:]]
            elif record_type == "%R" and current_table and current_fields:
                values = parts[1:]
                row_dict = self._build_row_dict(current_fields, values)
                self._add_record(schedule, current_table, row_dict, line_num)
            elif record_type == "%E":
                break  # end of file marker

        # Post-processing: generate composite keys
        self._generate_composite_keys(schedule)

        return schedule

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_lines(self) -> list[str]:
        """Read file with encoding detection.

        Tries each encoding in ``ENCODINGS`` until one succeeds. Falls back
        to UTF-8 with ``errors='replace'`` as a last resort.

        Returns:
            List of raw text lines from the file.
        """
        for encoding in ENCODINGS:
            try:
                with open(self.file_path, encoding=encoding) as fh:
                    lines = fh.readlines()
                self._encoding = encoding
                logger.debug("Read %s with encoding %s", self.file_path, encoding)
                return lines
            except UnicodeDecodeError, UnicodeError:
                continue

        # Last resort: replace bad characters
        logger.warning("All preferred encodings failed; using utf-8 with error replacement")
        with open(self.file_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        self._encoding = "utf-8"
        return lines

    def _parse_header(self, parts: list[str]) -> XERHeader:
        """Parse ERMHDR line into an ``XERHeader`` model.

        The ERMHDR line typically has the structure::

            ERMHDR <version> <date_format> <currency> <filename> <user> <date>

        Args:
            parts: Tab-split segments of the ERMHDR line.

        Returns:
            Populated ``XERHeader`` instance.
        """
        header = XERHeader()
        if len(parts) > 1:
            header.version = parts[1].strip()
        if len(parts) > 2:
            header.date_format = parts[2].strip()
        if len(parts) > 3:
            header.currency_name = parts[3].strip()
        if len(parts) > 4:
            header.file_name = parts[4].strip()
        if len(parts) > 5:
            header.user_name = parts[5].strip()
        if len(parts) > 6:
            header.export_date = parts[6].strip()
        return header

    def _build_row_dict(self, fields: list[str], values: list[str]) -> dict[str, str]:
        """Build a field-to-value dictionary, handling mismatched lengths.

        If there are fewer values than fields the missing entries are set to
        empty strings.  Extra values beyond the field list are silently
        discarded.

        Args:
            fields: Column names from the ``%F`` row.
            values: Cell values from the ``%R`` row.

        Returns:
            Dictionary mapping field names to string values.
        """
        row: dict[str, str] = {}
        for idx, field_name in enumerate(fields):
            if idx < len(values):
                row[field_name] = values[idx].strip()
            else:
                row[field_name] = ""
        return row

    def _parse_date(self, value: str) -> datetime | None:
        """Try multiple date formats and return a datetime or ``None``.

        Args:
            value: Raw date string from the XER file.

        Returns:
            Parsed ``datetime`` or ``None`` if the value is empty or no
            format matches.
        """
        if not value or not value.strip():
            return None
        value = value.strip()
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        logger.warning("Unable to parse date: '%s'", value)
        return None

    def _coerce_row(self, row: dict[str, str], model_cls: type[Any]) -> dict[str, Any]:
        """Convert raw string values to the types expected by *model_cls*.

        Handles date parsing, float/int conversion, and maps empty strings
        to ``None`` for ``Optional`` fields.

        Args:
            row: Raw string-keyed dictionary.
            model_cls: The Pydantic model class the row will be fed into.

        Returns:
            Dictionary with values coerced to appropriate Python types.
        """
        model_fields = model_cls.model_fields
        coerced: dict[str, Any] = {}
        for key, raw_value in row.items():
            if key not in model_fields:
                continue

            if key in _DATE_FIELD_NAMES:
                coerced[key] = self._parse_date(raw_value)
            elif key in _FLOAT_FIELD_NAMES:
                coerced[key] = self._parse_float(raw_value)
            elif key in _INT_FIELD_NAMES:
                coerced[key] = self._parse_int(raw_value)
            else:
                # For optional string fields, map "" -> None not needed;
                # Pydantic default handles it. Keep raw string.
                coerced[key] = raw_value
        return coerced

    @staticmethod
    def _parse_float(value: str) -> float | None:
        """Safely parse a string to float."""
        if not value or not value.strip():
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_int(value: str) -> int | None:
        """Safely parse a string to int."""
        if not value or not value.strip():
            return None
        try:
            return int(float(value))
        except ValueError:
            return None

    def _add_record(
        self,
        schedule: ParsedSchedule,
        table_name: str,
        row: dict[str, str],
        line_num: int,
    ) -> None:
        """Add a parsed row to the appropriate list in the schedule.

        If the table is recognised (present in ``TABLE_MAP``), the row is
        coerced and converted into the corresponding Pydantic model.
        Otherwise it is stored as a raw dictionary in ``raw_tables``.

        Args:
            schedule: The target schedule being built.
            table_name: XER table name (e.g. ``"TASK"``).
            row: Field-value dictionary for one row.
            line_num: Source line number for error reporting.
        """
        if table_name in TABLE_MAP:
            model_cls, field_name = TABLE_MAP[table_name]
            coerced = self._coerce_row(row, model_cls)
            try:
                record = model_cls(**coerced)
                getattr(schedule, field_name).append(record)
            except (ValidationError, TypeError) as exc:
                logger.warning("Skipping %s row at line %d: %s", table_name, line_num, exc)
        else:
            # Store in raw_tables
            if table_name not in schedule.raw_tables:
                schedule.raw_tables[table_name] = []
                if table_name not in schedule.unmapped_tables:
                    schedule.unmapped_tables.append(table_name)
            schedule.raw_tables[table_name].append(row)

    @staticmethod
    def _generate_composite_keys(schedule: ParsedSchedule) -> None:
        """Generate ``proj_id.task_id`` composite keys for multi-project support.

        This makes task lookups unique across projects when a single XER
        file contains more than one project.

        Args:
            schedule: The parsed schedule to post-process.
        """
        for task in schedule.activities:
            task.task_id_key = f"{task.proj_id}.{task.task_id}"
