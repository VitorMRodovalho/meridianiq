# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Composite Schedule Health Score per DCMA + GAO.

Produces a single 0–100 score answering "how healthy is this schedule?"
by combining structural quality (DCMA 14-point), float distribution,
logic integrity, and trend direction.

Formula:
    Health = 0.40 * DCMA_Score + 0.25 * Float_Health
           + 0.20 * Logic_Integrity + 0.15 * Trend_Direction

Standards:
    - DCMA 14-Point Assessment — structural quality
    - AACE RP 49R-06 — Float distribution and consumption
    - DCMA checks #6, #7 — Logic completeness
    - GAO Schedule Assessment Guide §9 — Trend surveillance
    - GAO 4 Characteristics: Comprehensive, Well-constructed, Credible, Controlled
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.analytics.dcma14 import DCMA14Analyzer, DCMA14Result
from src.analytics.float_trends import FloatTrendAnalyzer, FloatTrendResult
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)

_HOURS_PER_DAY = 8.0

# Rating thresholds aligned with GAO 4 characteristics
_RATING_THRESHOLDS = {
    "excellent": 85.0,  # Comprehensive + Well-constructed + Credible + Controlled
    "good": 70.0,       # Minor gaps in 1 characteristic
    "fair": 50.0,       # Significant gaps in 2+ characteristics
}


@dataclass
class HealthScore:
    """Composite schedule health score result.

    Attributes:
        overall: Composite health score (0–100).
        dcma_component: Weighted DCMA contribution (0–40).
        float_component: Weighted float health contribution (0–25).
        logic_component: Weighted logic integrity contribution (0–20).
        trend_component: Weighted trend direction contribution (0–15).
        dcma_raw: Raw DCMA score before weighting (0–100).
        float_raw: Raw float health score before weighting (0–100).
        logic_raw: Raw logic integrity score before weighting (0–100).
        trend_raw: Raw trend direction score before weighting (0–100).
        rating: 'excellent', 'good', 'fair', or 'poor'.
        trend_arrow: Direction indicator arrow.
        details: Breakdown details for transparency.
    """

    overall: float = 0.0
    dcma_component: float = 0.0
    float_component: float = 0.0
    logic_component: float = 0.0
    trend_component: float = 0.0
    dcma_raw: float = 0.0
    float_raw: float = 0.0
    logic_raw: float = 0.0
    trend_raw: float = 0.0
    rating: str = "poor"
    trend_arrow: str = "→"
    details: dict[str, Any] = field(default_factory=dict)


class HealthScoreCalculator:
    """Calculate the composite schedule health score.

    Can operate in two modes:
    1. **Single schedule:** DCMA + float + logic only (trend = 50, neutral).
    2. **Two schedules:** Full analysis including trend direction.

    Usage (single schedule)::

        calc = HealthScoreCalculator(schedule)
        score = calc.calculate()
        print(f"Health: {score.overall:.0f} — {score.rating}")

    Usage (with trend)::

        calc = HealthScoreCalculator(update, baseline=baseline)
        score = calc.calculate()
        print(f"Health: {score.overall:.0f} {score.trend_arrow}")

    Args:
        schedule: The current schedule to assess.
        baseline: Optional baseline schedule for trend calculation.
        hours_per_day: Hours per working day for conversions.
    """

    # Component weights
    W_DCMA = 0.40
    W_FLOAT = 0.25
    W_LOGIC = 0.20
    W_TREND = 0.15

    def __init__(
        self,
        schedule: ParsedSchedule,
        baseline: ParsedSchedule | None = None,
        hours_per_day: float = _HOURS_PER_DAY,
    ) -> None:
        self.schedule = schedule
        self.baseline = baseline
        self.hours_per_day = hours_per_day

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(self) -> HealthScore:
        """Compute the composite health score.

        Returns:
            A ``HealthScore`` with overall score and component breakdown.
        """
        result = HealthScore()

        # Component 1: DCMA Score (0–100)
        dcma_raw = self._compute_dcma_score()
        result.dcma_raw = dcma_raw
        result.dcma_component = round(dcma_raw * self.W_DCMA, 2)

        # Component 2: Float Health (0–100)
        float_raw = self._compute_float_health()
        result.float_raw = float_raw
        result.float_component = round(float_raw * self.W_FLOAT, 2)

        # Component 3: Logic Integrity (0–100)
        logic_raw = self._compute_logic_integrity()
        result.logic_raw = logic_raw
        result.logic_component = round(logic_raw * self.W_LOGIC, 2)

        # Component 4: Trend Direction (0–100)
        trend_raw = self._compute_trend_direction()
        result.trend_raw = trend_raw
        result.trend_component = round(trend_raw * self.W_TREND, 2)

        # Composite score
        result.overall = round(
            result.dcma_component
            + result.float_component
            + result.logic_component
            + result.trend_component,
            1,
        )

        # Clamp to 0–100
        result.overall = max(0.0, min(100.0, result.overall))

        # Rating
        result.rating = self._classify_rating(result.overall)

        # Trend arrow
        result.trend_arrow = self._classify_trend_arrow(trend_raw)

        # Details for transparency
        result.details = {
            "weights": {
                "dcma": self.W_DCMA,
                "float": self.W_FLOAT,
                "logic": self.W_LOGIC,
                "trend": self.W_TREND,
            },
            "raw_scores": {
                "dcma": dcma_raw,
                "float_health": float_raw,
                "logic_integrity": logic_raw,
                "trend_direction": trend_raw,
            },
            "has_baseline": self.baseline is not None,
        }

        return result

    # ------------------------------------------------------------------
    # Component 1: DCMA Score
    # ------------------------------------------------------------------

    def _compute_dcma_score(self) -> float:
        """Run the existing DCMA 14-point assessment and return 0–100 score.

        The DCMA analyzer produces an ``overall_score`` that represents
        (passed_count / 14) * 100.

        Returns:
            DCMA composite score (0–100).
        """
        try:
            analyzer = DCMA14Analyzer(
                self.schedule, hours_per_day=self.hours_per_day
            )
            dcma_result = analyzer.analyze()
            return dcma_result.overall_score
        except Exception:
            logger.warning("DCMA analysis failed in health score calculation")
            return 50.0  # neutral on failure

    # ------------------------------------------------------------------
    # Component 2: Float Health
    # ------------------------------------------------------------------

    def _compute_float_health(self) -> float:
        """Compute float health sub-score.

        Formula: Float_Health = 100 - (neg_float_% * 2 + high_float_% * 0.5)

        Where:
            neg_float_% = % of incomplete activities with TF < 0
            high_float_% = % of incomplete activities with TF > 44 days

        Per AACE RP 49R-06 and DCMA checks #4/#6.

        Returns:
            Float health score (0–100).
        """
        incomplete = [
            t for t in self.schedule.activities
            if t.status_code.lower() != "tk_complete"
            and t.task_type.lower() not in ("tt_loe", "tt_wbs")
        ]

        if not incomplete:
            return 100.0

        high_float_hours = 44.0 * self.hours_per_day
        neg_count = 0
        high_count = 0

        for t in incomplete:
            if t.total_float_hr_cnt is None:
                continue
            if t.total_float_hr_cnt < 0:
                neg_count += 1
            if t.total_float_hr_cnt > high_float_hours:
                high_count += 1

        total = len(incomplete)
        neg_pct = (neg_count / total) * 100
        high_pct = (high_count / total) * 100

        score = 100.0 - (neg_pct * 2 + high_pct * 0.5)
        return max(0.0, min(100.0, round(score, 2)))

    # ------------------------------------------------------------------
    # Component 3: Logic Integrity
    # ------------------------------------------------------------------

    def _compute_logic_integrity(self) -> float:
        """Compute logic integrity sub-score.

        Formula: Logic_Integrity = 100 * (1 - open_ended_% - missing_logic_%)

        Where:
            open_ended_% = % of activities missing BOTH pred and succ
            missing_logic_% = % of activities missing EITHER pred or succ
                              (but having the other)

        Per DCMA checks #6 (missing successors) and #7 (missing predecessors).

        Returns:
            Logic integrity score (0–100).
        """
        all_countable = [
            t for t in self.schedule.activities
            if t.task_type.lower() not in ("tt_loe", "tt_wbs")
        ]

        if not all_countable:
            return 100.0

        # Build predecessor/successor lookup
        has_pred: set[str] = set()
        has_succ: set[str] = set()
        for rel in self.schedule.relationships:
            has_pred.add(rel.task_id)
            has_succ.add(rel.pred_task_id)

        open_ended = 0  # missing both
        missing_one = 0  # missing either pred or succ

        for t in all_countable:
            mp = t.task_id not in has_pred
            ms = t.task_id not in has_succ
            if mp and ms:
                open_ended += 1
            elif mp or ms:
                missing_one += 1

        total = len(all_countable)
        open_pct = (open_ended / total) * 100
        missing_pct = (missing_one / total) * 100

        score = 100.0 * (1 - (open_pct + missing_pct) / 100)
        return max(0.0, min(100.0, round(score, 2)))

    # ------------------------------------------------------------------
    # Component 4: Trend Direction
    # ------------------------------------------------------------------

    def _compute_trend_direction(self) -> float:
        """Compute trend direction sub-score using float trend analysis.

        Score mapping:
            0   = declining (more activities deteriorating than improving)
            50  = stable (no baseline available, or balanced changes)
            100 = improving (more activities improving than deteriorating)

        Per GAO Schedule Assessment Guide §9.

        Returns:
            Trend direction score (0–100).
        """
        if self.baseline is None:
            return 50.0  # neutral when no baseline available

        try:
            ft_analyzer = FloatTrendAnalyzer(
                self.baseline, self.schedule, hours_per_day=self.hours_per_day
            )
            ft_result = ft_analyzer.analyze()
        except Exception:
            logger.warning("Float trend analysis failed in health score calculation")
            return 50.0

        improving = sum(
            1 for t in ft_result.activity_trends if t.direction == "improving"
        )
        deteriorating = sum(
            1 for t in ft_result.activity_trends if t.direction == "deteriorating"
        )
        total = improving + deteriorating

        if total == 0:
            return 50.0

        # Net ratio: 1.0 = all improving, 0.0 = all deteriorating
        net_ratio = improving / total
        score = net_ratio * 100

        return max(0.0, min(100.0, round(score, 2)))

    # ------------------------------------------------------------------
    # Rating classification
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_rating(overall: float) -> str:
        """Classify the overall score into a rating label.

        Thresholds aligned with GAO 4 characteristics:
            85–100: excellent
            70–84:  good
            50–69:  fair
            < 50:   poor
        """
        if overall >= _RATING_THRESHOLDS["excellent"]:
            return "excellent"
        elif overall >= _RATING_THRESHOLDS["good"]:
            return "good"
        elif overall >= _RATING_THRESHOLDS["fair"]:
            return "fair"
        else:
            return "poor"

    @staticmethod
    def _classify_trend_arrow(trend_raw: float) -> str:
        """Classify trend direction into an arrow indicator.

        Returns:
            Arrow string based on trend score.
        """
        if trend_raw > 60:
            return "↑"
        elif trend_raw < 40:
            return "↓"
        else:
            return "→"
