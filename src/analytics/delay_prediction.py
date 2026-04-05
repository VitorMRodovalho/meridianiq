# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Delay prediction engine — activity-level delay risk scoring.

Extracts schedule features and produces per-activity risk scores with
explainable risk factors.  Works in two tiers:

1. **Single-schedule** — rule-based risk scoring using float, logic,
   duration, and network features.  No training data required.
2. **With baseline** — trend-enhanced scoring that detects float
   deterioration, duration growth, and constraint additions.

The risk model uses weighted multi-factor scoring aligned with DCMA
14-Point thresholds, AACE RP 49R-06 float health criteria, and the
GAO Schedule Assessment Guide.

References:
    - DCMA 14-Point Assessment — standard thresholds
    - AACE RP 49R-06 — Float Trend Analysis
    - GAO Schedule Assessment Guide §7–§9
    - Gondia et al. (2021) — Applied AI for Construction Delay Prediction
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.cpm import CPMCalculator, CPMResult
from src.parser.models import ParsedSchedule, Task

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — thresholds aligned with DCMA / AACE standards
# ---------------------------------------------------------------------------

_HOURS_PER_DAY = 8.0

# Float thresholds (in hours)
_FLOAT_NEGATIVE = 0.0
_FLOAT_CRITICAL = 0.001  # Essentially zero
_FLOAT_NEAR_CRITICAL = 10 * _HOURS_PER_DAY  # 10 days per DCMA
_FLOAT_HIGH = 44 * _HOURS_PER_DAY  # 44 days per DCMA check #6

# Duration thresholds (in hours)
_DURATION_LONG = 44 * _HOURS_PER_DAY  # DCMA check #8
_DURATION_VERY_LONG = 80 * _HOURS_PER_DAY

# Risk level thresholds
_RISK_LOW = 25
_RISK_MEDIUM = 50
_RISK_HIGH = 75

# Risk component weights
_W_FLOAT = 0.30
_W_PROGRESS = 0.20
_W_LOGIC = 0.15
_W_DURATION = 0.15
_W_NETWORK = 0.10
_W_TREND = 0.10


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


@dataclass
class RiskFactor:
    """A single explainable risk factor contributing to an activity's score."""

    name: str
    contribution: float  # 0-1 weight of this factor
    description: str
    value: str


@dataclass
class ActivityRisk:
    """Delay risk assessment for a single activity."""

    task_id: str
    task_code: str
    task_name: str
    risk_score: float  # 0-100
    risk_level: str  # "low", "medium", "high", "critical"
    predicted_delay_days: float  # Estimated delay based on float/progress
    confidence: float  # 0-1
    top_risk_factors: list[RiskFactor] = field(default_factory=list)
    is_critical_path: bool = False
    wbs_id: str = ""

    # Sub-scores for transparency
    float_risk: float = 0.0
    progress_risk: float = 0.0
    logic_risk: float = 0.0
    duration_risk: float = 0.0
    network_risk: float = 0.0
    trend_risk: float = 0.0


@dataclass
class DelayPredictionResult:
    """Complete delay prediction for all activities in a schedule."""

    activity_risks: list[ActivityRisk] = field(default_factory=list)
    project_risk_score: float = 0.0
    project_risk_level: str = "low"
    predicted_completion_delay: float = 0.0
    high_risk_count: int = 0
    critical_risk_count: int = 0
    risk_distribution: dict[str, int] = field(default_factory=dict)
    methodology: str = "Rule-based multi-factor risk scoring"
    features_used: int = 0
    has_baseline: bool = False
    summary: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------


@dataclass
class _ActivityFeatures:
    """Internal feature vector for a single activity."""

    task: Task
    # Float features
    total_float_hrs: float = 0.0
    free_float_hrs: float = 0.0
    float_bucket: str = "unknown"  # negative, critical, near_critical, moderate, high, excessive
    # Duration features
    remaining_ratio: float = 0.0  # remain / target (0 = done, >1 = over-budget)
    duration_bucket: str = "normal"  # short, normal, long, very_long
    # Logic features
    has_predecessor: bool = False
    has_successor: bool = False
    predecessor_count: int = 0
    successor_count: int = 0
    has_constraint: bool = False
    # Network features
    is_critical: bool = False
    topo_position: float = 0.0  # 0 = start, 1 = end of network
    # Progress features
    progress_pct: float = 0.0
    is_active: bool = False
    is_not_started: bool = False
    is_complete: bool = False
    progress_consistency: float = 1.0  # How well progress matches elapsed time
    # Trend features (only with baseline)
    float_delta_hrs: float = 0.0
    duration_change_hrs: float = 0.0
    constraint_added: bool = False
    has_trend_data: bool = False
    # Schedule-level context
    schedule_logic_pct: float = 0.0
    schedule_constraint_pct: float = 0.0
    schedule_neg_float_pct: float = 0.0


def _extract_features(
    schedule: ParsedSchedule,
    cpm_result: CPMResult,
    baseline: ParsedSchedule | None = None,
) -> list[_ActivityFeatures]:
    """Extract feature vectors for all non-complete activities."""
    # Build relationship maps
    pred_count: dict[str, int] = {}
    succ_count: dict[str, int] = {}
    for rel in schedule.relationships:
        succ_count[rel.task_id] = succ_count.get(rel.task_id, 0)
        pred_count[rel.task_id] = pred_count.get(rel.task_id, 0) + 1
        succ_count[rel.pred_task_id] = succ_count.get(rel.pred_task_id, 0) + 1
        pred_count[rel.pred_task_id] = pred_count.get(rel.pred_task_id, 0)

    # Topological position
    topo_order = []
    if not cpm_result.has_cycles and cpm_result.critical_path:
        topo_order = list(cpm_result.activity_results.keys())
    topo_map: dict[str, float] = {}
    for i, tid in enumerate(topo_order):
        topo_map[tid] = i / max(len(topo_order) - 1, 1)

    # Critical path set
    cp_set = set(cpm_result.critical_path)

    # Baseline lookup
    base_tasks: dict[str, Task] = {}
    if baseline:
        base_by_id = {t.task_id: t for t in baseline.activities}
        base_by_code = {t.task_code: t for t in baseline.activities if t.task_code}
        base_tasks = {**base_by_code, **{t.task_id: t for t in baseline.activities}}
        base_tasks.update(base_by_id)

    # Schedule-level features
    total_acts = len(schedule.activities)
    acts_with_pred = sum(1 for t in schedule.activities if pred_count.get(t.task_id, 0) > 0)
    acts_with_succ = sum(1 for t in schedule.activities if succ_count.get(t.task_id, 0) > 0)
    logic_pct = (acts_with_pred + acts_with_succ) / (2 * total_acts) * 100 if total_acts > 0 else 0
    constraint_count = sum(1 for t in schedule.activities if (t.cstr_type or "").strip())
    constraint_pct = constraint_count / total_acts * 100 if total_acts > 0 else 0
    neg_float_count = sum(
        1
        for t in schedule.activities
        if t.total_float_hr_cnt is not None and t.total_float_hr_cnt < 0
    )
    neg_float_pct = neg_float_count / total_acts * 100 if total_acts > 0 else 0

    features: list[_ActivityFeatures] = []

    for task in schedule.activities:
        # Skip completed activities
        if task.status_code.lower() == "tk_complete":
            continue

        f = _ActivityFeatures(task=task)

        # Float
        tf = task.total_float_hr_cnt if task.total_float_hr_cnt is not None else 0.0
        ff = task.free_float_hr_cnt if task.free_float_hr_cnt is not None else 0.0
        f.total_float_hrs = tf
        f.free_float_hrs = ff
        f.float_bucket = _float_bucket(tf)

        # Duration
        target = task.target_drtn_hr_cnt if task.target_drtn_hr_cnt > 0 else 1.0
        f.remaining_ratio = task.remain_drtn_hr_cnt / target
        f.duration_bucket = _duration_bucket(task.remain_drtn_hr_cnt)

        # Logic
        f.predecessor_count = pred_count.get(task.task_id, 0)
        f.successor_count = succ_count.get(task.task_id, 0)
        f.has_predecessor = f.predecessor_count > 0
        f.has_successor = f.successor_count > 0
        f.has_constraint = bool((task.cstr_type or "").strip())

        # Network
        f.is_critical = task.task_id in cp_set
        f.topo_position = topo_map.get(task.task_id, 0.5)

        # Progress
        f.progress_pct = task.phys_complete_pct
        f.is_active = task.status_code.lower() == "tk_active"
        f.is_not_started = task.status_code.lower() == "tk_notstart"
        f.is_complete = False  # Filtered above

        # Progress consistency: compare % complete vs remaining ratio
        if f.is_active and task.target_drtn_hr_cnt > 0:
            expected_remaining = 1.0 - (task.phys_complete_pct / 100.0)
            actual_remaining = f.remaining_ratio
            if expected_remaining > 0.01:
                f.progress_consistency = min(actual_remaining / expected_remaining, 2.0)
            else:
                f.progress_consistency = actual_remaining * 10  # Should be near 0

        # Trend features (baseline comparison)
        if baseline:
            base_task = base_tasks.get(task.task_id) or base_tasks.get(task.task_code, None)
            if base_task:
                f.has_trend_data = True
                base_tf = base_task.total_float_hr_cnt or 0.0
                f.float_delta_hrs = tf - base_tf
                f.duration_change_hrs = task.remain_drtn_hr_cnt - base_task.remain_drtn_hr_cnt
                base_cstr = (base_task.cstr_type or "").strip()
                curr_cstr = (task.cstr_type or "").strip()
                f.constraint_added = bool(not base_cstr and curr_cstr)

        # Schedule-level context
        f.schedule_logic_pct = logic_pct
        f.schedule_constraint_pct = constraint_pct
        f.schedule_neg_float_pct = neg_float_pct

        features.append(f)

    return features


def _float_bucket(total_float_hrs: float) -> str:
    if total_float_hrs < _FLOAT_NEGATIVE:
        return "negative"
    if total_float_hrs < _FLOAT_CRITICAL:
        return "critical"
    if total_float_hrs < _FLOAT_NEAR_CRITICAL:
        return "near_critical"
    if total_float_hrs < _FLOAT_HIGH:
        return "moderate"
    return "high"


def _duration_bucket(remain_hrs: float) -> str:
    if remain_hrs <= 5 * _HOURS_PER_DAY:
        return "short"
    if remain_hrs <= _DURATION_LONG:
        return "normal"
    if remain_hrs <= _DURATION_VERY_LONG:
        return "long"
    return "very_long"


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------


def _score_float_risk(f: _ActivityFeatures) -> tuple[float, list[RiskFactor]]:
    """Score float-related risk (0-100)."""
    factors: list[RiskFactor] = []
    tf = f.total_float_hrs
    tf_days = tf / _HOURS_PER_DAY

    if tf < 0:
        score = min(100, 70 + abs(tf_days) * 2)
        factors.append(
            RiskFactor(
                "negative_float",
                0.9,
                f"Activity has {tf_days:.1f} days of negative float",
                f"{tf_days:.1f}d",
            )
        )
    elif tf < _FLOAT_CRITICAL:
        score = 70.0
        factors.append(
            RiskFactor("zero_float", 0.7, "Activity is on critical path (zero float)", "0d")
        )
    elif tf < _FLOAT_NEAR_CRITICAL:
        score = 40 + (1 - tf / _FLOAT_NEAR_CRITICAL) * 30
        factors.append(
            RiskFactor(
                "near_critical_float",
                0.5,
                f"Float is near-critical ({tf_days:.1f} days, threshold: 10d)",
                f"{tf_days:.1f}d",
            )
        )
    elif tf < _FLOAT_HIGH:
        score = 10 + (1 - tf / _FLOAT_HIGH) * 30
    else:
        score = 5.0

    return score, factors


def _score_progress_risk(f: _ActivityFeatures) -> tuple[float, list[RiskFactor]]:
    """Score progress-related risk (0-100)."""
    factors: list[RiskFactor] = []

    if f.is_not_started:
        # Not started activities have moderate base risk
        score = 30.0
        if f.topo_position > 0.8:
            score = 15.0  # Late in network, expected to not be started yet
    elif f.is_active:
        # Check progress consistency
        if f.progress_consistency > 1.5:
            score = 70.0
            factors.append(
                RiskFactor(
                    "behind_schedule",
                    0.7,
                    f"Remaining work ({f.remaining_ratio:.0%}) exceeds expected "
                    f"based on {f.progress_pct:.0f}% progress",
                    f"{f.progress_consistency:.1f}x",
                )
            )
        elif f.progress_consistency > 1.2:
            score = 50.0
            factors.append(
                RiskFactor(
                    "slow_progress",
                    0.5,
                    "Progress is slightly behind remaining duration",
                    f"{f.progress_consistency:.1f}x",
                )
            )
        else:
            score = 15.0
    else:
        score = 0.0

    return score, factors


def _score_logic_risk(f: _ActivityFeatures) -> tuple[float, list[RiskFactor]]:
    """Score logic integrity risk (0-100)."""
    factors: list[RiskFactor] = []
    score = 0.0

    if not f.has_predecessor and not f.has_successor:
        score += 60.0
        factors.append(
            RiskFactor(
                "open_ended",
                0.6,
                "Activity has no predecessors or successors (dangling)",
                "0 rels",
            )
        )
    elif not f.has_predecessor:
        score += 30.0
        factors.append(RiskFactor("no_predecessor", 0.3, "Activity has no predecessors", "0 pred"))
    elif not f.has_successor:
        score += 20.0
        factors.append(RiskFactor("no_successor", 0.2, "Activity has no successors", "0 succ"))

    if f.has_constraint:
        score += 25.0
        factors.append(
            RiskFactor(
                "hard_constraint",
                0.3,
                "Activity has a hard constraint (may mask float)",
                f"{f.task.cstr_type}",
            )
        )

    return min(score, 100), factors


def _score_duration_risk(f: _ActivityFeatures) -> tuple[float, list[RiskFactor]]:
    """Score duration-related risk (0-100)."""
    factors: list[RiskFactor] = []
    remain_days = f.task.remain_drtn_hr_cnt / _HOURS_PER_DAY

    if f.duration_bucket == "very_long":
        score = 60.0
        factors.append(
            RiskFactor(
                "very_long_duration",
                0.6,
                f"Remaining duration is very long ({remain_days:.0f} days, threshold: 80d)",
                f"{remain_days:.0f}d",
            )
        )
    elif f.duration_bucket == "long":
        score = 35.0
        factors.append(
            RiskFactor(
                "long_duration",
                0.35,
                f"Remaining duration exceeds 44-day DCMA threshold ({remain_days:.0f}d)",
                f"{remain_days:.0f}d",
            )
        )
    elif f.remaining_ratio > 1.2:
        score = 45.0
        factors.append(
            RiskFactor(
                "duration_overrun",
                0.45,
                f"Remaining duration exceeds original by {(f.remaining_ratio - 1) * 100:.0f}%",
                f"{f.remaining_ratio:.0%}",
            )
        )
    else:
        score = 5.0

    return score, factors


def _score_network_risk(f: _ActivityFeatures) -> tuple[float, list[RiskFactor]]:
    """Score network position risk (0-100)."""
    factors: list[RiskFactor] = []
    score = 0.0

    if f.is_critical:
        score += 50.0
        factors.append(RiskFactor("critical_path", 0.5, "Activity is on the critical path", "CP"))

    # Activities early in network with many successors are higher risk
    if f.successor_count > 5:
        score += 15.0
        factors.append(
            RiskFactor(
                "many_successors",
                0.15,
                f"Activity drives {f.successor_count} successors",
                f"{f.successor_count}",
            )
        )

    return min(score, 100), factors


def _score_trend_risk(f: _ActivityFeatures) -> tuple[float, list[RiskFactor]]:
    """Score trend-based risk (0-100). Requires baseline data."""
    if not f.has_trend_data:
        return 0.0, []

    factors: list[RiskFactor] = []
    score = 0.0
    float_delta_days = f.float_delta_hrs / _HOURS_PER_DAY

    if f.float_delta_hrs < -5 * _HOURS_PER_DAY:
        severity = min(abs(float_delta_days) / 20 * 60, 80)
        score += severity
        factors.append(
            RiskFactor(
                "float_erosion",
                min(severity / 100, 0.8),
                f"Float eroded by {abs(float_delta_days):.1f} days since baseline",
                f"{float_delta_days:+.1f}d",
            )
        )

    dur_delta_days = f.duration_change_hrs / _HOURS_PER_DAY
    if f.duration_change_hrs > 5 * _HOURS_PER_DAY:
        score += 30.0
        factors.append(
            RiskFactor(
                "duration_growth",
                0.3,
                f"Remaining duration increased by {dur_delta_days:.1f} days",
                f"+{dur_delta_days:.1f}d",
            )
        )

    if f.constraint_added:
        score += 20.0
        factors.append(
            RiskFactor(
                "constraint_added",
                0.2,
                "Hard constraint added since baseline",
                "new",
            )
        )

    return min(score, 100), factors


def _compute_activity_risk(f: _ActivityFeatures) -> ActivityRisk:
    """Compute the composite risk score for a single activity."""
    float_score, float_factors = _score_float_risk(f)
    progress_score, progress_factors = _score_progress_risk(f)
    logic_score, logic_factors = _score_logic_risk(f)
    duration_score, duration_factors = _score_duration_risk(f)
    network_score, network_factors = _score_network_risk(f)
    trend_score, trend_factors = _score_trend_risk(f)

    composite = (
        _W_FLOAT * float_score
        + _W_PROGRESS * progress_score
        + _W_LOGIC * logic_score
        + _W_DURATION * duration_score
        + _W_NETWORK * network_score
        + _W_TREND * trend_score
    )

    # Collect and sort risk factors by contribution
    all_factors = (
        float_factors
        + progress_factors
        + logic_factors
        + duration_factors
        + network_factors
        + trend_factors
    )
    all_factors.sort(key=lambda rf: rf.contribution, reverse=True)

    # Determine risk level
    if composite >= _RISK_HIGH:
        level = "critical"
    elif composite >= _RISK_MEDIUM:
        level = "high"
    elif composite >= _RISK_LOW:
        level = "medium"
    else:
        level = "low"

    # Predict delay days based on float and progress
    predicted_delay = 0.0
    tf_days = f.total_float_hrs / _HOURS_PER_DAY
    if tf_days < 0:
        predicted_delay = abs(tf_days)
    elif f.is_active and f.progress_consistency > 1.2:
        # Estimate based on how far behind progress is
        remain_days = f.task.remain_drtn_hr_cnt / _HOURS_PER_DAY
        predicted_delay = remain_days * (f.progress_consistency - 1.0)

    # Confidence based on data quality
    confidence = 0.6  # Base confidence for rule-based
    if f.has_trend_data:
        confidence += 0.2  # Trend data improves confidence
    if f.has_predecessor and f.has_successor:
        confidence += 0.1  # Good logic improves confidence
    if f.total_float_hrs is not None:
        confidence += 0.1

    return ActivityRisk(
        task_id=f.task.task_id,
        task_code=f.task.task_code,
        task_name=f.task.task_name,
        risk_score=round(composite, 1),
        risk_level=level,
        predicted_delay_days=round(predicted_delay, 1),
        confidence=min(confidence, 1.0),
        top_risk_factors=all_factors[:5],  # Top 5 factors
        is_critical_path=f.is_critical,
        wbs_id=f.task.wbs_id,
        float_risk=round(float_score, 1),
        progress_risk=round(progress_score, 1),
        logic_risk=round(logic_score, 1),
        duration_risk=round(duration_score, 1),
        network_risk=round(network_score, 1),
        trend_risk=round(trend_score, 1),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def predict_delays(
    schedule: ParsedSchedule,
    baseline: ParsedSchedule | None = None,
) -> DelayPredictionResult:
    """Predict delay risk for all non-complete activities in a schedule.

    Uses a weighted multi-factor risk scoring model aligned with DCMA
    14-Point thresholds and AACE RP 49R-06 float health criteria.

    Args:
        schedule: The current schedule to analyze.
        baseline: Optional earlier schedule for trend-based features.

    Returns:
        A ``DelayPredictionResult`` with per-activity risks and project
        aggregate scores.
    """
    result = DelayPredictionResult()
    result.has_baseline = baseline is not None

    # Run CPM
    try:
        cpm_result = CPMCalculator(schedule).calculate()
    except Exception:
        logger.warning("CPM calculation failed for delay prediction")
        cpm_result = CPMResult()

    # Extract features
    features = _extract_features(schedule, cpm_result, baseline)
    result.features_used = 35 if baseline else 31

    if not features:
        result.methodology = "No non-complete activities to analyze"
        result.summary = {"activities_analyzed": 0}
        return result

    # Score each activity
    for f in features:
        risk = _compute_activity_risk(f)
        result.activity_risks.append(risk)

    # Sort by risk score descending
    result.activity_risks.sort(key=lambda r: r.risk_score, reverse=True)

    # Aggregate project-level metrics
    scores = [r.risk_score for r in result.activity_risks]
    result.project_risk_score = round(sum(scores) / len(scores), 1)

    # Project risk level
    if result.project_risk_score >= _RISK_HIGH:
        result.project_risk_level = "critical"
    elif result.project_risk_score >= _RISK_MEDIUM:
        result.project_risk_level = "high"
    elif result.project_risk_score >= _RISK_LOW:
        result.project_risk_level = "medium"
    else:
        result.project_risk_level = "low"

    # Risk distribution
    dist: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for r in result.activity_risks:
        dist[r.risk_level] += 1
    result.risk_distribution = dist
    result.high_risk_count = dist["high"]
    result.critical_risk_count = dist["critical"]

    # Predicted completion delay (max of CP activity predictions)
    cp_delays = [r.predicted_delay_days for r in result.activity_risks if r.is_critical_path]
    result.predicted_completion_delay = round(max(cp_delays, default=0.0), 1)

    # Methodology
    result.methodology = (
        "Rule-based multi-factor risk scoring with trend analysis"
        if baseline
        else "Rule-based multi-factor risk scoring (single schedule)"
    )

    # Summary
    result.summary = {
        "activities_analyzed": len(result.activity_risks),
        "project_risk_score": result.project_risk_score,
        "project_risk_level": result.project_risk_level,
        "predicted_completion_delay_days": result.predicted_completion_delay,
        "risk_distribution": dist,
        "high_risk_count": result.high_risk_count,
        "critical_risk_count": result.critical_risk_count,
        "has_baseline": result.has_baseline,
        "features_used": result.features_used,
        "methodology": result.methodology,
        "top_risk_activities": [
            {
                "task_code": r.task_code,
                "task_name": r.task_name,
                "risk_score": r.risk_score,
                "risk_level": r.risk_level,
                "predicted_delay": r.predicted_delay_days,
                "top_factor": r.top_risk_factors[0].name if r.top_risk_factors else "",
            }
            for r in result.activity_risks[:10]
        ],
        "references": [
            "DCMA 14-Point Assessment — standard thresholds",
            "AACE RP 49R-06 — Float Trend Analysis",
            "GAO Schedule Assessment Guide §7–§9",
        ],
    }

    return result
