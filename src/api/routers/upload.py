# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Upload router — XER and MS Project XML file ingestion."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from src.analytics.dcma14 import DCMA14Analyzer
from src.parser.xer_reader import XERReader

from ..auth import optional_auth
from ..cache import invalidate_namespace
from ..deps import _sandbox_projects, get_store, limiter
from ..schemas import ProjectSummary, ScheduleMetadataSchema

router = APIRouter()


@router.get("/api/v1/demo/project")
def demo_project():
    """Return a pre-analyzed demo project from the sample XER fixture.

    No authentication required. Used by the landing page "Try with sample data" flow.
    """
    sample_path = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "sample.xer"
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Demo data not available")

    from src.parser.xer_reader import XerReader
    from src.analytics.cpm import CPMEngine

    reader = XerReader()
    schedule = reader.parse(sample_path.read_text(encoding="utf-8"))
    analyzer = DCMA14Analyzer(schedule)
    dcma = analyzer.analyze()

    cpm = CPMEngine(schedule)
    cpm_result = cpm.calculate()

    return {
        "project": {
            "name": schedule.project.proj_short_name if schedule.project else "Demo Project",
            "activity_count": len(schedule.activities),
            "relationship_count": len(schedule.relationships),
            "calendar_count": len(schedule.calendars),
            "wbs_count": len(schedule.wbs_nodes),
        },
        "validation": {
            "overall_score": dcma.overall_score,
            "passed_count": dcma.passed_count,
            "failed_count": dcma.failed_count,
            "metrics": [
                {
                    "number": m.number,
                    "name": m.name,
                    "value": round(m.value, 1),
                    "threshold": m.threshold,
                    "unit": m.unit,
                    "passed": m.passed,
                    "direction": m.direction,
                }
                for m in dcma.metrics
            ],
        },
        "critical_path": {
            "length": len(cpm_result.critical_path),
            "activities": [
                {
                    "task_code": a.task_code,
                    "task_name": a.task_name,
                    "total_float": round((a.total_float_hr_cnt or 0) / 8, 1),
                }
                for a in cpm_result.critical_path[:20]
            ],
        },
    }


@router.post("/api/v1/upload", response_model=ProjectSummary)
@limiter.limit("10/minute")
async def upload_xer(
    request: Request,
    file: UploadFile = File(...),
    is_sandbox: bool = Form(False),
    _user: object = Depends(optional_auth),
) -> ProjectSummary:
    """Upload a schedule file (XER or MS Project XML), parse it, and store the result.

    Supports:
    - Primavera P6 XER files (.xer)
    - Microsoft Project XML files (.xml)

    Returns:
        A summary of the parsed project.

    Raises:
        HTTPException: If the file format is not supported.
    """
    filename = (file.filename or "").lower()
    is_xer = filename.endswith(".xer")
    is_xml = filename.endswith(".xml")

    if not is_xer and not is_xml:
        raise HTTPException(
            status_code=400,
            detail="Unsupported format. Upload a .xer (Primavera P6) or .xml (Microsoft Project) file.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    # Enforce upload size limit (50 MB)
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024
    if len(file_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(file_bytes) / 1024 / 1024:.1f} MB). "
            f"Maximum allowed: {MAX_UPLOAD_SIZE / 1024 / 1024:.0f} MB.",
        )

    # Parse based on format
    try:
        if is_xml:
            from src.parser.msp_reader import MSPReader

            msp_reader = MSPReader()
            schedule = msp_reader.parse(file_bytes.decode("utf-8"))
            xer_bytes = file_bytes  # Store XML as-is
        else:
            xer_bytes = file_bytes
            with tempfile.NamedTemporaryFile(suffix=".xer", delete=False) as tmp:
                tmp.write(xer_bytes)
                tmp_path = Path(tmp.name)

            reader = XERReader(tmp_path)
            schedule = reader.parse()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse XER file: {exc}")
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass

    if not schedule.activities:
        raise HTTPException(status_code=400, detail="XER file contains no activities")

    store = get_store()
    user_id = _user["id"] if _user else None
    project_id = store.add(schedule, xer_bytes, user_id=user_id)

    # Drop stale KPI aggregates — a new schedule invalidates any cached
    # CPM/DCMA/Health bundles under this user's project set. Namespace-wide
    # drop is intentional: the cache has no per-project key enumeration.
    invalidate_namespace("schedule:kpis")

    # Track sandbox status
    if is_sandbox:
        _sandbox_projects.add(project_id)

    data_date = None
    name = ""
    dd_dt = None
    if schedule.projects:
        proj = schedule.projects[0]
        name = proj.proj_short_name
        dd_dt = proj.last_recalc_date or proj.sum_data_date
        if dd_dt:
            data_date = dd_dt.isoformat()

    # Extract schedule metadata intelligence
    from src.analytics.schedule_metadata import extract_metadata

    meta = extract_metadata(
        filename=file.filename or "",
        project_name=name,
        data_date=dd_dt,
        activities=schedule.activities,
        raw_tables=schedule.raw_tables if hasattr(schedule, "raw_tables") else None,
    )
    meta_schema = ScheduleMetadataSchema(
        update_number=meta.update_number,
        revision_number=meta.revision_number,
        is_draft=meta.is_draft,
        is_final=meta.is_final,
        is_baseline=meta.is_baseline,
        schedule_type=meta.schedule_type,
        schedule_prefix=meta.schedule_prefix,
        has_baseline_dates=meta.has_baseline_dates,
        baseline_coverage_pct=meta.baseline_coverage_pct,
        retained_logic=meta.retained_logic,
        progress_override=meta.progress_override,
        multiple_float_paths=meta.multiple_float_paths,
        tags=meta.tags,
    )

    return ProjectSummary(
        project_id=project_id,
        name=name,
        activity_count=len(schedule.activities),
        relationship_count=len(schedule.relationships),
        calendar_count=len(schedule.calendars),
        wbs_count=len(schedule.wbs_nodes),
        data_date=data_date,
        metadata=meta_schema,
    )
