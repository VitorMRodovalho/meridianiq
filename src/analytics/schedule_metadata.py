"""Schedule metadata intelligence — extract update/revision/type from filename and XER data.

Detects:
- Update number (UP 01, UP 02, ...)
- Revision number (Rev 00 = draft, Rev 01+ = final)
- Schedule type: MPS (Master Program Schedule), IMS (Integrated Master Schedule),
  CMAR (Contractor Schedule), Baseline, Draft
- Data date from XER PROJECT table
- Baseline presence (target_start_date / target_end_date fields)
- Schedule series grouping (same project across time)

Reference: AACE RP 49R-06 — Identifying the Critical Path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScheduleMetadata:
    """Extracted metadata about a schedule file."""

    # From filename/project name
    update_number: int | None = None
    revision_number: int | None = None
    is_draft: bool = False
    is_final: bool = False
    is_baseline: bool = False
    schedule_type: str = "unknown"  # mps, ims, cmar, baseline, construction, other
    schedule_prefix: str = ""  # FDTP, BPTR, BPT, FDT, etc.

    # From XER data
    data_date: str | None = None
    project_start: str | None = None
    project_finish: str | None = None
    project_name: str = ""
    activity_count: int = 0
    relationship_count: int = 0
    calendar_count: int = 0
    has_baseline_dates: bool = False
    baseline_coverage_pct: float = 0.0

    # Scheduling options
    retained_logic: bool = False
    progress_override: bool = False
    multiple_float_paths: bool = False

    # Derived
    tags: list[str] = field(default_factory=list)


def extract_metadata(
    filename: str,
    project_name: str = "",
    data_date: datetime | None = None,
    activities: list | None = None,
    raw_tables: dict | None = None,
) -> ScheduleMetadata:
    """Extract schedule metadata from filename, project name, and XER data.

    Args:
        filename: Original upload filename (e.g. "FDTP - MPS UP 08 Rev 00.xer").
        project_name: P6 project short name from XER PROJECT table.
        data_date: Data date from XER PROJECT.last_recalc_date.
        activities: Parsed activity list (for baseline detection).
        raw_tables: Raw XER table dict (for SCHEDOPTIONS, etc.).

    Returns:
        ScheduleMetadata with all detected fields.
    """
    meta = ScheduleMetadata()
    meta.project_name = project_name

    # Use project_name if more informative, else filename
    source = project_name or filename

    # ── Extract from filename / project name ──────────────

    # Update number: "UP 03", "UP03", "UP-03"
    up_match = re.search(r"UP[\s\-]*(\d+)", source, re.IGNORECASE)
    if up_match:
        meta.update_number = int(up_match.group(1))

    # Revision: "Rev 00", "Rev00", "Rev 01", "R1"
    rev_match = re.search(r"Rev[\s]*(\d+)", source, re.IGNORECASE)
    if not rev_match:
        rev_match = re.search(r"R(\d+)(?:\b|$)", source)
    if rev_match:
        meta.revision_number = int(rev_match.group(1))

    # Draft / Final
    meta.is_draft = bool(re.search(r"\bDraft\b", source, re.IGNORECASE))
    meta.is_final = bool(re.search(r"\bFINAL\b", source, re.IGNORECASE))
    if meta.revision_number is not None:
        if meta.revision_number == 0 and not meta.is_final:
            meta.is_draft = True
        elif meta.revision_number > 0:
            meta.is_final = True

    # Baseline detection from name
    meta.is_baseline = bool(
        re.search(
            r"BL[-\s]*\d+|BASE[-\s]*\d*|\bBaseline\b",
            source,
            re.IGNORECASE,
        )
    )

    # Schedule type (order matters: most specific first)
    if re.search(r"\bMPS\b", source, re.IGNORECASE):
        meta.schedule_type = "mps"
    elif re.search(r"\bCMAR\b|GMP[-\s]*\d|\bCSW\b", source, re.IGNORECASE):
        meta.schedule_type = "cmar"
    elif meta.is_baseline:
        meta.schedule_type = "baseline"
    elif re.search(r"\bIMS\b", source, re.IGNORECASE):
        meta.schedule_type = "ims"
    elif re.search(r"\bPhase\b", source, re.IGNORECASE):
        meta.schedule_type = "ims"
    else:
        meta.schedule_type = "other"

    # Prefix: first token before " - " or "-"
    prefix_match = re.match(r"^([A-Z]{2,6})", source.strip())
    if prefix_match:
        meta.schedule_prefix = prefix_match.group(1)

    # ── Extract from XER data ─────────────────────────────

    if data_date:
        meta.data_date = data_date.strftime("%Y-%m-%d")

    if activities:
        meta.activity_count = len(activities)
        acts_with_baseline = sum(
            1 for a in activities if hasattr(a, "target_start_date") and a.target_start_date
        )
        meta.has_baseline_dates = acts_with_baseline > 0
        meta.baseline_coverage_pct = (
            (acts_with_baseline / len(activities) * 100) if activities else 0.0
        )

    if raw_tables:
        sched_opts = raw_tables.get("SCHEDOPTIONS", [])
        if sched_opts:
            opts = sched_opts[0]
            meta.retained_logic = opts.get("sched_retained_logic") == "Y"
            meta.progress_override = opts.get("sched_progress_override") == "Y"
            meta.multiple_float_paths = opts.get("enable_multiple_longest_path_calc") == "Y"

    # ── Build tags ────────────────────────────────────────

    tags: list[str] = []
    if meta.schedule_type != "unknown":
        tags.append(meta.schedule_type.upper())
    if meta.update_number is not None:
        tags.append(f"UP#{meta.update_number:02d}")
    if meta.revision_number is not None:
        tags.append(f"Rev{meta.revision_number:02d}")
    if meta.is_draft:
        tags.append("DRAFT")
    if meta.is_final:
        tags.append("FINAL")
    if meta.is_baseline and meta.schedule_type != "baseline":
        tags.append("BASELINE")
    if meta.has_baseline_dates:
        tags.append("HAS_BL_DATES")
    if meta.retained_logic:
        tags.append("RETAINED_LOGIC")
    if meta.progress_override:
        tags.append("PROGRESS_OVERRIDE")
    if meta.multiple_float_paths:
        tags.append("MULTI_FLOAT_PATH")
    meta.tags = tags

    return meta
