# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Reports router — PDF report generation, download, and availability."""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..auth import optional_auth
from ..deps import get_evm_store, get_report_store, get_risk_store, get_store, get_tia_store
from ..schemas import (
    GenerateReportRequest,
    GenerateReportResponse,
)
from ..storage import ProjectStore

from src.analytics.calendar_validation import validate_calendars
from src.analytics.comparison import ScheduleComparison
from src.analytics.delay_attribution import compute_delay_attribution
from src.analytics.early_warning import EarlyWarningEngine
from src.analytics.forensics import ForensicAnalyzer
from src.analytics.report_generator import ReportGenerator
from src.parser.models import ParsedSchedule

router = APIRouter()


_VALID_REPORT_TYPES = {
    "health",
    "comparison",
    "forensic",
    "tia",
    "risk",
    "monthly_review",
    "executive_summary",
    "calendar",
    "attribution",
    "narrative",
    "scl_protocol",
    "aace_29r03",
    "aia_g702",
}


# ------------------------------------------------------------------
# Report Generation
# ------------------------------------------------------------------


@router.post(
    "/api/v1/reports/generate",
    response_model=GenerateReportResponse,
)
def generate_report(
    request: GenerateReportRequest,
    _user: object = Depends(optional_auth),
) -> GenerateReportResponse:
    """Generate a PDF report. Returns report ID for download.

    Supports 6 report types:
    - health: Schedule Health Report (DCMA + health score + alerts)
    - comparison: Comparison Report (requires baseline_id)
    - forensic: Forensic Report (requires baseline_id for timeline)
    - tia: TIA Report (requires baseline_id)
    - risk: Risk Report (requires baseline_id)
    - monthly_review: Monthly Review Report (health + comparison + alerts)

    Args:
        request: Report generation parameters.

    Raises:
        HTTPException: If the project is not found or report type is invalid.
    """
    if request.report_type not in _VALID_REPORT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report_type '{request.report_type}'. "
            f"Valid types: {', '.join(sorted(_VALID_REPORT_TYPES))}",
        )

    store = get_store()
    schedule = store.get(request.project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    generator = ReportGenerator()
    report_type = request.report_type

    try:
        if report_type == "health":
            pdf_bytes = _generate_health_report(generator, schedule, request)
        elif report_type == "comparison":
            pdf_bytes = _generate_comparison_report(generator, schedule, request, store)
        elif report_type == "forensic":
            pdf_bytes = _generate_forensic_report(generator, schedule, request, store)
        elif report_type == "tia":
            pdf_bytes = _generate_tia_report(generator, schedule, request, store)
        elif report_type == "risk":
            pdf_bytes = _generate_risk_report(generator, schedule, request, store)
        elif report_type == "monthly_review":
            pdf_bytes = _generate_monthly_review_report(generator, schedule, request, store)
        elif report_type == "executive_summary":
            pdf_bytes = _generate_executive_summary(generator, schedule, request.project_id, store)
        elif report_type == "calendar":
            result = validate_calendars(schedule)
            pdf_bytes = generator.generate_calendar_report(schedule, result)
        elif report_type == "attribution":
            result = compute_delay_attribution(schedule)
            pdf_bytes = generator.generate_attribution_report(schedule, result)
        elif report_type == "narrative":
            pdf_bytes = _generate_narrative_report(generator, schedule, request, store)
        elif report_type == "scl_protocol":
            pdf_bytes = _generate_scl_protocol_report(generator, schedule, request, store)
        elif report_type == "aace_29r03":
            pdf_bytes = _generate_aace_29r03_report(generator, schedule, request, store)
        elif report_type == "aia_g702":
            pdf_bytes = _generate_aia_g702_report(generator, schedule, request, store)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported report type: {report_type}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}")

    from datetime import datetime as _dt

    generated_at = _dt.now().isoformat()

    report_store = get_report_store()
    report_id = report_store.add(
        pdf_bytes,
        {
            "report_type": report_type,
            "project_id": request.project_id,
            "generated_at": generated_at,
        },
    )

    return GenerateReportResponse(
        report_id=report_id,
        report_type=report_type,
        project_id=request.project_id,
        generated_at=generated_at,
    )


# ------------------------------------------------------------------
# Report Download
# ------------------------------------------------------------------


@router.get("/api/v1/reports/{report_id}/download")
def download_report(
    report_id: str,
    _user: object = Depends(optional_auth),
) -> StreamingResponse:
    """Download a generated PDF report.

    Args:
        report_id: The report identifier from generate_report.

    Raises:
        HTTPException: If the report is not found.
    """
    report_store = get_report_store()
    report = report_store.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    pdf_bytes = report["bytes"]
    report_type = report.get("report_type", "report")

    # Determine content type: PDF if starts with %PDF, otherwise HTML
    content_type = "application/pdf"
    extension = "pdf"
    if not pdf_bytes[:5].startswith(b"%PDF"):
        content_type = "text/html"
        extension = "html"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="meridianiq-{report_type}-{report_id}.{extension}"',
        },
    )


# ------------------------------------------------------------------
# Report Availability
# ------------------------------------------------------------------


@router.get("/api/v1/projects/{project_id}/available-reports")
def get_available_reports(
    project_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """Check which report types have data available for a project.

    Returns a list of report descriptors with ``ready`` boolean and a
    human-readable ``reason`` when the report is not yet available.
    """
    store = get_store()
    user_id = _user["id"] if _user else None
    schedule = store.get(project_id, user_id=user_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    reports = []

    # --- health: always computable from the schedule itself ---
    reports.append(
        {
            "type": "health",
            "name": "Schedule Health Report",
            "ready": True,
            "reason": "",
        }
    )

    # --- dcma: always computable from the schedule itself ---
    reports.append(
        {
            "type": "dcma",
            "name": "DCMA 14-Point Report",
            "ready": True,
            "reason": "",
        }
    )

    # --- comparison: needs a second upload in the same program ---
    comparison_ready = False
    comparison_reason = "Requires at least two schedule revisions in the same program"
    if hasattr(store, "_upload_program"):
        # InMemoryStore: look for a sibling upload
        program_id = store._upload_program.get(project_id)
        if program_id:
            siblings = [
                pid
                for pid, prog in store._upload_program.items()
                if prog == program_id and pid != project_id
            ]
            if siblings:
                comparison_ready = True
                comparison_reason = ""
    elif hasattr(store, "get_program_revisions"):
        # SupabaseStore: check via program revisions
        programs = store.get_programs(user_id=user_id)
        for prog in programs:
            revisions = store.get_program_revisions(prog["id"], user_id=user_id)
            ids = [r["id"] for r in revisions]
            if project_id in ids and len(ids) >= 2:
                comparison_ready = True
                comparison_reason = ""
                break

    reports.append(
        {
            "type": "comparison",
            "name": "Schedule Comparison Report",
            "ready": comparison_ready,
            "reason": comparison_reason,
        }
    )

    # --- evm: check if an EVM analysis exists for this project ---
    evm_ready = False
    evm_reason = "Run EVM analysis first"
    evm_store = get_evm_store()
    for entry in evm_store.list_all():
        if entry.get("project_id") == project_id:
            evm_ready = True
            evm_reason = ""
            break

    reports.append(
        {
            "type": "evm",
            "name": "Earned Value Report",
            "ready": evm_ready,
            "reason": evm_reason,
        }
    )

    # --- risk: check if a risk simulation exists for this project ---
    risk_ready = False
    risk_reason = "Run Monte Carlo simulation first"
    risk_store = get_risk_store()
    for entry in risk_store.list_all():
        if entry.get("project_id") == project_id:
            risk_ready = True
            risk_reason = ""
            break

    reports.append(
        {
            "type": "risk",
            "name": "Risk / QSRA Report",
            "ready": risk_ready,
            "reason": risk_reason,
        }
    )

    # --- monthly_review: always computable (enhanced with comparison if available) ---
    reports.append(
        {
            "type": "monthly_review",
            "name": "Monthly Review Report",
            "ready": True,
            "reason": "",
        }
    )

    # --- calendar: always computable from the schedule itself ---
    reports.append(
        {
            "type": "calendar",
            "name": "Calendar Validation Report",
            "ready": True,
            "reason": "",
        }
    )

    # --- attribution: always computable (enhanced with baseline) ---
    reports.append(
        {
            "type": "attribution",
            "name": "Delay Attribution Report",
            "ready": True,
            "reason": "",
        }
    )

    # --- narrative: always computable from schedule summary + scorecard ---
    reports.append(
        {
            "type": "narrative",
            "name": "Schedule Narrative Report",
            "ready": True,
            "reason": "",
        }
    )

    # --- executive_summary: always computable (enriched with attribution,
    # CBS variance, and program rollup when project has siblings / snapshots) ---
    reports.append(
        {
            "type": "executive_summary",
            "name": "Executive Summary",
            "ready": True,
            "reason": "",
        }
    )

    # --- scl_protocol: always computable (enriched with forensic timeline
    # when baseline_id is passed to generate; core sections render from
    # schedule alone as factual narrative) ---
    reports.append(
        {
            "type": "scl_protocol",
            "name": "SCL Protocol Delay Analysis",
            "ready": True,
            "reason": "",
        }
    )

    # --- aace_29r03: AACE RP 29R-03 §5.3 forensic submission ---
    reports.append(
        {
            "type": "aace_29r03",
            "name": "AACE RP 29R-03 §5.3 Forensic Report",
            "ready": True,
            "reason": "",
        }
    )

    # --- aia_g702: Application and Certificate for Payment (requires CBS snapshot) ---
    has_snapshot = False
    if hasattr(store, "list_cost_snapshots"):
        try:
            has_snapshot = bool(store.list_cost_snapshots(project_id))
        except Exception:
            has_snapshot = False
    reports.append(
        {
            "type": "aia_g702",
            "name": "AIA G702 Application and Certificate for Payment",
            "ready": has_snapshot,
            "reason": "" if has_snapshot else "Requires at least one CBS snapshot",
        }
    )

    return {"project_id": project_id, "reports": reports}


# ------------------------------------------------------------------
# Helper functions for report generation
# ------------------------------------------------------------------


def _generate_health_report(
    generator: ReportGenerator,
    schedule: ParsedSchedule,
    request: GenerateReportRequest,
) -> bytes:
    """Generate a health report PDF."""
    from src.analytics.dcma14 import DCMA14Analyzer
    from src.analytics.health_score import HealthScoreCalculator

    dcma = DCMA14Analyzer(schedule)
    dcma_result = dcma.analyze()

    baseline = None
    if request.baseline_id:
        baseline = get_store().get(request.baseline_id)

    calc = HealthScoreCalculator(schedule, baseline=baseline)
    health = calc.calculate()

    alerts_result = None
    if baseline:
        try:
            engine = EarlyWarningEngine(baseline, schedule)
            alerts_result = engine.analyze()
        except Exception:
            pass

    return generator.generate_health_report(schedule, dcma_result, health, alerts_result)


def _generate_comparison_report(
    generator: ReportGenerator,
    schedule: ParsedSchedule,
    request: GenerateReportRequest,
    store: ProjectStore,
) -> bytes:
    """Generate a comparison report PDF."""
    if not request.baseline_id:
        raise HTTPException(
            status_code=400,
            detail="baseline_id is required for comparison reports",
        )

    baseline = store.get(request.baseline_id)
    if baseline is None:
        raise HTTPException(status_code=404, detail="Baseline project not found")

    comparison = ScheduleComparison(baseline, schedule)
    result = comparison.compare()

    return generator.generate_comparison_report(baseline, schedule, result)


def _generate_forensic_report(
    generator: ReportGenerator,
    schedule: ParsedSchedule,
    request: GenerateReportRequest,
    store: ProjectStore,
) -> bytes:
    """Generate a forensic report PDF."""
    if not request.baseline_id:
        raise HTTPException(
            status_code=400,
            detail="baseline_id is required for forensic reports",
        )

    baseline = store.get(request.baseline_id)
    if baseline is None:
        raise HTTPException(status_code=404, detail="Baseline project not found")

    analyzer = ForensicAnalyzer(
        schedules=[baseline, schedule],
        project_ids=[request.baseline_id, request.project_id],
    )
    timeline = analyzer.analyze()

    return generator.generate_forensic_report(timeline)


def _generate_tia_report(
    generator: ReportGenerator,
    schedule: ParsedSchedule,
    request: GenerateReportRequest,
    store: ProjectStore,
) -> bytes:
    """Generate a TIA report PDF."""
    # Look for existing TIA analysis, or create a minimal one
    tia_store = get_tia_store()
    analyses = tia_store.list_all()
    if analyses:
        # Use the most recent TIA analysis
        latest = analyses[-1]
        analysis = tia_store.get(latest["analysis_id"])
        if analysis:
            return generator.generate_tia_report(analysis)

    raise HTTPException(
        status_code=400,
        detail="No TIA analysis found. Please run a TIA analysis first.",
    )


def _generate_risk_report(
    generator: ReportGenerator,
    schedule: ParsedSchedule,
    request: GenerateReportRequest,
    store: ProjectStore,
) -> bytes:
    """Generate a risk report PDF."""
    risk_store = get_risk_store()
    simulations = risk_store.list_all()
    if simulations:
        latest = simulations[-1]
        result = risk_store.get(latest["simulation_id"])
        if result:
            return generator.generate_risk_report(result)

    raise HTTPException(
        status_code=400,
        detail="No risk simulation found. Please run a Monte Carlo simulation first.",
    )


def _generate_monthly_review_report(
    generator: ReportGenerator,
    schedule: ParsedSchedule,
    request: GenerateReportRequest,
    store: ProjectStore,
) -> bytes:
    """Generate a monthly review report PDF.

    Combines health score, DCMA, comparison delta, and early warning alerts
    into a single standardised monthly update report per PMI PMBOK 7 S4.6
    and CMAA (2019) S7.
    """
    from src.analytics.dcma14 import DCMA14Analyzer
    from src.analytics.health_score import HealthScoreCalculator

    dcma = DCMA14Analyzer(schedule)
    dcma_result = dcma.analyze()

    baseline = None
    if request.baseline_id:
        baseline = store.get(request.baseline_id)

    calc = HealthScoreCalculator(schedule, baseline=baseline)
    health = calc.calculate()

    # Comparison with baseline (if provided)
    comparison_result = None
    if baseline:
        comparison = ScheduleComparison(baseline, schedule)
        comparison_result = comparison.compare()

    # Early warning alerts (if baseline provided)
    alerts_result = None
    if baseline:
        try:
            engine = EarlyWarningEngine(baseline, schedule)
            alerts_result = engine.analyze()
        except Exception:
            pass

    return generator.generate_monthly_review_report(
        schedule,
        dcma_result,
        health,
        comparison_result,
        alerts_result,
        baseline,
    )


def _generate_narrative_report(
    generator: ReportGenerator,
    schedule: ParsedSchedule,
    request: GenerateReportRequest,
    store: ProjectStore,
) -> bytes:
    """Generate Narrative Schedule Report PDF.

    Combines schedule view summary + scorecard + optional baseline
    comparison into a severity-tagged narrative, then renders to PDF.

    Reference: AACE RP 29R-03 §5.3 — Forensic Schedule Report.
    """
    from src.analytics.comparison import ScheduleComparison
    from src.analytics.narrative_report import generate_schedule_narrative
    from src.analytics.schedule_view import build_schedule_view
    from src.analytics.scorecard import calculate_scorecard

    view = build_schedule_view(schedule)

    scorecard_data = None
    try:
        from dataclasses import asdict as _asdict

        sc = calculate_scorecard(schedule)
        scorecard_data = _asdict(sc)
    except Exception:
        pass

    comparison_data = None
    if request.baseline_id:
        baseline = store.get(request.baseline_id)
        if baseline is not None:
            try:
                comp = ScheduleComparison(baseline, schedule)
                comparison_data = comp.compare()
            except Exception:
                pass

    narrative = generate_schedule_narrative(
        project_name=view.project_name,
        data_date=view.data_date,
        summary=view.summary,
        scorecard=scorecard_data,
        comparison=comparison_data,
    )

    return generator.generate_narrative_report(schedule, narrative)


def _generate_scl_protocol_report(
    generator: ReportGenerator,
    schedule: ParsedSchedule,
    request: GenerateReportRequest,
    store: ProjectStore,
) -> bytes:
    """Generate SCL Protocol submission PDF.

    Composes: delay attribution (always), forensic timeline (when
    baseline_id is supplied), and schedule narrative (always).
    """
    from src.analytics.delay_attribution import compute_delay_attribution
    from src.analytics.narrative_report import generate_schedule_narrative
    from src.analytics.schedule_view import build_schedule_view
    from src.analytics.scorecard import calculate_scorecard

    attribution = None
    timeline = None
    narrative = None

    baseline = None
    if request.baseline_id:
        baseline = store.get(request.baseline_id)

    try:
        attribution = compute_delay_attribution(schedule, baseline=baseline)
    except Exception:
        pass

    if baseline is not None:
        try:
            analyzer = ForensicAnalyzer(
                schedules=[baseline, schedule],
                project_ids=[request.baseline_id or "", request.project_id],
            )
            timeline = analyzer.analyze()
        except Exception:
            pass

    try:
        view = build_schedule_view(schedule)
        scorecard_data = None
        try:
            from dataclasses import asdict as _asdict

            scorecard_data = _asdict(calculate_scorecard(schedule))
        except Exception:
            pass
        narrative = generate_schedule_narrative(
            project_name=view.project_name,
            data_date=view.data_date,
            summary=view.summary,
            scorecard=scorecard_data,
        )
    except Exception:
        pass

    return generator.generate_scl_protocol_report(
        schedule,
        timeline=timeline,
        attribution=attribution,
        narrative=narrative,
    )


def _generate_aace_29r03_report(
    generator: ReportGenerator,
    schedule: ParsedSchedule,
    request: GenerateReportRequest,
    store: ProjectStore,
) -> bytes:
    """Generate AACE RP 29R-03 §5.3 forensic submission PDF."""
    from src.analytics.delay_attribution import compute_delay_attribution
    from src.analytics.scorecard import calculate_scorecard

    attribution = None
    timeline = None
    scorecard = None
    half_step = None

    baseline = None
    if request.baseline_id:
        baseline = store.get(request.baseline_id)

    try:
        attribution = compute_delay_attribution(schedule, baseline=baseline)
    except Exception:
        pass

    if baseline is not None:
        try:
            analyzer = ForensicAnalyzer(
                schedules=[baseline, schedule],
                project_ids=[request.baseline_id or "", request.project_id],
            )
            timeline = analyzer.analyze()
        except Exception:
            pass

    try:
        scorecard = calculate_scorecard(schedule)
    except Exception:
        pass

    if baseline is not None and request.options.get("bifurcated"):
        try:
            from src.analytics.half_step import analyze_half_step

            half_step = analyze_half_step(baseline, schedule)
        except Exception:
            pass

    return generator.generate_aace_forensic_report(
        schedule,
        timeline=timeline,
        attribution=attribution,
        scorecard=scorecard,
        half_step=half_step,
        baseline=baseline,
    )


def _generate_executive_summary(
    generator: ReportGenerator,
    schedule: ParsedSchedule,
    project_id: str,
    store: ProjectStore,
) -> bytes:
    """Generate executive summary PDF combining scorecard + DCMA + health + risk,
    optionally enriched with delay attribution, CBS variance, and program rollup."""
    from src.analytics.dcma14 import DCMA14Analyzer
    from src.analytics.delay_attribution import compute_delay_attribution
    from src.analytics.delay_prediction import predict_delays
    from src.analytics.health_score import HealthScoreCalculator
    from src.analytics.scorecard import calculate_scorecard

    scorecard = calculate_scorecard(schedule)
    dcma_result = DCMA14Analyzer(schedule).analyze()
    health = HealthScoreCalculator(schedule).calculate()
    delay = predict_delays(schedule)

    # Delay attribution — always computable from the schedule itself
    delay_attribution = None
    try:
        delay_attribution = compute_delay_attribution(schedule)
    except Exception:
        pass

    # CBS variance — compare the two most recent snapshots if available
    cost_comparison = None
    try:
        snapshots = (
            store.list_cost_snapshots(project_id) if hasattr(store, "list_cost_snapshots") else []
        )
        if len(snapshots) >= 2:
            # list_cost_snapshots returns newest first; compare prior (a) vs latest (b)
            latest_id = snapshots[0]["snapshot_id"]
            prior_id = snapshots[1]["snapshot_id"]
            snap_b = store.get_cost_snapshot(project_id, latest_id)
            snap_a = store.get_cost_snapshot(project_id, prior_id)
            if snap_a is not None and snap_b is not None:
                from src.analytics.cost_integration import compare_cost_snapshots

                cost_comparison = compare_cost_snapshots(
                    snap_a, snap_b, snapshot_a_id=prior_id, snapshot_b_id=latest_id
                )
    except Exception:
        pass

    # Program rollup — if this project belongs to a program with ≥2 revisions
    program_rollup = None
    try:
        program_id = None
        if hasattr(store, "_upload_program"):
            program_id = store._upload_program.get(project_id)
        else:
            programs = store.get_programs() if hasattr(store, "get_programs") else []
            for prog in programs:
                revisions = (
                    store.get_program_revisions(prog["id"])
                    if hasattr(store, "get_program_revisions")
                    else []
                )
                if any(r.get("id") == project_id for r in revisions):
                    program_id = prog["id"]
                    break

        if program_id:
            from src.api.routers.programs import compute_program_rollup

            program_rollup = compute_program_rollup(program_id)
    except Exception:
        program_rollup = None

    return generator.generate_executive_summary(
        schedule,
        scorecard=scorecard,
        dcma_result=dcma_result,
        health_score=health,
        delay_prediction=delay,
        delay_attribution=delay_attribution,
        cost_comparison=cost_comparison,
        program_rollup=program_rollup,
    )


def _generate_aia_g702_report(
    generator: ReportGenerator,
    schedule: ParsedSchedule,
    request: GenerateReportRequest,
    store: ProjectStore,
) -> bytes:
    """Generate AIA G702 Application and Certificate for Payment PDF.

    Requires a CBS snapshot (for the paired G703 totals) and several
    caller-supplied contract fields passed via ``request.options``:

    - ``snapshot_id`` (required) — CBS snapshot to derive G703 totals from
    - ``original_contract_sum`` (required, float)
    - ``application_number`` (int, default 1)
    - ``period_to`` (str, default "")
    - ``retainage_pct`` (float, default 0.10)
    - ``retainage_stored_fraction`` (float 0-1, default 0.0) — split of
      g703.total_retainage between stored materials (5b) and completed
      work (5a)
    - ``previous_certificates_total`` (float, default 0.0) — Line 7
    - ``change_order`` (dict with keys prior_additions,
      prior_deductions, this_period_additions, this_period_deductions)
    - ``owner``, ``contractor``, ``architect``, ``contract_for``,
      ``architects_project_number``, ``contract_date``, ``via_architect``
      (str, optional header fields)
    """
    opts = request.options or {}

    snapshot_id = opts.get("snapshot_id")
    if not snapshot_id:
        raise HTTPException(
            status_code=400,
            detail="aia_g702 requires 'snapshot_id' in options (CBS snapshot)",
        )

    original_contract_sum = opts.get("original_contract_sum")
    if original_contract_sum is None:
        raise HTTPException(
            status_code=400,
            detail="aia_g702 requires 'original_contract_sum' in options",
        )

    snapshot = None
    if hasattr(store, "get_cost_snapshot"):
        snapshot = store.get_cost_snapshot(request.project_id, snapshot_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404, detail=f"CBS snapshot not retrievable: {snapshot_id}"
        )

    project_name = (
        schedule.projects[0].proj_short_name if schedule.projects else request.project_id
    )

    from src.analytics.aia_g702 import G702ChangeOrder, build_g702_from_g703
    from src.analytics.aia_g703 import build_g703_from_cbs

    g703 = build_g703_from_cbs(
        snapshot,
        project_name=project_name,
        application_number=int(opts.get("application_number", 1) or 1),
        period_to=str(opts.get("period_to", "") or ""),
        retainage_pct=float(opts.get("retainage_pct", 0.10) or 0.10),
    )

    co_input = opts.get("change_order") or {}
    change_order = G702ChangeOrder(
        prior_additions=float(co_input.get("prior_additions", 0.0) or 0.0),
        prior_deductions=float(co_input.get("prior_deductions", 0.0) or 0.0),
        this_period_additions=float(co_input.get("this_period_additions", 0.0) or 0.0),
        this_period_deductions=float(co_input.get("this_period_deductions", 0.0) or 0.0),
    )

    g702 = build_g702_from_g703(
        g703,
        original_contract_sum=float(original_contract_sum),
        previous_certificates_total=float(opts.get("previous_certificates_total", 0.0) or 0.0),
        change_order=change_order,
        retainage_stored_fraction=float(opts.get("retainage_stored_fraction", 0.0) or 0.0),
        owner=str(opts.get("owner", "") or ""),
        contractor=str(opts.get("contractor", "") or ""),
        architect=str(opts.get("architect", "") or ""),
        contract_for=str(opts.get("contract_for", "") or ""),
        architects_project_number=str(opts.get("architects_project_number", "") or ""),
        contract_date=str(opts.get("contract_date", "") or ""),
        via_architect=str(opts.get("via_architect", "") or ""),
    )

    return generator.generate_aia_g702_report(g702, g703=g703)
