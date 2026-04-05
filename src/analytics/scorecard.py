# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Schedule scorecard — single-page aggregate assessment.

Combines outputs from DCMA 14-Point, Health Score, Delay Prediction, and
Benchmark Comparison into a unified letter-grade scorecard with actionable
recommendations.

The scorecard provides a quick "executive summary" of schedule quality
across five dimensions, each scored 0-100 and graded A-F.

References:
    - DCMA 14-Point Assessment — schedule validation standard
    - GAO Schedule Assessment Guide — 4 characteristics of a reliable schedule
    - AACE RP 49R-06 — Schedule Health Assessment
    - AACE RP 57R-09 — Schedule Risk Analysis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.dcma14 import DCMA14Analyzer
from src.analytics.delay_prediction import predict_delays
from src.analytics.health_score import HealthScoreCalculator
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

_GRADE_THRESHOLDS = [(90, "A"), (80, "B"), (70, "C"), (60, "D")]


def _score_to_grade(score: float) -> str:
    """Convert a 0-100 score to a letter grade."""
    for threshold, grade in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


@dataclass
class ScorecardDimension:
    """A single dimension of the scorecard."""

    name: str
    score: float  # 0-100
    grade: str  # A-F
    description: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScorecardResult:
    """Complete schedule scorecard."""

    overall_score: float = 0.0
    overall_grade: str = "F"
    dimensions: list[ScorecardDimension] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    methodology: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------


def _score_validation(schedule: ParsedSchedule) -> ScorecardDimension:
    """DCMA 14-Point validation dimension."""
    try:
        analyzer = DCMA14Analyzer(schedule)
        dcma = analyzer.analyze()
        score = dcma.overall_score
    except Exception:
        logger.warning("DCMA analysis failed for scorecard")
        score = 0.0

    return ScorecardDimension(
        name="Validation",
        score=round(score, 1),
        grade=_score_to_grade(score),
        description="DCMA 14-Point schedule quality assessment",
        details={"standard": "DCMA 14-Point Assessment"},
    )


def _score_health(schedule: ParsedSchedule) -> ScorecardDimension:
    """Composite health score dimension."""
    try:
        calc = HealthScoreCalculator(schedule)
        health = calc.calculate()
        score = health.overall
    except Exception:
        logger.warning("Health score failed for scorecard")
        score = 0.0

    return ScorecardDimension(
        name="Health",
        score=round(score, 1),
        grade=_score_to_grade(score),
        description="Composite schedule health (float, logic, trends)",
        details={"standard": "AACE RP 49R-06"},
    )


def _score_risk(schedule: ParsedSchedule) -> ScorecardDimension:
    """Delay risk dimension (inverted — low risk = high score)."""
    try:
        result = predict_delays(schedule)
        # Invert: 0 risk → 100 score, 100 risk → 0 score
        score = max(0.0, 100.0 - result.project_risk_score)
    except Exception:
        logger.warning("Delay prediction failed for scorecard")
        score = 50.0  # Unknown risk defaults to middle

    return ScorecardDimension(
        name="Risk",
        score=round(score, 1),
        grade=_score_to_grade(score),
        description="Delay risk assessment (lower risk = higher score)",
        details={"standard": "Gondia et al. (2021), AACE RP 57R-09"},
    )


def _score_logic(schedule: ParsedSchedule) -> ScorecardDimension:
    """Logic integrity dimension."""
    total = len(schedule.activities)
    if total == 0:
        return ScorecardDimension(name="Logic", score=0.0, grade="F", description="No activities")

    # Count logic completeness
    pred_set: set[str] = set()
    succ_set: set[str] = set()
    for rel in schedule.relationships:
        pred_set.add(rel.task_id)
        succ_set.add(rel.pred_task_id)

    both = pred_set & succ_set
    logic_pct = len(both) / total * 100 if total > 0 else 0

    # Constraint count
    constrained = sum(1 for t in schedule.activities if (t.cstr_type or "").strip())
    constraint_pct = constrained / total * 100 if total > 0 else 0

    # Score: logic% is good, constraints% is bad
    score = min(100.0, logic_pct - constraint_pct * 0.5)
    score = max(0.0, score)

    return ScorecardDimension(
        name="Logic",
        score=round(score, 1),
        grade=_score_to_grade(score),
        description="Network logic completeness and constraint usage",
        details={
            "logic_pct": round(logic_pct, 1),
            "constraint_pct": round(constraint_pct, 1),
            "standard": "DCMA checks #1-#2, GAO Schedule Guide",
        },
    )


def _score_completeness(schedule: ParsedSchedule) -> ScorecardDimension:
    """Data completeness dimension — checks for missing fields."""
    total = len(schedule.activities)
    if total == 0:
        return ScorecardDimension(
            name="Completeness", score=0.0, grade="F", description="No activities"
        )

    checks = 0
    passed = 0

    for task in schedule.activities:
        # Has calendar
        checks += 1
        if task.clndr_id:
            passed += 1
        # Has duration
        checks += 1
        if task.target_drtn_hr_cnt > 0 or task.status_code.lower() == "tk_complete":
            passed += 1
        # Has dates
        checks += 1
        if task.early_start_date or task.act_start_date:
            passed += 1
        # Has WBS
        checks += 1
        if task.wbs_id:
            passed += 1

    score = (passed / checks * 100) if checks > 0 else 0

    return ScorecardDimension(
        name="Completeness",
        score=round(score, 1),
        grade=_score_to_grade(score),
        description="Data completeness (calendars, durations, dates, WBS)",
        details={"checks": checks, "passed": passed},
    )


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

_RECOMMENDATIONS: list[tuple[str, str, float]] = [
    ("Validation", "Run DCMA 14-Point remediation — focus on failed checks", 70),
    ("Health", "Address float concentration and logic gaps per AACE RP 49R-06", 70),
    ("Risk", "Review high-risk activities — negative float and dangling logic", 70),
    ("Logic", "Add missing predecessors/successors — target >95% logic density", 80),
    ("Completeness", "Fill missing WBS assignments, calendars, and target dates", 90),
]


def _generate_recommendations(dimensions: list[ScorecardDimension]) -> list[str]:
    """Generate recommendations based on dimension scores."""
    recs: list[str] = []
    dim_map = {d.name: d for d in dimensions}

    for dim_name, rec_text, threshold in _RECOMMENDATIONS:
        dim = dim_map.get(dim_name)
        if dim and dim.score < threshold:
            recs.append(f"[{dim.grade}] {dim.name}: {rec_text}")

    if not recs:
        recs.append("Schedule meets all quality thresholds — maintain current standards")

    return recs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_scorecard(
    schedule: ParsedSchedule,
) -> ScorecardResult:
    """Calculate a comprehensive schedule scorecard.

    Aggregates five quality dimensions into a single letter-graded
    assessment with actionable recommendations.

    Args:
        schedule: The schedule to assess.

    Returns:
        A ``ScorecardResult`` with overall grade, dimension scores,
        and recommendations.

    References:
        - DCMA 14-Point Assessment
        - GAO Schedule Assessment Guide (4 characteristics)
        - AACE RP 49R-06 — Schedule Health
        - AACE RP 57R-09 — Schedule Risk
    """
    result = ScorecardResult()

    # Calculate each dimension
    dimensions = [
        _score_validation(schedule),
        _score_health(schedule),
        _score_risk(schedule),
        _score_logic(schedule),
        _score_completeness(schedule),
    ]
    result.dimensions = dimensions

    # Overall score (weighted average)
    weights = {
        "Validation": 0.30,
        "Health": 0.25,
        "Risk": 0.20,
        "Logic": 0.15,
        "Completeness": 0.10,
    }
    weighted_sum = sum(d.score * weights.get(d.name, 0.2) for d in dimensions)
    result.overall_score = round(weighted_sum, 1)
    result.overall_grade = _score_to_grade(result.overall_score)

    # Recommendations
    result.recommendations = _generate_recommendations(dimensions)

    # Methodology
    result.methodology = (
        "Weighted multi-dimension scorecard: Validation (30%), Health (25%), "
        "Risk (20%), Logic (15%), Completeness (10%)"
    )

    # Summary
    result.summary = {
        "overall_score": result.overall_score,
        "overall_grade": result.overall_grade,
        "dimensions": {d.name: {"score": d.score, "grade": d.grade} for d in dimensions},
        "recommendations_count": len(result.recommendations),
        "methodology": result.methodology,
        "references": [
            "DCMA 14-Point Assessment",
            "GAO Schedule Assessment Guide",
            "AACE RP 49R-06 — Schedule Health",
            "AACE RP 57R-09 — Schedule Risk",
        ],
    }

    return result
