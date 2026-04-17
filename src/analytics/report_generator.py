# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Professional PDF report generator per AACE RP 29R-03 S5.3.

Generates court-submittable reports with:
- Executive summary (auto-generated)
- Methodology statement with standard citations
- Data summary (project info, data date, activity count)
- Analysis results (tables, findings)
- Conclusions & recommendations

Supports 6 report types:
1. Schedule Health Report: DCMA results, health score, float distribution, alerts
2. Comparison Report: Delta summary, manipulation indicators, changes by WBS
3. Forensic Report: Timeline, delay waterfall, windows analysis
4. TIA Report: Fragment analysis, CP impact, compliance check
5. Risk Report: Monte Carlo results, P-values, sensitivity
6. Monthly Review Report: Standardized monthly update narrative with
   progress, health, comparison delta, alerts, and action items

Standards:
    - AACE RP 29R-03 S5.3 -- Documentation
    - CMAA (2019) S7 -- Reporting
    - DCMA 14-Point Assessment -- Schedule quality metrics
    - AACE RP 52R-06 -- Time Impact Analysis
    - AACE RP 57R-09 -- Schedule Risk Analysis
    - PMI PMBOK 7 S4.6 -- Measurement Performance Domain
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ── CSS Styles ──────────────────────────────────────────

_CSS = """
@page {
    size: letter;
    margin: 2cm 2.5cm;
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9px;
        color: #666;
    }
}
body {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #1a1a1a;
    margin: 0;
    padding: 0;
}
.header {
    border-bottom: 3px solid #1e40af;
    padding-bottom: 12px;
    margin-bottom: 24px;
}
.header .brand {
    font-size: 24px;
    font-weight: 700;
    color: #1e40af;
    letter-spacing: 1px;
}
.header .subtitle {
    font-size: 11px;
    color: #64748b;
    margin-top: 2px;
}
.header .report-title {
    font-size: 18px;
    font-weight: 600;
    color: #1a1a1a;
    margin-top: 8px;
}
.header .report-meta {
    font-size: 10px;
    color: #64748b;
    margin-top: 4px;
}
h2 {
    font-size: 14pt;
    color: #1e40af;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 4px;
    margin-top: 28px;
    margin-bottom: 12px;
    page-break-after: avoid;
}
h3 {
    font-size: 12pt;
    color: #334155;
    margin-top: 16px;
    margin-bottom: 8px;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 10pt;
}
th {
    background-color: #1e40af;
    color: white;
    padding: 8px 10px;
    text-align: left;
    font-weight: 600;
    font-size: 9pt;
}
td {
    padding: 6px 10px;
    border-bottom: 1px solid #e2e8f0;
}
tr:nth-child(even) td {
    background-color: #f8fafc;
}
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 9pt;
    font-weight: 600;
}
.badge-green { background: #dcfce7; color: #166534; }
.badge-yellow { background: #fef9c3; color: #854d0e; }
.badge-red { background: #fee2e2; color: #991b1b; }
.badge-blue { background: #dbeafe; color: #1e40af; }
.badge-gray { background: #f1f5f9; color: #475569; }
.score-circle {
    display: inline-block;
    width: 64px;
    height: 64px;
    border-radius: 50%;
    text-align: center;
    line-height: 64px;
    font-size: 22pt;
    font-weight: 700;
    margin-right: 16px;
}
.score-excellent { background: #dcfce7; color: #166534; border: 3px solid #16a34a; }
.score-good { background: #dbeafe; color: #1e40af; border: 3px solid #2563eb; }
.score-fair { background: #fef9c3; color: #854d0e; border: 3px solid #ca8a04; }
.score-poor { background: #fee2e2; color: #991b1b; border: 3px solid #dc2626; }
.kpi-grid {
    display: flex;
    gap: 12px;
    margin: 12px 0;
}
.kpi-box {
    flex: 1;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 12px;
    text-align: center;
}
.kpi-value {
    font-size: 20pt;
    font-weight: 700;
}
.kpi-label {
    font-size: 9pt;
    color: #64748b;
    margin-top: 4px;
}
.methodology {
    background: #f8fafc;
    border-left: 3px solid #1e40af;
    padding: 12px 16px;
    margin: 12px 0;
    font-size: 10pt;
}
.finding {
    background: #fffbeb;
    border-left: 3px solid #f59e0b;
    padding: 10px 14px;
    margin: 10px 0;
    font-size: 10pt;
}
.finding-critical {
    background: #fef2f2;
    border-left: 3px solid #dc2626;
}
.footer {
    margin-top: 40px;
    padding-top: 12px;
    border-top: 1px solid #e2e8f0;
    font-size: 8pt;
    color: #94a3b8;
    text-align: center;
}
.page-break {
    page-break-before: always;
}
p { margin: 6px 0; }
"""


def _severity_badge(severity: str) -> str:
    """Return an HTML badge span for a severity level."""
    cls = {
        "critical": "badge-red",
        "warning": "badge-yellow",
        "info": "badge-blue",
        "green": "badge-green",
        "excellent": "badge-green",
        "good": "badge-blue",
        "fair": "badge-yellow",
        "poor": "badge-red",
    }.get(severity.lower(), "badge-gray")
    return f'<span class="badge {cls}">{severity.upper()}</span>'


def _score_class(rating: str) -> str:
    """Return CSS class for score circle based on rating."""
    return f"score-{rating}" if rating in ("excellent", "good", "fair", "poor") else "score-fair"


def _threshold_badge(status: str) -> str:
    """Return badge for threshold status."""
    return _severity_badge(
        {"green": "green", "yellow": "warning", "red": "critical"}.get(status, status)
    )


def _format_date(dt: datetime | None) -> str:
    """Format a datetime for display."""
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d")


def _esc(text: Any) -> str:
    """HTML-escape a value."""
    s = str(text) if text is not None else ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class ReportGenerator:
    """Generate professional PDF reports for schedule analysis.

    Produces HTML documents styled with inline CSS, then converts to PDF
    via weasyprint.  All reports follow the structure defined in AACE RP
    29R-03 S5.3.

    Usage::

        gen = ReportGenerator()
        pdf_bytes = gen.generate_health_report(schedule, dcma_result, health_score, alerts)
        with open("report.pdf", "wb") as f:
            f.write(pdf_bytes)
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_health_report(
        self,
        schedule: Any,
        dcma_result: Any,
        health_score: Any,
        alerts: Any | None = None,
    ) -> bytes:
        """Generate Schedule Health Report PDF.

        Args:
            schedule: ParsedSchedule object.
            dcma_result: DCMA14Result from the analyzer.
            health_score: HealthScore from the calculator.
            alerts: Optional EarlyWarningResult.

        Returns:
            PDF bytes.
        """
        html = self._build_health_html(schedule, dcma_result, health_score, alerts)
        return self._html_to_pdf(html)

    def generate_comparison_report(
        self,
        baseline: Any,
        update: Any,
        comparison_result: Any,
    ) -> bytes:
        """Generate Comparison Report PDF.

        Args:
            baseline: Baseline ParsedSchedule.
            update: Update ParsedSchedule.
            comparison_result: ComparisonResult.

        Returns:
            PDF bytes.
        """
        html = self._build_comparison_html(baseline, update, comparison_result)
        return self._html_to_pdf(html)

    def generate_forensic_report(
        self,
        timeline: Any,
    ) -> bytes:
        """Generate Forensic Report PDF.

        Args:
            timeline: ForensicTimeline object.

        Returns:
            PDF bytes.
        """
        html = self._build_forensic_html(timeline)
        return self._html_to_pdf(html)

    def generate_tia_report(
        self,
        analysis: Any,
    ) -> bytes:
        """Generate TIA Report PDF.

        Args:
            analysis: TIAAnalysis object.

        Returns:
            PDF bytes.
        """
        html = self._build_tia_html(analysis)
        return self._html_to_pdf(html)

    def generate_risk_report(
        self,
        simulation_result: Any,
    ) -> bytes:
        """Generate Risk Report PDF.

        Args:
            simulation_result: SimulationResult object.

        Returns:
            PDF bytes.
        """
        html = self._build_risk_html(simulation_result)
        return self._html_to_pdf(html)

    def generate_monthly_review_report(
        self,
        schedule: Any,
        dcma_result: Any,
        health_score: Any,
        comparison_result: Any | None = None,
        alerts: Any | None = None,
        baseline: Any | None = None,
    ) -> bytes:
        """Generate Monthly Review Report PDF.

        A standardized monthly schedule update narrative combining health,
        progress, comparison delta, alerts, and action items per
        PMI PMBOK 7 S4.6 (Measurement Performance Domain) and
        CMAA (2019) S7 (Reporting).

        Args:
            schedule: Current ParsedSchedule (the update).
            dcma_result: DCMA14Result from the analyzer.
            health_score: HealthScore from the calculator.
            comparison_result: Optional ComparisonResult (current vs previous).
            alerts: Optional EarlyWarningResult.
            baseline: Optional baseline ParsedSchedule (for data summary).

        Returns:
            PDF bytes.
        """
        html = self._build_monthly_review_html(
            schedule,
            dcma_result,
            health_score,
            comparison_result,
            alerts,
            baseline,
        )
        return self._html_to_pdf(html)

    def generate_executive_summary(
        self,
        schedule: Any,
        scorecard: Any | None = None,
        dcma_result: Any | None = None,
        health_score: Any | None = None,
        delay_prediction: Any | None = None,
        delay_attribution: Any | None = None,
        cost_comparison: Any | None = None,
        program_rollup: dict | None = None,
    ) -> bytes:
        """Generate Executive Summary PDF — single-page project overview.

        Aggregates scorecard grades, health score, DCMA pass/fail,
        delay risk, responsible-party attribution, cost variance, and
        program-level context into a concise briefing suitable for
        program directors and stakeholders.

        Args:
            schedule: ParsedSchedule object.
            scorecard: Optional ScorecardResult.
            dcma_result: Optional DCMA14Result.
            health_score: Optional HealthScore.
            delay_prediction: Optional DelayPredictionResult.
            delay_attribution: Optional AttributionResult (party breakdown).
            cost_comparison: Optional CostComparisonResult (CBS variance).
            program_rollup: Optional dict from /programs/{id}/rollup
                (expects keys ``revision_count``, ``latest_metrics``,
                ``trend_direction``, ``trend_delta``).

        Returns:
            PDF bytes.

        References:
            PMI PMBOK 7 — Measurement Performance Domain,
            GAO Schedule Assessment Guide,
            AACE RP 29R-03 §5.3 — delay attribution and variance.
        """
        project_name = ""
        if schedule and hasattr(schedule, "projects") and schedule.projects:
            project_name = schedule.projects[0].proj_short_name or "Project"

        act_count = len(schedule.activities) if schedule else 0

        sections = [f"<h1>Executive Summary — {project_name}</h1>"]
        sections.append(
            f"<p class='subtitle'>Activities: {act_count} | Generated by MeridianIQ</p>"
        )

        if program_rollup:
            trend = program_rollup.get("trend_direction", "stable")
            trend_delta = program_rollup.get("trend_delta")
            trend_str = f" ({trend}, Δ {trend_delta:+.1f} pts)" if trend_delta is not None else ""
            sections.append(
                f"<h2>Program Context</h2>"
                f"<p>Revision <strong>{program_rollup.get('latest_revision_number', '?')}</strong>"
                f" of {program_rollup.get('revision_count', 1)} · "
                f"Health trend: <strong>{trend}</strong>{trend_str}</p>"
            )

        if scorecard:
            dims_html = "".join(
                f"<tr><td>{d.name}</td><td><strong>{d.grade}</strong></td>"
                f"<td>{d.score:.0f}/100</td></tr>"
                for d in scorecard.dimensions
            )
            sections.append(
                f"<h2>Schedule Scorecard: {scorecard.overall_grade} "
                f"({scorecard.overall_score:.0f}/100)</h2>"
                f"<table><tr><th>Dimension</th><th>Grade</th><th>Score</th></tr>"
                f"{dims_html}</table>"
            )
            if scorecard.recommendations:
                recs = "".join(f"<li>{r}</li>" for r in scorecard.recommendations[:5])
                sections.append(f"<h3>Recommendations</h3><ul>{recs}</ul>")

        if dcma_result:
            sections.append(
                f"<h2>DCMA 14-Point: {dcma_result.overall_score:.0f}/100 "
                f"({dcma_result.passed_count} passed, "
                f"{dcma_result.failed_count} failed)</h2>"
            )

        if health_score:
            sections.append(
                f"<h2>Health Score: {health_score.overall:.0f}/100 ({health_score.rating})</h2>"
            )

        if delay_prediction:
            sections.append(
                f"<h2>Delay Risk: {delay_prediction.project_risk_score:.0f}/100 "
                f"({delay_prediction.project_risk_level})</h2>"
                f"<p>Predicted completion delay: "
                f"{delay_prediction.predicted_completion_delay:.1f} days</p>"
            )

        if delay_attribution and getattr(delay_attribution, "total_delay_days", 0) > 0:
            parties_html = "".join(
                f"<tr><td>{p.party}</td><td>{p.delay_days:.1f}</td>"
                f"<td>{p.pct_of_total:.0f}%</td></tr>"
                for p in delay_attribution.parties
            )
            sections.append(
                f"<h2>Delay Attribution ({delay_attribution.total_delay_days:.0f} days total)</h2>"
                f"<p>Excusable: <strong>{delay_attribution.excusable_days:.1f}d</strong> · "
                f"Non-excusable: <strong>{delay_attribution.non_excusable_days:.1f}d</strong> · "
                f"Concurrent: <strong>{delay_attribution.concurrent_days:.1f}d</strong></p>"
                f"<table><tr><th>Party</th><th>Days</th><th>%</th></tr>{parties_html}</table>"
                f"<p class='subtitle'>Source: {delay_attribution.data_source}"
                f" — {delay_attribution.methodology}</p>"
            )

        if cost_comparison:
            direction = (
                "increase"
                if cost_comparison.total_budget_delta > 0
                else "decrease"
                if cost_comparison.total_budget_delta < 0
                else "unchanged"
            )
            sections.append(
                f"<h2>Cost Variance "
                f"({cost_comparison.snapshot_a} → {cost_comparison.snapshot_b})</h2>"
                f"<p>Program budget {direction}: "
                f"<strong>${cost_comparison.total_budget_delta / 1e6:+.1f}M</strong> "
                f"({cost_comparison.budget_variance_pct:+.1f}%)</p>"
                f"<p>CBS elements: {cost_comparison.changed_count} changed · "
                f"{cost_comparison.added_count} added · "
                f"{cost_comparison.removed_count} removed · "
                f"{cost_comparison.unchanged_count} unchanged</p>"
            )
            if cost_comparison.insights:
                variance_insights = "".join(f"<li>{i}</li>" for i in cost_comparison.insights[:5])
                sections.append(f"<ul>{variance_insights}</ul>")

        html = self._html_wrapper("Executive Summary", project_name, "\n".join(sections))
        return self._html_to_pdf(html)

    def generate_scl_protocol_report(
        self,
        schedule: Any,
        timeline: Any | None = None,
        attribution: Any | None = None,
        narrative: Any | None = None,
    ) -> bytes:
        """Generate an SCL Protocol Delay Analysis submission PDF.

        Structured per the SCL Delay and Disruption Protocol (2nd ed.) —
        the de-facto UK/Commonwealth standard for contractual delay
        claims. Sections map to SCL guidance on contemporaneous period
        analysis, responsibility attribution, and concurrency.

        Args:
            schedule: ParsedSchedule of the update / current status.
            timeline: Optional ForensicTimeline (multi-window CPA).
            attribution: Optional AttributionResult (party breakdown).
            narrative: Optional NarrativeReport (factual narrative).

        Returns:
            PDF bytes.

        References:
            SCL Delay and Disruption Protocol (2nd ed., 2017) §Appendix B;
            AACE RP 29R-03 cross-reference for methodology alignment.
        """
        project_name = ""
        if schedule and hasattr(schedule, "projects") and schedule.projects:
            project_name = schedule.projects[0].proj_short_name or "Project"

        sections = [
            self._methodology_box(
                "Prepared per the Society of Construction Law Delay and "
                "Disruption Protocol (2nd ed., 2017), Appendix B — Records. "
                "Contemporaneous Period Analysis methodology per AACE RP 29R-03 MIP 3.3."
            )
        ]

        sections.append("<h2>1. Factual Narrative</h2>" + self._narrative_sections_html(narrative))

        sections.append(
            "<h2>2. Contractual Milestone Status</h2>" + self._milestone_status_html(timeline)
        )

        sections.append("<h2>3. Critical Path Evolution</h2>" + self._cp_evolution_html(timeline))

        sections.append(
            "<h2>4. Contemporaneous Period Analysis (Windows)</h2>"
            + self._window_table_html(timeline)
        )

        sections.append(
            "<h2>5. Responsibility Attribution</h2>" + self._attribution_html(attribution)
        )

        sections.append(
            "<h2>6. Concurrency Assessment</h2>" + self._concurrency_html(attribution, timeline)
        )

        sections.append(
            "<h2>7. Records Appendix — Driving Activities</h2>"
            + self._driving_activities_html(timeline, attribution)
        )

        html = self._html_wrapper(
            "SCL Protocol Delay Analysis Submission",
            project_name,
            "\n".join(sections),
        )
        return self._html_to_pdf(html)

    def generate_aace_forensic_report(
        self,
        schedule: Any,
        timeline: Any | None = None,
        attribution: Any | None = None,
        scorecard: Any | None = None,
        half_step: Any | None = None,
        baseline: Any | None = None,
    ) -> bytes:
        """Generate an AACE RP 29R-03 §5.3 forensic schedule analysis report.

        Section structure follows AACE RP 29R-03 §5.3 (Forensic Schedule
        Analysis — Documentation Requirements) with explicit support for
        MIP 3.4 bifurcated analysis when a half-step result is supplied.

        Args:
            schedule: ParsedSchedule of the current / update state.
            timeline: Optional ForensicTimeline (required for most sections).
            attribution: Optional AttributionResult.
            scorecard: Optional ScorecardResult for executive summary.
            half_step: Optional HalfStepResult (MIP 3.4 bifurcated split).
            baseline: Optional baseline ParsedSchedule for §2 background.

        Returns:
            PDF bytes.

        References:
            AACE RP 29R-03 §5.3 — Forensic Schedule Analysis Documentation;
            MIP 3.3 (observational) and MIP 3.4 (half-step bifurcated).
        """
        project_name = ""
        if schedule and hasattr(schedule, "projects") and schedule.projects:
            project_name = schedule.projects[0].proj_short_name or "Project"

        sections = [
            self._methodology_box(
                "Prepared per AACE International Recommended Practice 29R-03, "
                "§5.3 Forensic Schedule Analysis — Documentation Requirements. "
                f"Method: MIP {'3.4 (Bifurcated)' if half_step else '3.3 (Observational / Contemporaneous)'}."
            )
        ]

        sections.append(
            "<h2>§5.3.1 Executive Summary</h2>"
            + self._aace_exec_summary_html(timeline, attribution, scorecard)
        )

        sections.append(
            "<h2>§5.3.2 Project Background &amp; Baseline Schedule</h2>"
            + self._project_background_html(schedule, baseline)
        )

        sections.append(
            "<h2>§5.3.3 Analysis Methodology</h2>"
            + self._methodology_detail_html(timeline, half_step)
        )

        sections.append(
            "<h2>§5.3.4 Schedule Updates &amp; Data Dates</h2>"
            + self._schedule_updates_html(timeline)
        )

        sections.append(
            "<h2>§5.3.5 Analysis Windows</h2>" + self._window_table_html(timeline, show_cp=True)
        )

        sections.append(
            "<h2>§5.3.6 Critical Path Tracking</h2>" + self._cp_evolution_html(timeline)
        )

        sections.append(
            "<h2>§5.3.7 Delay Attribution by Party</h2>" + self._attribution_html(attribution)
        )

        if half_step:
            sections.append(
                "<h2>§5.3.8 Bifurcated Analysis (MIP 3.4)</h2>" + self._half_step_html(half_step)
            )

        sections.append(
            "<h2>§5.3.9 Concurrency &amp; Interaction</h2>"
            + self._concurrency_html(attribution, timeline)
        )

        html = self._html_wrapper(
            "AACE RP 29R-03 §5.3 Forensic Schedule Analysis Report",
            project_name,
            "\n".join(sections),
        )
        return self._html_to_pdf(html)

    # ------------------------------------------------------------------
    # Submission-report HTML section helpers
    # ------------------------------------------------------------------

    def _narrative_sections_html(self, narrative: Any | None) -> str:
        if not narrative or not getattr(narrative, "sections", None):
            return "<p>No narrative content supplied.</p>"
        parts = []
        if getattr(narrative, "executive_summary", ""):
            parts.append(f"<p><em>{_esc(narrative.executive_summary)}</em></p>")
        for s in narrative.sections[:8]:
            parts.append(f"<h3>{_esc(s.title)}</h3><p>{_esc(s.content)}</p>")
        return "\n".join(parts) or "<p>No narrative content supplied.</p>"

    def _milestone_status_html(self, timeline: Any | None) -> str:
        if not timeline:
            return "<p>Contractual milestone data not supplied.</p>"
        contract = getattr(timeline, "contract_completion", None)
        current = getattr(timeline, "current_completion", None)
        total = getattr(timeline, "total_delay_days", 0.0) or 0.0
        return (
            "<table><tr><th>Contract Completion</th><th>Current Forecast</th>"
            "<th>Total Slippage (days)</th></tr>"
            f"<tr><td>{_esc(str(contract) if contract else '—')}</td>"
            f"<td>{_esc(str(current) if current else '—')}</td>"
            f"<td>{total:.1f}</td></tr></table>"
        )

    def _cp_evolution_html(self, timeline: Any | None) -> str:
        if not timeline or not getattr(timeline, "windows", None):
            return "<p>No window results supplied.</p>"
        rows = []
        for w in timeline.windows:
            win = getattr(w, "window", None)
            num = getattr(win, "window_number", None) if win else None
            start = getattr(win, "start_date", None) if win else None
            end = getattr(win, "end_date", None) if win else None
            joined = len(getattr(w, "cp_activities_joined", []) or [])
            left = len(getattr(w, "cp_activities_left", []) or [])
            driver = getattr(w, "driving_activity", "") or "—"
            rows.append(
                f"<tr><td>{num if num is not None else '—'}</td>"
                f"<td>{start or '—'} → {end or '—'}</td>"
                f"<td>+{joined} / −{left}</td>"
                f"<td>{_esc(driver)}</td></tr>"
            )
        return (
            "<table><tr><th>Window</th><th>Period</th><th>CP Δ (joined/left)</th>"
            "<th>Driving Activity</th></tr>" + "".join(rows) + "</table>"
        )

    def _window_table_html(self, timeline: Any | None, show_cp: bool = False) -> str:
        if not timeline or not getattr(timeline, "windows", None):
            return "<p>No forensic windows available.</p>"
        headers = ["Window", "Period", "Delay (days)", "Cumulative"]
        if show_cp:
            headers.append("CP Length")
        head = "".join(f"<th>{h}</th>" for h in headers)
        rows = []
        for w in timeline.windows:
            win = getattr(w, "window", None)
            num = getattr(win, "window_number", None) if win else None
            start = getattr(win, "start_date", None) if win else None
            end = getattr(win, "end_date", None) if win else None
            cells = [
                f"<td>{num if num is not None else '—'}</td>",
                f"<td>{start or '—'} → {end or '—'}</td>",
                f"<td>{w.delay_days:.1f}</td>",
                f"<td>{w.cumulative_delay:.1f}</td>",
            ]
            if show_cp:
                cp_len = len(getattr(w, "critical_path_end", []) or [])
                cells.append(f"<td>{cp_len}</td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")
        return f"<table><tr>{head}</tr>" + "".join(rows) + "</table>"

    def _attribution_html(self, attribution: Any | None) -> str:
        if not attribution or not getattr(attribution, "parties", None):
            return "<p>Delay attribution data not supplied.</p>"
        rows = "".join(
            f"<tr><td><strong>{_esc(p.party)}</strong></td>"
            f"<td>{p.delay_days:.1f}</td><td>{p.pct_of_total:.0f}%</td>"
            f"<td>{p.activity_count}</td></tr>"
            for p in attribution.parties
        )
        summary = (
            f"<p>Total: <strong>{attribution.total_delay_days:.1f} days</strong> · "
            f"Excusable: {attribution.excusable_days:.1f}d · "
            f"Non-excusable: {attribution.non_excusable_days:.1f}d · "
            f"Concurrent: {attribution.concurrent_days:.1f}d · "
            f"Source: {attribution.data_source}</p>"
        )
        return (
            summary
            + "<table><tr><th>Party</th><th>Days</th><th>%</th><th>Activities</th></tr>"
            + rows
            + "</table>"
        )

    def _concurrency_html(self, attribution: Any | None, timeline: Any | None) -> str:
        concurrent = 0.0
        if attribution:
            concurrent = getattr(attribution, "concurrent_days", 0.0) or 0.0
        if concurrent <= 0:
            return "<p>No concurrent delay periods identified.</p>"
        return (
            f"<p>Concurrent delay: <strong>{concurrent:.1f} days</strong>. "
            "Overlapping owner/contractor delays identified through forensic "
            "window comparison. Per SCL Protocol §10, concurrent periods may "
            "qualify the contractor for time but not cost relief.</p>"
        )

    def _driving_activities_html(self, timeline: Any | None, attribution: Any | None) -> str:
        names: list[str] = []
        if timeline and getattr(timeline, "windows", None):
            for w in timeline.windows:
                drv = getattr(w, "driving_activity", "") or ""
                if drv and drv not in names:
                    names.append(drv)
        if attribution and getattr(attribution, "parties", None):
            for p in attribution.parties:
                for a in (getattr(p, "top_activities", None) or [])[:3]:
                    if a not in names:
                        names.append(a)
        if not names:
            return "<p>No driving activities identified.</p>"
        items = "".join(f"<li>{_esc(n)}</li>" for n in names[:25])
        return f"<ul>{items}</ul>"

    def _aace_exec_summary_html(
        self, timeline: Any | None, attribution: Any | None, scorecard: Any | None
    ) -> str:
        parts = []
        if timeline:
            parts.append(
                f"<p>Total project delay: <strong>"
                f"{getattr(timeline, 'total_delay_days', 0.0):.1f} days</strong> "
                f"across {len(getattr(timeline, 'windows', []) or [])} windows.</p>"
            )
        if attribution:
            parts.append(
                f"<p>Attributed: Excusable {attribution.excusable_days:.1f}d · "
                f"Non-excusable {attribution.non_excusable_days:.1f}d · "
                f"Concurrent {attribution.concurrent_days:.1f}d.</p>"
            )
        if scorecard:
            parts.append(
                f"<p>Schedule quality at analysis: "
                f"<strong>{scorecard.overall_grade}</strong> "
                f"({scorecard.overall_score:.0f}/100).</p>"
            )
        return "\n".join(parts) or "<p>Summary data not supplied.</p>"

    def _project_background_html(self, schedule: Any, baseline: Any | None) -> str:
        act_count = len(schedule.activities) if schedule else 0
        baseline_acts = len(baseline.activities) if baseline else 0
        baseline_line = (
            f"Baseline: {baseline_acts} activities."
            if baseline
            else "No baseline schedule supplied."
        )
        return f"<p>Current schedule: {act_count} activities. {baseline_line}</p>"

    def _methodology_detail_html(self, timeline: Any | None, half_step: Any | None) -> str:
        method = (
            "MIP 3.4 — Modeled/Additive Bifurcated (half-step analysis)"
            if half_step
            else "MIP 3.3 — Observational / Contemporaneous Period Analysis"
        )
        window_count = len(getattr(timeline, "windows", []) or []) if timeline else 0
        return (
            f"<p><strong>Method:</strong> {method}</p>"
            f"<p><strong>Analysis windows:</strong> {window_count}</p>"
            "<p>Delay measured per window by comparing the as-planned "
            "completion against the contemporaneous re-forecast, with "
            "critical-path evolution tracked for each interval.</p>"
        )

    def _schedule_updates_html(self, timeline: Any | None) -> str:
        if not timeline or not getattr(timeline, "windows", None):
            return "<p>No schedule updates supplied.</p>"
        rows = []
        for i, w in enumerate(timeline.windows, start=1):
            win = getattr(w, "window", None)
            start = getattr(win, "start_date", None) if win else None
            end = getattr(win, "end_date", None) if win else None
            rows.append(
                f"<tr><td>Update {i}</td>"
                f"<td>{start or '—'}</td>"
                f"<td>{end or '—'}</td></tr>"
            )
        return (
            "<table><tr><th>Schedule</th><th>Start</th><th>End</th></tr>"
            + "".join(rows)
            + "</table>"
        )

    def _half_step_html(self, half_step: Any) -> str:
        progress = getattr(half_step, "progress_effect_days", 0.0) or 0.0
        revision = getattr(half_step, "revision_effect_days", 0.0) or 0.0
        total = getattr(half_step, "total_delay_days", 0.0) or 0.0
        invariant = getattr(half_step, "invariant_holds", False)
        return (
            f"<p>Total: <strong>{total:.1f} days</strong> — "
            f"Progress effect: {progress:+.1f}d · Revision effect: {revision:+.1f}d · "
            f"Invariant holds: {'Yes' if invariant else 'No'}.</p>"
            "<p>Per MIP 3.4, the total delay is decomposed into the effect "
            "of progress made during the window (actual work) and the "
            "effect of schedule revisions (logic, duration or date changes) "
            "so they can be attributed independently.</p>"
        )

    def generate_calendar_report(
        self,
        schedule: Any,
        validation_result: Any,
    ) -> bytes:
        """Generate Calendar Validation Report PDF.

        Args:
            schedule: ParsedSchedule object.
            validation_result: CalendarValidationResult.

        Returns:
            PDF bytes.

        References:
            DCMA 14-Point Check #13 — Calendar adequacy.
            AACE RP 49R-06 — Schedule Health Assessment.
        """
        project_name = ""
        if schedule and hasattr(schedule, "projects") and schedule.projects:
            project_name = schedule.projects[0].proj_short_name or "Project"

        sections = []
        vr = validation_result

        sections.append(
            f"<h2>Calendar Health: {vr.grade} ({vr.score:.0f}/100)</h2>"
            f"<p>Calendars: {vr.total_calendars} | "
            f"Tasks with calendar: {vr.tasks_with_calendar} / {vr.total_tasks} | "
            f"Default: {'Yes' if vr.has_default else 'No'}</p>"
        )

        if vr.issues:
            rows = "".join(
                f"<tr><td class='{'red' if i.severity == 'critical' else 'amber' if i.severity == 'warning' else ''}'>"
                f"{i.severity.upper()}</td><td>{_esc(i.description)}</td>"
                f"<td>{i.affected_tasks}</td></tr>"
                for i in vr.issues
            )
            sections.append(
                "<h2>Findings</h2>"
                "<table><tr><th>Severity</th><th>Description</th><th>Tasks</th></tr>"
                f"{rows}</table>"
            )

        if vr.calendars:
            rows = "".join(
                f"<tr><td>{_esc(c.name)}</td><td>{'Yes' if c.is_default else ''}</td>"
                f"<td>{c.day_hr_cnt}</td><td>{c.week_hr_cnt}</td>"
                f"<td>{c.working_days_per_week}</td>"
                f"<td>{c.task_count} ({c.pct_of_tasks}%)</td></tr>"
                for c in vr.calendars
            )
            sections.append(
                "<h2>Calendar Details</h2>"
                "<table><tr><th>Name</th><th>Default</th><th>Hrs/Day</th>"
                "<th>Hrs/Week</th><th>Days/Week</th><th>Tasks</th></tr>"
                f"{rows}</table>"
            )

        sections.append(f"<p class='methodology'>{vr.methodology}</p>")
        body = "\n".join(sections)
        html = self._html_wrapper("Calendar Validation Report", project_name, body)
        return self._html_to_pdf(html)

    def generate_attribution_report(
        self,
        schedule: Any,
        attribution_result: Any,
    ) -> bytes:
        """Generate Delay Attribution Report PDF.

        Args:
            schedule: ParsedSchedule object.
            attribution_result: AttributionResult.

        Returns:
            PDF bytes.

        References:
            AACE RP 29R-03 — Forensic Schedule Analysis.
            AACE RP 52R-06 — Time Impact Analysis.
            SCL Delay and Disruption Protocol.
        """
        project_name = ""
        if schedule and hasattr(schedule, "projects") and schedule.projects:
            project_name = schedule.projects[0].proj_short_name or "Project"

        ar = attribution_result
        sections = []

        sections.append(
            f"<h2>Delay Attribution Summary</h2>"
            f"<p>Total Delay: <strong>{ar.total_delay_days} days</strong> | "
            f"Excusable: {ar.excusable_days}d | "
            f"Non-Excusable: {ar.non_excusable_days}d | "
            f"Concurrent: {ar.concurrent_days}d | "
            f"Source: {ar.data_source}</p>"
        )

        if ar.parties:
            rows = "".join(
                f"<tr><td><strong>{_esc(p.party)}</strong></td>"
                f"<td>{p.delay_days}d</td><td>{p.pct_of_total}%</td>"
                f"<td>{p.activity_count}</td>"
                f"<td>{', '.join(p.top_activities[:3]) if p.top_activities else '-'}</td></tr>"
                for p in ar.parties
            )
            sections.append(
                "<h2>Party Breakdown</h2>"
                "<table><tr><th>Party</th><th>Delay</th><th>%</th>"
                "<th>Activities</th><th>Top Drivers</th></tr>"
                f"{rows}</table>"
            )

        sections.append(f"<p class='methodology'>{ar.methodology}</p>")
        body = "\n".join(sections)
        html = self._html_wrapper("Delay Attribution Report", project_name, body)
        return self._html_to_pdf(html)

    def generate_narrative_report(
        self,
        schedule: Any,
        narrative: Any,
    ) -> bytes:
        """Generate Narrative Schedule Report PDF.

        Converts a ``NarrativeReport`` (text + severity-tagged sections)
        into a formatted PDF suitable for claims submission or monthly
        reporting.

        Args:
            schedule: ParsedSchedule object (used for project fallback).
            narrative: NarrativeReport with executive_summary + sections.

        Returns:
            PDF bytes.

        References:
            AACE RP 29R-03 §5.3 — Forensic Schedule Report documentation.
            SCL Delay and Disruption Protocol — Narrative presentation.
        """
        project_name = narrative.project_name or ""
        if not project_name and schedule and getattr(schedule, "projects", None):
            project_name = schedule.projects[0].proj_short_name or "Project"

        parts: list[str] = []

        # Executive summary
        if getattr(narrative, "executive_summary", ""):
            parts.append(f"<h2>Executive Summary</h2><p>{_esc(narrative.executive_summary)}</p>")

        # Data date line
        data_date = getattr(narrative, "data_date", "") or ""
        generated_at = getattr(narrative, "generated_at", "") or ""
        if data_date or generated_at:
            parts.append(
                f"<p class='methodology'>Data date: {_esc(data_date or 'N/A')} "
                f"&middot; Report generated: {_esc(generated_at)}</p>"
            )

        # Sections, styled by severity
        for s in getattr(narrative, "sections", []) or []:
            sev = (getattr(s, "severity", "") or "info").lower()
            cls = "finding finding-critical" if sev == "critical" else "finding"
            badge_color = {
                "critical": "#dc2626",
                "warning": "#d97706",
                "info": "#2563eb",
            }.get(sev, "#4b5563")
            badge = (
                f"<span style='display:inline-block;padding:2px 8px;margin-right:8px;"
                f"background:{badge_color};color:#fff;border-radius:10px;"
                f"font-size:10px;font-weight:600;text-transform:uppercase;'>{_esc(sev)}</span>"
            )
            content_html = _esc(getattr(s, "content", "")).replace("\n", "<br/>")
            parts.append(f"<h2>{badge}{_esc(s.title)}</h2><div class='{cls}'>{content_html}</div>")

        if not parts:
            parts.append("<p>No narrative content available for this schedule.</p>")

        body = "\n".join(parts)
        html = self._html_wrapper(
            narrative.title or "Schedule Narrative Report",
            project_name,
            body,
        )
        return self._html_to_pdf(html)

    # ------------------------------------------------------------------
    # PDF conversion
    # ------------------------------------------------------------------

    def _html_to_pdf(self, html: str) -> bytes:
        """Convert HTML string to PDF bytes using weasyprint.

        Falls back to returning UTF-8 HTML bytes if weasyprint is not
        installed (allows running in environments without system deps).
        """
        try:
            from weasyprint import HTML

            return HTML(string=html).write_pdf()
        except ImportError:
            logger.warning("weasyprint not installed -- returning raw HTML bytes instead of PDF")
            return html.encode("utf-8")
        except Exception as exc:
            logger.warning("weasyprint PDF generation failed: %s -- returning HTML", exc)
            return html.encode("utf-8")

    # ------------------------------------------------------------------
    # Common HTML building blocks
    # ------------------------------------------------------------------

    def _html_wrapper(self, title: str, project_name: str, body: str) -> str:
        """Wrap body content in a full HTML document."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{_esc(title)}</title>
<style>{_CSS}</style>
</head>
<body>

<div class="header">
    <div class="brand">MeridianIQ</div>
    <div class="subtitle">Schedule Intelligence Platform</div>
    <div class="report-title">{_esc(title)}</div>
    <div class="report-meta">Project: {_esc(project_name)} | Generated: {now}</div>
</div>

{body}

<div class="footer">
    Generated by MeridianIQ &mdash; MIT License &mdash;
    Methodology per AACE RP 29R-03, DCMA 14-Point Assessment,
    GAO Schedule Assessment Guide (2020), PMI Practice Standard for Scheduling
</div>

</body>
</html>"""

    def _section(self, title: str, content: str, page_break: bool = False) -> str:
        """Build an HTML section with optional page break."""
        pb = ' class="page-break"' if page_break else ""
        return f"<div{pb}><h2>{_esc(title)}</h2>{content}</div>"

    def _methodology_box(self, text: str) -> str:
        """Build a methodology citation box."""
        return f'<div class="methodology">{text}</div>'

    def _finding_box(self, text: str, critical: bool = False) -> str:
        """Build a finding/alert box."""
        cls = "finding finding-critical" if critical else "finding"
        return f'<div class="{cls}">{text}</div>'

    def _table(self, headers: list[str], rows: list[list[str]]) -> str:
        """Build an HTML table."""
        hdr = "".join(f"<th>{_esc(h)}</th>" for h in headers)
        body = ""
        for row in rows:
            cells = "".join(f"<td>{c}</td>" for c in row)  # cells may contain HTML
            body += f"<tr>{cells}</tr>\n"
        return f"<table><thead><tr>{hdr}</tr></thead><tbody>{body}</tbody></table>"

    def _kpi_grid(self, kpis: list[tuple[str, str, str]]) -> str:
        """Build a KPI grid. Each KPI is (value, label, color_class)."""
        boxes = ""
        for val, label, color in kpis:
            boxes += f"""<div class="kpi-box">
                <div class="kpi-value" style="color:{color}">{val}</div>
                <div class="kpi-label">{_esc(label)}</div>
            </div>"""
        return f'<div class="kpi-grid">{boxes}</div>'

    # ------------------------------------------------------------------
    # Helper: extract project info
    # ------------------------------------------------------------------

    def _project_info(self, schedule: Any) -> dict[str, str]:
        """Extract project metadata from a ParsedSchedule."""
        info: dict[str, str] = {
            "Project Name": "Unknown",
            "Data Date": "N/A",
            "Activities": str(len(schedule.activities)),
            "Relationships": str(len(schedule.relationships)),
            "Calendars": str(len(schedule.calendars)),
            "WBS Elements": str(len(schedule.wbs_nodes)),
        }
        if schedule.projects:
            proj = schedule.projects[0]
            info["Project Name"] = proj.proj_short_name or "Unknown"
            dd = proj.last_recalc_date or proj.sum_data_date
            if dd:
                info["Data Date"] = _format_date(dd)
        return info

    def _project_info_table(self, schedule: Any) -> str:
        """Build a project info summary table."""
        info = self._project_info(schedule)
        rows = [[_esc(k), _esc(v)] for k, v in info.items()]
        return self._table(["Field", "Value"], rows)

    # ------------------------------------------------------------------
    # Report Type 1: Schedule Health Report
    # ------------------------------------------------------------------

    def _build_health_html(
        self,
        schedule: Any,
        dcma_result: Any,
        health_score: Any,
        alerts: Any | None = None,
    ) -> str:
        """Build HTML for Schedule Health Report."""
        project_name = "Unknown"
        if schedule.projects:
            project_name = schedule.projects[0].proj_short_name or "Unknown"

        body = ""

        # Executive Summary
        rating = health_score.rating
        overall = health_score.overall
        exec_text = (
            f"The schedule received an overall health score of <strong>{overall:.0f}/100</strong> "
            f"({_severity_badge(rating)}). "
        )
        if rating == "excellent":
            exec_text += (
                "The schedule demonstrates strong structural quality, appropriate float "
                "distribution, and complete logic integrity. It meets all four GAO "
                "characteristics: comprehensive, well-constructed, credible, and controlled."
            )
        elif rating == "good":
            exec_text += (
                "The schedule is generally well-constructed with minor areas for improvement. "
                "It meets most GAO quality characteristics with minor gaps."
            )
        elif rating == "fair":
            exec_text += (
                "The schedule has significant gaps in two or more quality characteristics. "
                "Corrective action is recommended to improve schedule reliability."
            )
        else:
            exec_text += (
                "The schedule has fundamental issues that compromise its reliability as a "
                "project management tool. Immediate corrective action is required."
            )

        dcma_passed = dcma_result.passed_count if hasattr(dcma_result, "passed_count") else 0
        dcma_failed = dcma_result.failed_count if hasattr(dcma_result, "failed_count") else 0
        exec_text += (
            f" The DCMA 14-Point Assessment resulted in {dcma_passed} passed and "
            f"{dcma_failed} failed checks."
        )

        body += self._section("1. Executive Summary", f"<p>{exec_text}</p>")

        # Methodology
        body += self._section(
            "2. Methodology",
            self._methodology_box(
                "Schedule health assessment performed per DCMA 14-Point Assessment methodology. "
                "Composite health score calculated per GAO Schedule Assessment Guide (2020) "
                "four characteristics framework (comprehensive, well-constructed, credible, "
                "controlled). Float analysis per AACE RP 49R-06. Logic integrity per DCMA "
                "checks #6 and #7. Trend direction per GAO S9 schedule surveillance."
            ),
        )

        # Data Summary
        body += self._section(
            "3. Data Summary",
            self._project_info_table(schedule),
        )

        # Health Score Breakdown
        score_cls = _score_class(rating)
        score_html = f"""
        <div style="display:flex; align-items:center; margin:16px 0;">
            <div class="score-circle {score_cls}">{overall:.0f}</div>
            <div>
                <div style="font-size:16pt; font-weight:600;">
                    Overall Health: {_severity_badge(rating)}
                </div>
                <div style="font-size:10pt; color:#64748b; margin-top:4px;">
                    Trend: {_esc(health_score.trend_arrow)}
                </div>
            </div>
        </div>
        """

        score_html += self._kpi_grid(
            [
                (
                    f"{health_score.dcma_raw:.0f}",
                    f"DCMA Score (x{health_score.details.get('weights', {}).get('dcma', 0.4):.0%})",
                    "#1e40af",
                ),
                (
                    f"{health_score.float_raw:.0f}",
                    f"Float Health (x{health_score.details.get('weights', {}).get('float', 0.25):.0%})",
                    "#0891b2",
                ),
                (
                    f"{health_score.logic_raw:.0f}",
                    f"Logic Integrity (x{health_score.details.get('weights', {}).get('logic', 0.2):.0%})",
                    "#7c3aed",
                ),
                (
                    f"{health_score.trend_raw:.0f}",
                    f"Trend Direction (x{health_score.details.get('weights', {}).get('trend', 0.15):.0%})",
                    "#059669",
                ),
            ]
        )

        score_html += self._table(
            ["Component", "Raw Score", "Weight", "Weighted"],
            [
                [
                    "DCMA Structural Quality",
                    f"{health_score.dcma_raw:.1f}",
                    "40%",
                    f"{health_score.dcma_component:.1f}",
                ],
                [
                    "Float Health",
                    f"{health_score.float_raw:.1f}",
                    "25%",
                    f"{health_score.float_component:.1f}",
                ],
                [
                    "Logic Integrity",
                    f"{health_score.logic_raw:.1f}",
                    "20%",
                    f"{health_score.logic_component:.1f}",
                ],
                [
                    "Trend Direction",
                    f"{health_score.trend_raw:.1f}",
                    "15%",
                    f"{health_score.trend_component:.1f}",
                ],
                ["<strong>Total</strong>", "", "", f"<strong>{overall:.1f}</strong>"],
            ],
        )

        body += self._section("4. Health Score Analysis", score_html, page_break=True)

        # DCMA Results
        dcma_html = ""
        if hasattr(dcma_result, "metrics"):
            rows = []
            for m in dcma_result.metrics:
                status = _severity_badge("green" if m.passed else "critical")
                rows.append(
                    [
                        f"#{m.number}",
                        _esc(m.name),
                        f"{m.value:.1f}{m.unit}",
                        f"{m.threshold}{m.unit}",
                        status,
                    ]
                )
            dcma_html += self._table(
                ["#", "Check", "Value", "Threshold", "Status"],
                rows,
            )
            dcma_score = dcma_result.overall_score if hasattr(dcma_result, "overall_score") else 0
            dcma_html += f"<p><strong>Overall DCMA Score: {dcma_score:.1f}%</strong> "
            dcma_html += f"({dcma_passed} of {dcma_passed + dcma_failed} checks passed)</p>"

        body += self._section("5. DCMA 14-Point Assessment", dcma_html, page_break=True)

        # Alerts
        if alerts and hasattr(alerts, "alerts") and alerts.alerts:
            alert_html = f"<p>{alerts.total_alerts} alerts detected "
            alert_html += f"({alerts.critical_count} critical, {alerts.warning_count} warning, "
            alert_html += f"{alerts.info_count} informational).</p>"

            rows = []
            for a in alerts.alerts[:20]:
                rows.append(
                    [
                        _severity_badge(a.severity),
                        _esc(a.title),
                        f"{a.projected_impact_days:.1f}d",
                        f"{a.confidence:.0%}",
                        f"{a.alert_score:.1f}",
                    ]
                )
            alert_html += self._table(
                ["Severity", "Alert", "Impact", "Confidence", "Score"],
                rows,
            )

            body += self._section("6. Early Warning Alerts", alert_html, page_break=True)

        # Conclusions
        conclusions = "<p>Based on the analysis:</p><ul>"
        if rating in ("poor", "fair"):
            conclusions += "<li>The schedule requires significant corrective action to meet quality standards.</li>"
        if dcma_failed > 3:
            conclusions += (
                f"<li>{dcma_failed} DCMA checks failed, indicating structural quality issues.</li>"
            )
        if alerts and hasattr(alerts, "critical_count") and alerts.critical_count > 0:
            conclusions += (
                f"<li>{alerts.critical_count} critical alerts require immediate attention.</li>"
            )
        if rating == "excellent":
            conclusions += "<li>The schedule meets all quality criteria and can be relied upon for project management decisions.</li>"
        conclusions += "</ul>"
        conclusions += "<p><strong>Recommendation:</strong> "
        if rating in ("poor", "fair"):
            conclusions += "Address failed DCMA checks and critical alerts before using this schedule for baseline purposes."
        else:
            conclusions += (
                "Continue monitoring schedule health through regular updates and trend analysis."
            )
        conclusions += "</p>"

        body += self._section(
            "7. Conclusions & Recommendations" if alerts else "6. Conclusions & Recommendations",
            conclusions,
            page_break=True,
        )

        return self._html_wrapper("Schedule Health Report", project_name, body)

    # ------------------------------------------------------------------
    # Report Type 2: Comparison Report
    # ------------------------------------------------------------------

    def _build_comparison_html(
        self,
        baseline: Any,
        update: Any,
        result: Any,
    ) -> str:
        """Build HTML for Comparison Report."""
        project_name = "Unknown"
        if update.projects:
            project_name = update.projects[0].proj_short_name or "Unknown"

        body = ""

        # Executive summary
        n_mods = (
            len(result.activity_modifications) if hasattr(result, "activity_modifications") else 0
        )
        n_added = len(result.activities_added) if hasattr(result, "activities_added") else 0
        n_deleted = len(result.activities_deleted) if hasattr(result, "activities_deleted") else 0
        n_flags = len(result.manipulation_flags) if hasattr(result, "manipulation_flags") else 0
        changed_pct = result.changed_percentage if hasattr(result, "changed_percentage") else 0

        exec_text = (
            f"Comparison of two schedule versions identified {changed_pct:.1f}% of activities "
            f"with changes. {n_added} activities were added, {n_deleted} deleted, "
            f"and {n_mods} modified. "
        )
        if n_flags > 0:
            exec_text += (
                f"<strong>{n_flags} manipulation indicators</strong> were detected, "
                f"requiring further investigation."
            )
        else:
            exec_text += "No manipulation indicators were detected."

        body += self._section("1. Executive Summary", f"<p>{exec_text}</p>")

        # Methodology
        body += self._section(
            "2. Methodology",
            self._methodology_box(
                "Schedule comparison performed per AACE RP 29R-03 Method 3 "
                "(Contemporaneous Period Analysis). Activity matching by task_code with "
                "fallback to task_id. Float analysis per AACE RP 49R-06. Manipulation "
                "detection checks for retroactive date changes, logic deletion, constraint "
                "additions, and progress overrides per DCMA guidance."
            ),
        )

        # Data Summary
        data_html = "<h3>Baseline Schedule</h3>"
        data_html += self._project_info_table(baseline)
        data_html += "<h3>Update Schedule</h3>"
        data_html += self._project_info_table(update)

        body += self._section("3. Data Summary", data_html)

        # Delta Summary
        delta_html = self._kpi_grid(
            [
                (str(n_added), "Activities Added", "#059669"),
                (str(n_deleted), "Activities Deleted", "#dc2626"),
                (str(n_mods), "Activities Modified", "#2563eb"),
                (f"{changed_pct:.1f}%", "Changed", "#7c3aed"),
            ]
        )

        # Relationship changes
        rels_added = (
            len(result.relationships_added) if hasattr(result, "relationships_added") else 0
        )
        rels_deleted = (
            len(result.relationships_deleted) if hasattr(result, "relationships_deleted") else 0
        )
        rels_modified = (
            len(result.relationships_modified) if hasattr(result, "relationships_modified") else 0
        )

        delta_html += self._table(
            ["Change Type", "Count"],
            [
                ["Activities Added", str(n_added)],
                ["Activities Deleted", str(n_deleted)],
                ["Activities Modified", str(n_mods)],
                ["Relationships Added", str(rels_added)],
                ["Relationships Deleted", str(rels_deleted)],
                ["Relationships Modified", str(rels_modified)],
                [
                    "Critical Path Changed",
                    "Yes" if getattr(result, "critical_path_changed", False) else "No",
                ],
            ],
        )

        body += self._section("4. Analysis Results", delta_html, page_break=True)

        # Manipulation Indicators
        if n_flags > 0:
            flag_html = f"<p>{n_flags} potential manipulation indicators detected:</p>"
            rows = []
            for f in result.manipulation_flags[:30]:
                rows.append(
                    [
                        _severity_badge(f.severity),
                        _esc(f.indicator),
                        _esc(f.task_name if hasattr(f, "task_name") else f.task_id),
                        _esc(f.description),
                    ]
                )
            flag_html += self._table(
                ["Severity", "Indicator", "Activity", "Description"],
                rows,
            )
            body += self._section("5. Manipulation Indicators", flag_html, page_break=True)

        # Float changes
        float_changes = getattr(result, "significant_float_changes", [])
        if float_changes:
            float_html = f"<p>{len(float_changes)} significant float changes detected:</p>"
            rows = []
            for fc in float_changes[:30]:
                direction = _severity_badge(
                    "critical" if fc.direction == "deteriorating" else "green"
                )
                rows.append(
                    [
                        _esc(fc.task_name if hasattr(fc, "task_name") else fc.task_id),
                        f"{fc.old_float:.1f}",
                        f"{fc.new_float:.1f}",
                        f"{fc.delta:.1f}",
                        direction,
                    ]
                )
            float_html += self._table(
                ["Activity", "Old Float", "New Float", "Delta", "Direction"],
                rows,
            )
            section_num = 6 if n_flags > 0 else 5
            body += self._section(f"{section_num}. Significant Float Changes", float_html)

        # Conclusions
        conclusions = "<p>Based on the comparison analysis:</p><ul>"
        if n_flags > 0:
            conclusions += f"<li><strong>{n_flags} manipulation indicators</strong> require investigation.</li>"
        if getattr(result, "critical_path_changed", False):
            conclusions += "<li>The critical path has changed between versions.</li>"
        if rels_deleted > 5:
            conclusions += f"<li>{rels_deleted} relationships were deleted, which may compromise schedule integrity.</li>"
        conclusions += "</ul>"

        body += self._section(
            f"{7 if n_flags > 0 else 6}. Conclusions & Recommendations",
            conclusions,
            page_break=True,
        )

        return self._html_wrapper("Schedule Comparison Report", project_name, body)

    # ------------------------------------------------------------------
    # Report Type 3: Forensic Report
    # ------------------------------------------------------------------

    def _build_forensic_html(self, timeline: Any) -> str:
        """Build HTML for Forensic Report."""
        project_name = getattr(timeline, "project_name", "Unknown")

        body = ""

        total_delay = getattr(timeline, "total_delay_days", 0)
        n_windows = len(timeline.windows) if hasattr(timeline, "windows") else 0
        contract = _format_date(getattr(timeline, "contract_completion", None))
        current = _format_date(getattr(timeline, "current_completion", None))

        exec_text = (
            f"Forensic analysis of {n_windows} schedule windows identified a total project "
            f"delay of <strong>{total_delay:.0f} days</strong>. "
            f"Contract completion: {contract}. Current projected completion: {current}."
        )
        body += self._section("1. Executive Summary", f"<p>{exec_text}</p>")

        body += self._section(
            "2. Methodology",
            self._methodology_box(
                "Forensic schedule analysis performed per AACE RP 29R-03 Method 4 "
                "(Window Analysis / Contemporaneous Period Analysis). Each window compares "
                "consecutive schedule updates to isolate delay causes within defined periods. "
                "Critical path analysis per AACE RP 49R-06."
            ),
        )

        # Windows summary
        if hasattr(timeline, "windows") and timeline.windows:
            rows = []
            for w in timeline.windows:
                win = getattr(w, "window", None)
                rows.append(
                    [
                        str(win.window_number if win else ""),
                        _format_date(
                            getattr(win, "start_date", None)
                            if win
                            else getattr(w, "start_date", None)
                        ),
                        _format_date(
                            getattr(win, "end_date", None) if win else getattr(w, "end_date", None)
                        ),
                        f"{w.delay_days:.1f}",
                        f"{w.cumulative_delay:.1f}",
                        _esc(getattr(w, "driving_activity", "N/A")),
                    ]
                )
            windows_html = self._table(
                ["Window", "Start", "End", "Delay (d)", "Cumulative (d)", "Driving Activity"],
                rows,
            )
            body += self._section("3. Window Analysis Results", windows_html, page_break=True)

        # Half-step bifurcation (MIP 3.4) — if available
        has_bifurcation = hasattr(timeline, "windows") and any(
            getattr(w, "half_step_result", None) is not None for w in timeline.windows
        )
        section_num = 4

        if has_bifurcation:
            bif_rows = []
            total_progress = 0.0
            total_revision = 0.0
            for w in timeline.windows:
                hs = getattr(w, "half_step_result", None)
                if hs is None:
                    continue
                win = getattr(w, "window", None)
                win_id = str(win.window_number if win else "")
                p_eff = getattr(hs, "progress_effect", 0.0)
                r_eff = getattr(hs, "revision_effect", 0.0)
                t_del = getattr(hs, "total_delay", 0.0)
                inv = "Yes" if getattr(hs, "invariant_check", False) else "No"
                bif_rows.append([win_id, f"{p_eff:+.1f}", f"{r_eff:+.1f}", f"{t_del:+.1f}", inv])
                total_progress += p_eff
                total_revision += r_eff

            bif_html = self._methodology_box(
                "Bifurcation per AACE RP 29R-03 MIP 3.4 &mdash; each window&rsquo;s "
                "delay is split into <strong>progress effect</strong> (actual work "
                "performance) and <strong>revision effect</strong> (logic/plan changes) "
                "by constructing an intermediate half-step schedule."
            )
            bif_html += self._table(
                ["Window", "Progress (d)", "Revision (d)", "Total (d)", "Invariant"],
                bif_rows,
            )
            bif_html += self._kpi_grid(
                [
                    (f"{total_progress:+.1f}d", "Total Progress Effect", "#3b82f6"),
                    (f"{total_revision:+.1f}d", "Total Revision Effect", "#f59e0b"),
                ]
            )
            body += self._section(
                f"{section_num}. Bifurcation Analysis (MIP 3.4)",
                bif_html,
                page_break=True,
            )
            section_num += 1

        # Delay summary
        body += self._section(
            f"{section_num}. Delay Summary",
            self._kpi_grid(
                [
                    (f"{total_delay:.0f}d", "Total Delay", "#dc2626"),
                    (str(n_windows), "Windows Analyzed", "#2563eb"),
                    (contract, "Contract Completion", "#64748b"),
                    (current, "Current Completion", "#dc2626"),
                ]
            ),
            page_break=True,
        )
        section_num += 1

        body += self._section(
            f"{section_num}. Conclusions",
            f"<p>The forensic window analysis identified {total_delay:.0f} days of project delay "
            f"across {n_windows} analysis windows. Each delay was isolated to specific activities "
            f"and time periods per AACE RP 29R-03 methodology.</p>",
        )

        return self._html_wrapper("Forensic Schedule Analysis Report", project_name, body)

    # ------------------------------------------------------------------
    # Report Type 4: TIA Report
    # ------------------------------------------------------------------

    def _build_tia_html(self, analysis: Any) -> str:
        """Build HTML for TIA Report."""
        project_name = getattr(analysis, "project_name", "Unknown")

        body = ""

        net_delay = getattr(analysis, "net_delay", 0)
        owner_delay = getattr(analysis, "total_owner_delay", 0)
        contractor_delay = getattr(analysis, "total_contractor_delay", 0)
        shared_delay = getattr(analysis, "total_shared_delay", 0)
        n_fragments = len(analysis.fragments) if hasattr(analysis, "fragments") else 0

        exec_text = (
            f"Time Impact Analysis of {n_fragments} delay fragments identified a net project "
            f"delay of <strong>{net_delay:.0f} days</strong>. "
            f"Owner-responsible: {owner_delay:.0f}d, Contractor-responsible: {contractor_delay:.0f}d"
        )
        if shared_delay > 0:
            exec_text += f", Shared: {shared_delay:.0f}d"
        exec_text += "."

        body += self._section("1. Executive Summary", f"<p>{exec_text}</p>")

        body += self._section(
            "2. Methodology",
            self._methodology_box(
                "Time Impact Analysis performed per AACE RP 52R-06 (Prospective TIA). "
                "Each delay fragment was inserted into the impacted schedule and the "
                "critical path recalculated to measure completion date impact. "
                "Concurrent delay identification per Braimah & Ndekugri (2008)."
            ),
        )

        body += self._section(
            "3. Delay Summary",
            self._kpi_grid(
                [
                    (f"{net_delay:.0f}d", "Net Delay", "#dc2626"),
                    (f"{owner_delay:.0f}d", "Owner Delay", "#f59e0b"),
                    (f"{contractor_delay:.0f}d", "Contractor Delay", "#2563eb"),
                    (str(n_fragments), "Fragments", "#7c3aed"),
                ]
            ),
        )

        # Fragment results
        if hasattr(analysis, "results") and analysis.results:
            rows = []
            for r in analysis.results:
                rows.append(
                    [
                        _esc(r.fragment_name),
                        _esc(r.responsible_party),
                        f"{r.delay_days:.1f}d",
                        "Yes" if r.critical_path_affected else "No",
                        _esc(r.delay_type),
                    ]
                )
            body += self._section(
                "4. Fragment Analysis Results",
                self._table(
                    ["Fragment", "Responsible", "Delay", "CP Affected", "Type"],
                    rows,
                ),
                page_break=True,
            )

        body += self._section(
            "5. Conclusions",
            f"<p>The TIA identified {net_delay:.0f} days of net project delay from "
            f"{n_fragments} delay events. Owner-responsible delays total {owner_delay:.0f} days "
            f"and contractor-responsible delays total {contractor_delay:.0f} days.</p>",
            page_break=True,
        )

        return self._html_wrapper("Time Impact Analysis Report", project_name, body)

    # ------------------------------------------------------------------
    # Report Type 5: Risk Report
    # ------------------------------------------------------------------

    def _build_risk_html(self, result: Any) -> str:
        """Build HTML for Risk Report."""
        project_name = getattr(result, "project_name", "Unknown")

        body = ""

        deterministic = getattr(result, "deterministic_days", 0)
        mean_days = getattr(result, "mean_days", 0)
        std_dev = getattr(result, "std_dev_days", 0)
        iterations = getattr(result, "iterations", 0)

        # Find key P-values
        p_values = getattr(result, "p_values", [])
        p50 = p80 = p90 = 0.0
        for pv in p_values:
            if pv.percentile == 50:
                p50 = pv.duration_days
            if pv.percentile == 80:
                p80 = pv.duration_days
            if pv.percentile == 90:
                p90 = pv.duration_days

        exec_text = (
            f"Monte Carlo simulation with {iterations:,} iterations produced a mean project "
            f"duration of <strong>{mean_days:.0f} days</strong> (deterministic: {deterministic:.0f}d). "
            f"P50={p50:.0f}d, P80={p80:.0f}d, P90={p90:.0f}d."
        )
        body += self._section("1. Executive Summary", f"<p>{exec_text}</p>")

        body += self._section(
            "2. Methodology",
            self._methodology_box(
                "Schedule Risk Analysis (QSRA) performed per AACE RP 57R-09. "
                "Monte Carlo simulation using Latin Hypercube sampling with duration "
                "uncertainty distributions. Critical path recalculated for each iteration. "
                "Sensitivity analysis identifies activities with highest correlation to "
                "project duration."
            ),
        )

        body += self._section(
            "3. Simulation Results",
            self._kpi_grid(
                [
                    (f"{deterministic:.0f}d", "Deterministic", "#64748b"),
                    (f"{mean_days:.0f}d", "Mean", "#2563eb"),
                    (f"{p50:.0f}d", "P50", "#059669"),
                    (f"{p80:.0f}d", "P80", "#f59e0b"),
                    (f"{p90:.0f}d", "P90", "#dc2626"),
                ]
            ),
        )

        # P-value table
        if p_values:
            rows = []
            for pv in p_values:
                rows.append(
                    [
                        f"P{pv.percentile}",
                        f"{pv.duration_days:.1f}",
                        _format_date(pv.completion_date)
                        if hasattr(pv, "completion_date") and pv.completion_date
                        else "N/A",
                    ]
                )
            body += self._table(
                ["Percentile", "Duration (days)", "Completion Date"],
                rows,
            )

        # Statistics
        stats_html = self._table(
            ["Statistic", "Value"],
            [
                ["Iterations", f"{iterations:,}"],
                ["Deterministic Duration", f"{deterministic:.1f} days"],
                ["Mean Duration", f"{mean_days:.1f} days"],
                ["Standard Deviation", f"{std_dev:.1f} days"],
                ["P50 Duration", f"{p50:.1f} days"],
                ["P80 Duration", f"{p80:.1f} days"],
                ["P90 Duration", f"{p90:.1f} days"],
            ],
        )
        body += self._section("4. Statistical Summary", stats_html, page_break=True)

        # Sensitivity
        sensitivity = getattr(result, "sensitivity", [])
        if sensitivity:
            rows = []
            for s in sensitivity[:15]:
                rows.append(
                    [
                        _esc(
                            getattr(s, "task_code", s.task_id if hasattr(s, "task_id") else "N/A")
                        ),
                        _esc(getattr(s, "task_name", "N/A")),
                        f"{s.correlation:.3f}",
                        f"{getattr(s, 'contribution_pct', 0):.1f}%",
                    ]
                )
            body += self._section(
                "5. Sensitivity Analysis",
                "<p>Activities most correlated with project completion:</p>"
                + self._table(["Activity", "Name", "Correlation", "Contribution"], rows),
                page_break=True,
            )

        body += self._section(
            "6. Conclusions",
            f"<p>The simulation indicates a {((p80 - deterministic) / deterministic * 100):.1f}% "
            f"schedule risk contingency is needed to achieve P80 confidence. The deterministic "
            f"schedule duration of {deterministic:.0f} days corresponds to approximately "
            f"P{self._estimate_percentile(p_values, deterministic)} confidence level.</p>",
        )

        return self._html_wrapper("Schedule Risk Analysis Report", project_name, body)

    # ------------------------------------------------------------------
    # Report Type 6: Monthly Review Report
    # ------------------------------------------------------------------

    def _build_monthly_review_html(
        self,
        schedule: Any,
        dcma_result: Any,
        health_score: Any,
        comparison_result: Any | None = None,
        alerts: Any | None = None,
        baseline: Any | None = None,
    ) -> str:
        """Build HTML for Monthly Review Report.

        Per PMI PMBOK 7 S4.6 and CMAA (2019) S7.
        """
        project_name = "Unknown"
        data_date = "N/A"
        if schedule.projects:
            proj = schedule.projects[0]
            project_name = proj.proj_short_name or "Unknown"
            dd = proj.last_recalc_date or proj.sum_data_date
            if dd:
                data_date = _format_date(dd)

        body = ""

        # ── 1. Executive Summary ──
        rating = health_score.rating
        overall = health_score.overall
        n_activities = len(schedule.activities)
        n_rels = len(schedule.relationships)

        # Progress counts
        complete = sum(
            1 for a in schedule.activities if getattr(a, "status_code", "").upper() == "TK_COMPLETE"
        )
        in_progress = sum(
            1 for a in schedule.activities if getattr(a, "status_code", "").upper() == "TK_ACTIVE"
        )
        not_started = n_activities - complete - in_progress

        pct_complete = (complete / n_activities * 100) if n_activities else 0

        exec_text = (
            f"This report summarises the schedule status as of data date "
            f"<strong>{data_date}</strong>. The schedule contains "
            f"{n_activities:,} activities and {n_rels:,} relationships. "
            f"Overall health score: <strong>{overall:.0f}/100</strong> "
            f"({_severity_badge(rating)}). "
            f"Progress: {complete:,} complete ({pct_complete:.0f}%), "
            f"{in_progress:,} in progress, {not_started:,} not started."
        )

        if comparison_result:
            changed_pct = getattr(comparison_result, "changed_percentage", 0)
            n_added = len(getattr(comparison_result, "activities_added", []))
            n_deleted = len(getattr(comparison_result, "activities_deleted", []))
            exec_text += (
                f" Compared to the previous update: {changed_pct:.1f}% of activities changed, "
                f"{n_added} added, {n_deleted} deleted."
            )

        body += self._section("1. Executive Summary", f"<p>{exec_text}</p>")

        # ── 2. Methodology ──
        body += self._section(
            "2. Methodology",
            self._methodology_box(
                "Monthly schedule review performed per PMI PMBOK 7 Section 4.6 "
                "(Measurement Performance Domain) and CMAA (2019) Section 7 "
                "(Reporting). Schedule quality assessed per DCMA 14-Point "
                "Assessment. Health score per GAO Schedule Assessment Guide (2020). "
                "Comparison analysis per AACE RP 29R-03. Early warning alerts per "
                "AACE RP 49R-06 and GAO Section 9 (Schedule Surveillance)."
            ),
        )

        # ── 3. Data Summary ──
        data_html = self._project_info_table(schedule)
        if baseline:
            data_html += "<h3>Previous Update (Baseline)</h3>"
            data_html += self._project_info_table(baseline)
        body += self._section("3. Data Summary", data_html)

        # ── 4. Progress Overview ──
        progress_html = self._kpi_grid(
            [
                (f"{pct_complete:.0f}%", "Overall Progress", "#059669"),
                (f"{complete:,}", "Complete", "#16a34a"),
                (f"{in_progress:,}", "In Progress", "#2563eb"),
                (f"{not_started:,}", "Not Started", "#64748b"),
            ]
        )

        # Progress bar
        ip_pct = (in_progress / n_activities * 100) if n_activities else 0
        ns_pct = 100 - pct_complete - ip_pct
        progress_html += f"""
        <div style="margin:16px 0;">
            <div style="background:#e2e8f0; border-radius:6px; overflow:hidden; height:24px;
                        display:flex;">
                <div style="width:{pct_complete:.1f}%; background:#16a34a; height:100%;"></div>
                <div style="width:{ip_pct:.1f}%; background:#2563eb; height:100%;"></div>
                <div style="width:{ns_pct:.1f}%; background:#e2e8f0; height:100%;"></div>
            </div>
            <div style="display:flex; gap:16px; margin-top:4px; font-size:9pt; color:#64748b;">
                <span>
                    <span style="display:inline-block;width:10px;height:10px;
                                 background:#16a34a;border-radius:2px;"></span>
                    Complete
                </span>
                <span>
                    <span style="display:inline-block;width:10px;height:10px;
                                 background:#2563eb;border-radius:2px;"></span>
                    In Progress
                </span>
                <span>
                    <span style="display:inline-block;width:10px;height:10px;
                                 background:#e2e8f0;border:1px solid #cbd5e1;
                                 border-radius:2px;"></span>
                    Not Started
                </span>
            </div>
        </div>
        """

        body += self._section("4. Progress Overview", progress_html, page_break=True)

        # ── 5. Schedule Health ──
        score_cls = _score_class(rating)
        health_html = f"""
        <div style="display:flex; align-items:center; margin:16px 0;">
            <div class="score-circle {score_cls}">{overall:.0f}</div>
            <div>
                <div style="font-size:16pt; font-weight:600;">
                    Health: {_severity_badge(rating)}
                </div>
                <div style="font-size:10pt; color:#64748b; margin-top:4px;">
                    Trend: {_esc(health_score.trend_arrow)}
                </div>
            </div>
        </div>
        """

        health_html += self._kpi_grid(
            [
                (f"{health_score.dcma_raw:.0f}", "DCMA Score", "#1e40af"),
                (f"{health_score.float_raw:.0f}", "Float Health", "#0891b2"),
                (f"{health_score.logic_raw:.0f}", "Logic Integrity", "#7c3aed"),
                (f"{health_score.trend_raw:.0f}", "Trend", "#059669"),
            ]
        )

        # DCMA summary table
        dcma_passed = dcma_result.passed_count if hasattr(dcma_result, "passed_count") else 0
        dcma_failed = dcma_result.failed_count if hasattr(dcma_result, "failed_count") else 0
        if hasattr(dcma_result, "metrics"):
            rows = []
            for m in dcma_result.metrics:
                status = _severity_badge("green" if m.passed else "critical")
                rows.append(
                    [
                        f"#{m.number}",
                        _esc(m.name),
                        f"{m.value:.1f}{m.unit}",
                        f"{m.threshold}{m.unit}",
                        status,
                    ]
                )
            health_html += self._table(
                ["#", "Check", "Value", "Threshold", "Status"],
                rows,
            )
            health_html += (
                f"<p><strong>{dcma_passed} of {dcma_passed + dcma_failed} checks passed"
                f"</strong></p>"
            )

        body += self._section("5. Schedule Health & DCMA Assessment", health_html, page_break=True)

        # ── 6. Comparison Delta (if available) ──
        section_num = 6
        if comparison_result:
            n_mods = len(getattr(comparison_result, "activity_modifications", []))
            n_added = len(getattr(comparison_result, "activities_added", []))
            n_deleted = len(getattr(comparison_result, "activities_deleted", []))
            changed_pct = getattr(comparison_result, "changed_percentage", 0)
            rels_added = len(getattr(comparison_result, "relationships_added", []))
            rels_deleted = len(getattr(comparison_result, "relationships_deleted", []))
            cp_changed = getattr(comparison_result, "critical_path_changed", False)

            delta_html = self._kpi_grid(
                [
                    (f"{changed_pct:.1f}%", "Activities Changed", "#7c3aed"),
                    (str(n_added), "Added", "#059669"),
                    (str(n_deleted), "Deleted", "#dc2626"),
                    (str(n_mods), "Modified", "#2563eb"),
                ]
            )

            delta_html += self._table(
                ["Metric", "Value"],
                [
                    ["Activities Added", str(n_added)],
                    ["Activities Deleted", str(n_deleted)],
                    ["Activities Modified", str(n_mods)],
                    ["Relationships Added", str(rels_added)],
                    ["Relationships Deleted", str(rels_deleted)],
                    [
                        "Critical Path Changed",
                        f"{_severity_badge('critical' if cp_changed else 'green')}"
                        f" {'Yes' if cp_changed else 'No'}",
                    ],
                ],
            )

            # Manipulation flags
            manip_flags = getattr(comparison_result, "manipulation_flags", [])
            if manip_flags:
                classification = getattr(comparison_result, "manipulation_classification", "normal")
                score = getattr(comparison_result, "manipulation_score", 0)
                delta_html += self._finding_box(
                    f"<strong>Manipulation Classification: "
                    f"{_severity_badge(classification.upper().replace('_', ' '))}</strong> "
                    f"&mdash; Risk Score: {score} &mdash; "
                    f"{len(manip_flags)} indicator(s) detected.",
                    critical=classification == "red_flag",
                )

            body += self._section(
                f"{section_num}. Changes Since Last Update",
                delta_html,
                page_break=True,
            )
            section_num += 1

        # ── 7. Early Warning Alerts (if available) ──
        if alerts and hasattr(alerts, "alerts") and alerts.alerts:
            alert_html = self._kpi_grid(
                [
                    (str(alerts.total_alerts), "Total Alerts", "#64748b"),
                    (str(alerts.critical_count), "Critical", "#dc2626"),
                    (str(alerts.warning_count), "Warning", "#f59e0b"),
                    (str(alerts.info_count), "Info", "#2563eb"),
                ]
            )

            rows = []
            for a in alerts.alerts[:25]:
                rows.append(
                    [
                        _severity_badge(a.severity),
                        _esc(a.title),
                        _esc(getattr(a, "description", "")),
                        f"{a.projected_impact_days:.1f}d",
                        f"{a.confidence:.0%}",
                    ]
                )
            alert_html += self._table(
                ["Severity", "Alert", "Description", "Impact", "Confidence"],
                rows,
            )

            body += self._section(
                f"{section_num}. Early Warning Alerts",
                alert_html,
                page_break=True,
            )
            section_num += 1

        # ── N. Key Issues & Action Items (template section) ──
        issues_html = """
        <p>The following issues and action items were identified during this review period:</p>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Issue / Action Item</th>
                    <th>Owner</th>
                    <th>Due Date</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>1</td>
                    <td><em>[To be completed by reviewer]</em></td>
                    <td></td>
                    <td></td>
                    <td></td>
                </tr>
                <tr>
                    <td>2</td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td></td>
                </tr>
                <tr>
                    <td>3</td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td></td>
                </tr>
            </tbody>
        </table>
        """

        body += self._section(
            f"{section_num}. Key Issues & Action Items",
            issues_html,
            page_break=True,
        )
        section_num += 1

        # ── N+1. Conclusions ──
        conclusions = "<p>Based on this monthly review:</p><ul>"
        if rating in ("poor", "fair"):
            conclusions += (
                "<li>The schedule health score indicates significant quality issues. "
                "Corrective action is recommended before the next update.</li>"
            )
        elif rating == "excellent":
            conclusions += (
                "<li>The schedule is in excellent condition and meets all GAO quality "
                "characteristics.</li>"
            )
        else:
            conclusions += (
                "<li>The schedule is in good condition with minor areas for improvement.</li>"
            )

        if comparison_result:
            cp_changed = getattr(comparison_result, "critical_path_changed", False)
            if cp_changed:
                conclusions += (
                    "<li>The critical path has changed since the last update &mdash; "
                    "review driving activities.</li>"
                )
            manip_flags = getattr(comparison_result, "manipulation_flags", [])
            if manip_flags:
                conclusions += (
                    f"<li>{len(manip_flags)} manipulation indicator(s) detected &mdash; "
                    f"investigate before accepting this update.</li>"
                )

        if alerts and hasattr(alerts, "critical_count") and alerts.critical_count > 0:
            conclusions += (
                f"<li>{alerts.critical_count} critical alert(s) require immediate attention.</li>"
            )

        conclusions += "</ul>"
        conclusions += (
            "<p><strong>Next Update Due:</strong> <em>[Date]</em></p>"
            "<p><strong>Prepared By:</strong> <em>[Name / Title]</em></p>"
            "<p><strong>Reviewed By:</strong> <em>[Name / Title]</em></p>"
        )

        body += self._section(
            f"{section_num}. Conclusions & Next Steps",
            conclusions,
            page_break=True,
        )

        return self._html_wrapper("Monthly Schedule Review Report", project_name, body)

    @staticmethod
    def _estimate_percentile(p_values: list, target_days: float) -> int:
        """Estimate the percentile for a given duration from P-value table."""
        if not p_values:
            return 50
        for pv in p_values:
            if pv.duration_days >= target_days:
                return pv.percentile
        return 99
