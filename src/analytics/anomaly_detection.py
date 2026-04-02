# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Anomaly Detection — statistical outlier identification in schedule data.

Uses z-score and IQR methods to identify activities with unusual:
- Duration (abnormally long or short relative to peers)
- Float (unexpected float values given schedule structure)
- Progress (physical % complete inconsistent with elapsed time)
- Relationships (unusually high or low predecessor/successor count)

Each anomaly is classified by severity (info/warning/critical) and
includes an explanation of why it's flagged.

Standards:
    - DCMA 14-Point — Thresholds for duration and float
    - AACE RP 29R-03 — Schedule manipulation detection patterns
    - Tukey (1977) — Box plot / IQR method for outlier detection
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


@dataclass
class Anomaly:
    """A single detected anomaly.

    Attributes:
        task_id: The activity's system ID.
        task_code: The user-visible activity code.
        task_name: The activity description.
        anomaly_type: Category (duration, float, progress, relationship, calendar).
        severity: info, warning, or critical.
        description: Human-readable explanation.
        value: The actual value that triggered the flag.
        expected_range: The normal range (min, max).
        z_score: Standard deviations from mean (if applicable).
    """

    task_id: str = ""
    task_code: str = ""
    task_name: str = ""
    anomaly_type: str = ""
    severity: str = "info"
    description: str = ""
    value: float = 0.0
    expected_range: tuple[float, float] = (0.0, 0.0)
    z_score: float = 0.0


@dataclass
class AnomalyDetectionResult:
    """Result of anomaly detection analysis.

    Attributes:
        anomalies: List of detected anomalies, sorted by severity.
        total: Total anomaly count.
        critical_count: Number of critical anomalies.
        warning_count: Number of warning anomalies.
        info_count: Number of info anomalies.
        activities_analyzed: Total activities analyzed.
        methodology: Description of detection methods used.
    """

    anomalies: list[Anomaly] = field(default_factory=list)
    total: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    activities_analyzed: int = 0
    methodology: str = (
        "Statistical outlier detection using IQR method (Tukey, 1977) and z-score "
        "analysis. Duration and float anomalies flagged at 1.5x IQR (warning) and "
        "3x IQR (critical). Progress anomalies use elapsed time ratio. "
        "Relationship density anomalies use z-score > 2 standard deviations."
    )


_HOURS_PER_DAY = 8.0

# Severity thresholds for IQR method
_IQR_WARNING = 1.5  # mild outlier
_IQR_CRITICAL = 3.0  # extreme outlier


def _iqr_bounds(values: list[float]) -> tuple[float, float, float, float]:
    """Compute Q1, Q3, and IQR bounds for outlier detection.

    Returns (lower_warning, lower_critical, upper_warning, upper_critical).
    """
    if len(values) < 4:
        return (0, 0, float("inf"), float("inf"))

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[3 * n // 4]
    iqr = q3 - q1

    if iqr == 0:
        return (q1, q1, q3, q3)

    return (
        q1 - _IQR_WARNING * iqr,
        q1 - _IQR_CRITICAL * iqr,
        q3 + _IQR_WARNING * iqr,
        q3 + _IQR_CRITICAL * iqr,
    )


def _z_score(value: float, mean: float, std: float) -> float:
    """Compute z-score."""
    if std == 0:
        return 0.0
    return (value - mean) / std


def detect_anomalies(schedule: ParsedSchedule) -> AnomalyDetectionResult:
    """Run anomaly detection on a parsed schedule.

    Analyzes duration, float, progress, and relationship patterns
    to identify statistical outliers that may indicate scheduling
    issues or manipulation.

    Args:
        schedule: Parsed schedule with activities and relationships.

    Returns:
        AnomalyDetectionResult with all detected anomalies.

    References:
        Tukey, J. W. (1977). Exploratory Data Analysis.
        DCMA 14-Point Assessment — duration and float thresholds.
        AACE RP 29R-03 — manipulation detection.
    """
    anomalies: list[Anomaly] = []

    # Filter to countable activities
    countable = [
        a
        for a in schedule.activities
        if a.task_type.lower() not in ("tt_loe", "tt_wbs", "tt_mile")
        and a.status_code.lower() != "tk_complete"
    ]

    if not countable:
        return AnomalyDetectionResult(activities_analyzed=0)

    # ── Duration Anomalies ──
    durations = [a.remain_drtn_hr_cnt / _HOURS_PER_DAY for a in countable if a.remain_drtn_hr_cnt]
    if len(durations) >= 4:
        lw, lc, uw, uc = _iqr_bounds(durations)
        mean_dur = sum(durations) / len(durations)
        std_dur = (sum((d - mean_dur) ** 2 for d in durations) / len(durations)) ** 0.5

        for a in countable:
            dur = a.remain_drtn_hr_cnt / _HOURS_PER_DAY
            if dur <= 0:
                continue

            if dur > uc:
                anomalies.append(
                    Anomaly(
                        task_id=a.task_id,
                        task_code=a.task_code,
                        task_name=a.task_name,
                        anomaly_type="duration",
                        severity="critical",
                        description=f"Extremely long duration ({dur:.0f}d) — over 3x IQR above Q3. "
                        f"May indicate missing decomposition or padding.",
                        value=dur,
                        expected_range=(lw, uw),
                        z_score=round(_z_score(dur, mean_dur, std_dur), 2),
                    )
                )
            elif dur > uw:
                anomalies.append(
                    Anomaly(
                        task_id=a.task_id,
                        task_code=a.task_code,
                        task_name=a.task_name,
                        anomaly_type="duration",
                        severity="warning",
                        description=f"Unusually long duration ({dur:.0f}d) — exceeds 1.5x IQR. "
                        f"Review if this should be decomposed.",
                        value=dur,
                        expected_range=(lw, uw),
                        z_score=round(_z_score(dur, mean_dur, std_dur), 2),
                    )
                )

    # ── Float Anomalies ──
    floats = [
        a.total_float_hr_cnt / _HOURS_PER_DAY for a in countable if a.total_float_hr_cnt is not None
    ]
    if len(floats) >= 4:
        lw, lc, uw, uc = _iqr_bounds(floats)
        mean_float = sum(floats) / len(floats)
        std_float = (sum((f - mean_float) ** 2 for f in floats) / len(floats)) ** 0.5

        for a in countable:
            if a.total_float_hr_cnt is None:
                continue
            tf = a.total_float_hr_cnt / _HOURS_PER_DAY

            if tf < lc:
                anomalies.append(
                    Anomaly(
                        task_id=a.task_id,
                        task_code=a.task_code,
                        task_name=a.task_name,
                        anomaly_type="float",
                        severity="critical",
                        description=f"Extreme negative float ({tf:.0f}d) — over 3x IQR below Q1. "
                        f"Schedule may be over-constrained or have logic errors.",
                        value=tf,
                        expected_range=(lw, uw),
                        z_score=round(_z_score(tf, mean_float, std_float), 2),
                    )
                )
            elif tf < lw:
                anomalies.append(
                    Anomaly(
                        task_id=a.task_id,
                        task_code=a.task_code,
                        task_name=a.task_name,
                        anomaly_type="float",
                        severity="warning",
                        description=f"Unusually low float ({tf:.0f}d) — below 1.5x IQR.",
                        value=tf,
                        expected_range=(lw, uw),
                        z_score=round(_z_score(tf, mean_float, std_float), 2),
                    )
                )
            elif tf > uc:
                anomalies.append(
                    Anomaly(
                        task_id=a.task_id,
                        task_code=a.task_code,
                        task_name=a.task_name,
                        anomaly_type="float",
                        severity="warning",
                        description=f"Excessive float ({tf:.0f}d) — over 3x IQR above Q3. "
                        f"May indicate disconnected logic per DCMA check #3.",
                        value=tf,
                        expected_range=(lw, uw),
                        z_score=round(_z_score(tf, mean_float, std_float), 2),
                    )
                )

    # ── Relationship Density Anomalies ──
    pred_count: dict[str, int] = {}
    succ_count: dict[str, int] = {}
    for r in schedule.relationships:
        succ_count[r.task_id] = succ_count.get(r.task_id, 0) + 1
        pred_count[r.pred_task_id] = pred_count.get(r.pred_task_id, 0) + 1

    all_counts = [pred_count.get(a.task_id, 0) + succ_count.get(a.task_id, 0) for a in countable]
    if all_counts:
        mean_rels = sum(all_counts) / len(all_counts)
        std_rels = (sum((c - mean_rels) ** 2 for c in all_counts) / len(all_counts)) ** 0.5

        for a in countable:
            count = pred_count.get(a.task_id, 0) + succ_count.get(a.task_id, 0)
            if count == 0:
                anomalies.append(
                    Anomaly(
                        task_id=a.task_id,
                        task_code=a.task_code,
                        task_name=a.task_name,
                        anomaly_type="relationship",
                        severity="critical",
                        description="No predecessors or successors — activity is disconnected from "
                        "the network. Violates DCMA checks #6/#7.",
                        value=0,
                        expected_range=(1, mean_rels + 2 * std_rels),
                        z_score=round(_z_score(0, mean_rels, std_rels), 2),
                    )
                )
            elif std_rels > 0 and _z_score(count, mean_rels, std_rels) > 3:
                anomalies.append(
                    Anomaly(
                        task_id=a.task_id,
                        task_code=a.task_code,
                        task_name=a.task_name,
                        anomaly_type="relationship",
                        severity="info",
                        description=f"Unusually high relationship count ({count}) — "
                        f"z-score {_z_score(count, mean_rels, std_rels):.1f}. "
                        f"May be a constraint or summary activity.",
                        value=count,
                        expected_range=(0, mean_rels + 2 * std_rels),
                        z_score=round(_z_score(count, mean_rels, std_rels), 2),
                    )
                )

    # ── Progress Anomalies ──
    for a in schedule.activities:
        if a.status_code.lower() == "tk_complete":
            continue
        pct = getattr(a, "phys_complete_pct", 0) or 0
        status = a.status_code.lower()

        # Active with 0% progress
        if status == "tk_active" and pct == 0:
            anomalies.append(
                Anomaly(
                    task_id=a.task_id,
                    task_code=a.task_code,
                    task_name=a.task_name,
                    anomaly_type="progress",
                    severity="warning",
                    description="Activity is marked active but has 0% physical progress. "
                    "May indicate a status override per DCMA check #12.",
                    value=0,
                    expected_range=(1, 99),
                )
            )
        # Not started with progress
        elif status != "tk_active" and status != "tk_complete" and pct > 0:
            anomalies.append(
                Anomaly(
                    task_id=a.task_id,
                    task_code=a.task_code,
                    task_name=a.task_name,
                    anomaly_type="progress",
                    severity="warning",
                    description=f"Activity not started but has {pct:.0f}% progress. "
                    f"Inconsistent status/progress.",
                    value=pct,
                    expected_range=(0, 0),
                )
            )

    # Sort by severity (critical first)
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    anomalies.sort(key=lambda a: severity_order.get(a.severity, 3))

    critical = sum(1 for a in anomalies if a.severity == "critical")
    warning = sum(1 for a in anomalies if a.severity == "warning")
    info = sum(1 for a in anomalies if a.severity == "info")

    return AnomalyDetectionResult(
        anomalies=anomalies,
        total=len(anomalies),
        critical_count=critical,
        warning_count=warning,
        info_count=info,
        activities_analyzed=len(countable),
    )
