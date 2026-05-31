# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Upload router — XER and MS Project XML file ingestion."""

from __future__ import annotations

import functools
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from src.analytics.cpm import CPMCalculator
from src.analytics.dcma14 import DCMA14Analyzer
from src.parser.xer_reader import XERReader

from ..auth import optional_auth
from ..cache import invalidate_namespace
from ..deps import (
    RATE_LIMIT_MODERATE,
    RATE_LIMIT_READ,
    _sandbox_projects,
    get_materializer,
    get_store,
    limiter,
)
from ..schemas import ProjectSummary, ScheduleMetadataSchema

router = APIRouter()


def _demo_sample_path() -> Path:
    # Ship the demo fixture INSIDE the package (src/api/demo_data/) so it is
    # copied into the production image by the Dockerfile's `COPY src/ src/`
    # and bundled by hatchling. The old tests/fixtures/ path 404'd in prod —
    # `tests/` is never copied into the container.
    return Path(__file__).resolve().parents[1] / "demo_data" / "sample.xer"


@functools.lru_cache(maxsize=1)
def _demo_payload() -> dict[str, Any]:
    """Parse + analyze the bundled sample XER once and memoize the result.

    The sample fixture is immutable, so the parse, DCMA 14-Point assessment
    (per DCMA EVMS guidelines) and CPM forward/backward pass are computed a
    single time per process. Memoizing keeps this public, unauthenticated
    endpoint cheap and removes it as an anonymous-compute abuse surface.
    """
    schedule = XERReader(_demo_sample_path()).parse()
    dcma = DCMA14Analyzer(schedule).analyze()
    cpm_result = CPMCalculator(schedule).calculate()

    # critical_path is a list of task_id node IDs — map back to the Task rows.
    task_map = {t.task_id: t for t in schedule.activities}
    cp_activities: list[dict[str, Any]] = []
    for task_id in cpm_result.critical_path[:20]:
        task = task_map.get(task_id)
        if task is None:
            continue
        cp_activities.append(
            {
                "task_code": task.task_code,
                "task_name": task.task_name,
                "total_float": round((task.total_float_hr_cnt or 0) / 8, 1),
            }
        )

    project_name = schedule.projects[0].proj_short_name if schedule.projects else "Demo Project"

    return {
        "project": {
            "name": project_name,
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
            "activities": cp_activities,
        },
    }


@router.get("/api/v1/demo/project")
@limiter.limit(RATE_LIMIT_READ)
def demo_project(request: Request) -> dict[str, Any]:
    """Return a pre-analyzed demo project from the sample XER fixture.

    No authentication required — powers the landing-page "Try with sample data"
    flow so a visitor sees real DCMA 14-Point + critical-path output with zero
    account. The parse + analysis is memoized (see ``_demo_payload``); the rate
    limit is defence-in-depth on the one public, unauthenticated compute path.
    """
    if not _demo_sample_path().exists():
        raise HTTPException(status_code=404, detail="Demo data not available")
    return _demo_payload()


@router.post("/api/v1/upload", response_model=ProjectSummary)
@limiter.limit(RATE_LIMIT_MODERATE)
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

    # ADR-0015: kick off the async materializer so the client can return
    # immediately while DCMA / health / CPM run in the background. The
    # handle carries the ``job_id`` the frontend subscribes to on the
    # ADR-0013 WebSocket progress channel.
    job_id: str | None = None
    ws_url: str | None = None
    try:
        materializer = get_materializer()
        handle = materializer.enqueue(project_id, user_id=user_id)
        job_id = handle.job_id
        ws_url = f"/api/v1/ws/progress/{handle.job_id}"
    except Exception:
        # Materializer wiring failure must not leave the row in 'pending'
        # forever (council W2 devils-advocate P1#4). Flip to 'failed' so
        # the UI surfaces the incident and the operator can reconcile.
        import logging as _logging

        _logging.getLogger(__name__).exception(
            "materializer.enqueue failed for project %s", project_id
        )
        try:
            if hasattr(store, "set_project_status"):
                store.set_project_status(project_id, "failed")
        except Exception:
            _logging.getLogger(__name__).exception(
                "set_project_status(failed) also failed for project %s", project_id
            )

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

    # ADR-0015: expose the state machine value so the frontend can render
    # the computing badge. SupabaseStore returns 'pending' right after save;
    # the async materializer flips to 'ready' once the engines complete.
    # InMemoryStore sync-fast-path returns 'ready' immediately.
    status_value = (
        store.get_project_status(project_id) if hasattr(store, "get_project_status") else "pending"
    )

    return ProjectSummary(
        project_id=project_id,
        name=name,
        activity_count=len(schedule.activities),
        relationship_count=len(schedule.relationships),
        calendar_count=len(schedule.calendars),
        wbs_count=len(schedule.wbs_nodes),
        data_date=data_date,
        status=status_value or "pending",
        job_id=job_id,
        ws_url=ws_url,
        metadata=meta_schema,
    )
