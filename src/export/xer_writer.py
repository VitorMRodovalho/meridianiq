# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Oracle P6 XER file writer.

Writes a ParsedSchedule back to XER format for import into Primavera P6.
Supports writing original, modified (post what-if / post-leveling), and
generated schedules.

XER format structure:
    ERMHDR\t...\t                    (file header)
    %T\tTABLE_NAME                   (table start)
    %F\tfield1\tfield2\t...          (field names)
    %R\tval1\tval2\t...              (data row)
    ...
    %E                               (end of file)

References:
    - Oracle Primavera P6 XER Format (de facto standard)
"""

from __future__ import annotations

import logging
from datetime import datetime
from io import StringIO
from typing import Any

from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)

# Date format for XER output (most common P6 format)
_XER_DATE_FORMAT = "%Y-%m-%d %H:%M"

# Table writing order (P6 expects dependencies before dependents)
_TABLE_ORDER = [
    "CURRTYPE",
    "PROJECT",
    "CALENDAR",
    "PROJWBS",
    "RSRC",
    "ACTVTYPE",
    "ACTVCODE",
    "TASK",
    "TASKPRED",
    "TASKRSRC",
    "TASKACTV",
    "UDFTYPE",
    "UDFVALUE",
    "FINDATES",
    "TASKFIN",
]

# Mapping: (table_name, field_names, schedule_attribute, field_extractors)
_TABLE_DEFS: list[tuple[str, list[str], str, list[str]]] = [
    (
        "PROJECT",
        [
            "proj_id",
            "proj_short_name",
            "plan_start_date",
            "plan_end_date",
            "scd_end_date",
            "sum_data_date",
            "last_recalc_date",
        ],
        "projects",
        [],
    ),
    (
        "CALENDAR",
        ["clndr_id", "clndr_name", "day_hr_cnt", "week_hr_cnt", "clndr_type", "default_flag"],
        "calendars",
        [],
    ),
    (
        "PROJWBS",
        ["wbs_id", "proj_id", "obs_id", "seq_num", "wbs_short_name", "wbs_name", "parent_wbs_id"],
        "wbs_nodes",
        [],
    ),
    (
        "TASK",
        [
            "task_id",
            "proj_id",
            "wbs_id",
            "clndr_id",
            "task_code",
            "task_name",
            "task_type",
            "status_code",
            "total_float_hr_cnt",
            "free_float_hr_cnt",
            "remain_drtn_hr_cnt",
            "target_drtn_hr_cnt",
            "phys_complete_pct",
            "act_start_date",
            "act_end_date",
            "early_start_date",
            "early_end_date",
            "late_start_date",
            "late_end_date",
            "target_start_date",
            "target_end_date",
            "cstr_type",
            "cstr_date",
        ],
        "activities",
        [],
    ),
    (
        "TASKPRED",
        ["task_pred_id", "task_id", "pred_task_id", "pred_type", "lag_hr_cnt"],
        "relationships",
        [],
    ),
    (
        "RSRC",
        ["rsrc_id", "rsrc_name", "rsrc_type"],
        "resources",
        [],
    ),
    (
        "TASKRSRC",
        [
            "taskrsrc_id",
            "task_id",
            "rsrc_id",
            "proj_id",
            "target_qty",
            "act_reg_qty",
            "remain_qty",
            "target_cost",
            "act_reg_cost",
            "remain_cost",
        ],
        "task_resources",
        [],
    ),
]

# Date fields that need formatting
_DATE_FIELDS = {
    "plan_start_date",
    "plan_end_date",
    "scd_end_date",
    "sum_data_date",
    "last_recalc_date",
    "act_start_date",
    "act_end_date",
    "early_start_date",
    "early_end_date",
    "late_start_date",
    "late_end_date",
    "target_start_date",
    "target_end_date",
    "cstr_date",
    "cstr_date2",
    "start_date",
    "end_date",
    "udf_date",
}


def _format_value(value: Any, field_name: str) -> str:
    """Format a value for XER output."""
    if value is None:
        return ""
    if field_name in _DATE_FIELDS:
        if isinstance(value, datetime):
            return value.strftime(_XER_DATE_FORMAT)
        return str(value) if value else ""
    if isinstance(value, float):
        # Avoid unnecessary decimals
        if value == int(value):
            return str(int(value))
        return f"{value:.6g}"
    if isinstance(value, bool):
        return "Y" if value else "N"
    return str(value)


def _extract_field(obj: Any, field_name: str) -> Any:
    """Extract a field value from a Pydantic model or dict."""
    if isinstance(obj, dict):
        return obj.get(field_name, "")
    return getattr(obj, field_name, "")


class XERWriter:
    """Write a ParsedSchedule to XER format.

    Usage::

        writer = XERWriter(schedule)
        xer_content = writer.write()
        Path("output.xer").write_text(xer_content)

    References:
        Oracle Primavera P6 XER Format Specification.
    """

    def __init__(self, schedule: ParsedSchedule) -> None:
        self.schedule = schedule

    def write(self) -> str:
        """Write the schedule to XER format string.

        Returns:
            Complete XER file content as a string.
        """
        buf = StringIO()

        # Header
        header = self.schedule.header
        buf.write(
            f"ERMHDR\t{header.version or '18.8.0.0'}\t"
            f"{header.date_format or _XER_DATE_FORMAT}\t"
            f"{header.currency_name or 'USD'}\t"
            f"{header.file_name or 'export'}\t"
            f"{header.user_name or 'MeridianIQ'}\t"
            f"{datetime.now().strftime(_XER_DATE_FORMAT)}\n"
        )

        # Write known tables
        for table_name, fields, attr_name, _ in _TABLE_DEFS:
            records = getattr(self.schedule, attr_name, [])
            if not records:
                continue
            self._write_table(buf, table_name, fields, records)

        # Write raw (unmodeled) tables for round-trip fidelity
        for table_name, rows in self.schedule.raw_tables.items():
            # Skip tables we already wrote from models
            if table_name in {td[0] for td in _TABLE_DEFS}:
                continue
            if not rows:
                continue
            fields = list(rows[0].keys())
            buf.write(f"%T\t{table_name}\n")
            buf.write("%F\t" + "\t".join(fields) + "\n")
            for row in rows:
                vals = [_format_value(row.get(f, ""), f) for f in fields]
                buf.write("%R\t" + "\t".join(vals) + "\n")

        # End marker
        buf.write("%E\n")

        return buf.getvalue()

    def write_to_file(self, path: str) -> None:
        """Write the schedule to an XER file.

        Args:
            path: Output file path.
        """
        from pathlib import Path as P

        content = self.write()
        P(path).write_text(content, encoding="utf-8")

    def _write_table(
        self,
        buf: StringIO,
        table_name: str,
        fields: list[str],
        records: list[Any],
    ) -> None:
        """Write a single table to the buffer."""
        buf.write(f"%T\t{table_name}\n")
        buf.write("%F\t" + "\t".join(fields) + "\n")

        for record in records:
            vals = [_format_value(_extract_field(record, f), f) for f in fields]
            buf.write("%R\t" + "\t".join(vals) + "\n")
