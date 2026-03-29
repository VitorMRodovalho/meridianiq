# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Professional PDF report generator per AACE RP 29R-03 S5.3.

Generates court-submittable reports with:
- Executive summary (auto-generated)
- Methodology statement with standard citations
- Data summary (project info, data date, activity count)
- Analysis results (tables, findings)
- Conclusions & recommendations

Supports 5 report types:
1. Schedule Health Report: DCMA results, health score, float distribution, alerts
2. Comparison Report: Delta summary, manipulation indicators, changes by WBS
3. Forensic Report: Timeline, delay waterfall, windows analysis
4. TIA Report: Fragment analysis, CP impact, compliance check
5. Risk Report: Monte Carlo results, P-values, sensitivity

Standards:
    - AACE RP 29R-03 S5.3 -- Documentation
    - CMAA (2019) S7 -- Reporting
    - DCMA 14-Point Assessment -- Schedule quality metrics
    - AACE RP 52R-06 -- Time Impact Analysis
    - AACE RP 57R-09 -- Schedule Risk Analysis
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
                rows.append(
                    [
                        str(w.window_number),
                        _format_date(getattr(w, "start_date", None)),
                        _format_date(getattr(w, "end_date", None)),
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

        # Delay waterfall
        body += self._section(
            "4. Delay Summary",
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

        body += self._section(
            "5. Conclusions",
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

    @staticmethod
    def _estimate_percentile(p_values: list, target_days: float) -> int:
        """Estimate the percentile for a given duration from P-value table."""
        if not p_values:
            return 50
        for pv in p_values:
            if pv.duration_days >= target_days:
                return pv.percentile
        return 99
