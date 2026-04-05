# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""ML duration prediction — benchmark-trained project duration forecasting.

Trains a Random Forest + Gradient Boosting ensemble on the benchmark
database to predict project duration based on schedule characteristics.
Unlike the delay prediction engine (which scores per-activity risk), this
engine predicts the expected overall project duration in days based on
structural features visible at planning time.

References:
    - AbdElMottaleb (2025) — ML for Construction Scheduling (R²=0.91)
    - Gondia et al. (2021) — Applied AI for Construction Delay Prediction
    - Breiman (2001) — Random Forests
    - Friedman (2001) — Gradient Boosting Machines
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from src.analytics.benchmarks import BenchmarkMetrics, extract_benchmark_metrics
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.model_selection import cross_val_score

    _HAS_SKLEARN = True
except ImportError:  # pragma: no cover
    _HAS_SKLEARN = False


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

_FEATURE_NAMES = [
    "activity_count",
    "relationship_count",
    "wbs_depth",
    "milestone_count",
    "dcma_score",
    "logic_pct",
    "constraint_pct",
    "high_float_pct",
    "negative_float_pct",
    "high_duration_pct",
    "relationship_fs_pct",
    "lead_pct",
    "lag_pct",
    "bei",
    "cpli",
    "float_mean_days",
    "float_median_days",
    "float_stdev_days",
    "relationship_density",
    "critical_path_length",
    "cp_percentage",
    "complete_pct",
    "active_pct",
    "not_started_pct",
    # One-hot size category
    "is_small",
    "is_medium",
    "is_large",
    "is_mega",
]


def _metrics_to_vector(m: BenchmarkMetrics) -> np.ndarray:
    """Convert BenchmarkMetrics to a feature vector."""
    return np.array(
        [
            m.activity_count,
            m.relationship_count,
            m.wbs_depth,
            m.milestone_count,
            m.dcma_score,
            m.logic_pct,
            m.constraint_pct,
            m.high_float_pct,
            m.negative_float_pct,
            m.high_duration_pct,
            m.relationship_fs_pct,
            m.lead_pct,
            m.lag_pct,
            m.bei,
            m.cpli,
            m.float_mean_days,
            m.float_median_days,
            m.float_stdev_days,
            m.relationship_density,
            m.critical_path_length,
            m.cp_percentage,
            m.complete_pct,
            m.active_pct,
            m.not_started_pct,
            1.0 if m.size_category == "small" else 0.0,
            1.0 if m.size_category == "medium" else 0.0,
            1.0 if m.size_category == "large" else 0.0,
            1.0 if m.size_category == "mega" else 0.0,
        ],
        dtype=np.float64,
    )


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


@dataclass
class DurationPrediction:
    """Result of ML duration prediction."""

    predicted_duration_days: float = 0.0
    confidence_low: float = 0.0  # Lower bound (e.g., P20)
    confidence_high: float = 0.0  # Upper bound (e.g., P80)
    actual_duration_days: float = 0.0  # From CPM if available
    delta_days: float = 0.0  # predicted - actual
    model_r_squared: float = 0.0
    training_samples: int = 0
    feature_importances: dict[str, float] = field(default_factory=dict)
    methodology: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ML model
# ---------------------------------------------------------------------------


class DurationPredictor:
    """Ensemble model for project duration prediction.

    Trained on benchmark database metrics to predict project_duration_days.

    References:
        - AbdElMottaleb (2025) — ML for Construction Scheduling
        - Breiman (2001) — Random Forests
        - Friedman (2001) — Gradient Boosting Machines
    """

    def __init__(self) -> None:
        if not _HAS_SKLEARN:
            raise RuntimeError(
                "scikit-learn required for duration prediction. "
                "Install with: pip install meridianiq[ml]"
            )
        self._rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=8,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=-1,
        )
        self._gb = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            min_samples_leaf=3,
            random_state=42,
        )
        self._is_trained = False
        self._r_squared = 0.0
        self._training_samples = 0

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    def train(self, benchmarks: list[BenchmarkMetrics]) -> dict[str, Any]:
        """Train on benchmark dataset.

        Args:
            benchmarks: List of benchmark metrics with project_duration_days > 0.

        Returns:
            Training summary with R², sample count, feature importances.
        """
        # Filter valid training samples
        valid = [b for b in benchmarks if b.project_duration_days > 0]
        if len(valid) < 10:
            raise ValueError(f"Need at least 10 benchmarks with duration, got {len(valid)}")

        X = np.array([_metrics_to_vector(b) for b in valid])
        y = np.array([b.project_duration_days for b in valid])

        # Handle NaN/inf
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        self._rf.fit(X, y)
        self._gb.fit(X, y)
        self._is_trained = True
        self._training_samples = len(valid)

        # Cross-validation R²
        if len(valid) >= 20:
            cv_scores = cross_val_score(self._rf, X, y, cv=5, scoring="r2")
            self._r_squared = round(float(np.mean(cv_scores)), 3)
        else:
            # Not enough for 5-fold CV, use training R²
            self._r_squared = round(float(self._rf.score(X, y)), 3)

        # Feature importances
        rf_imp = self._rf.feature_importances_
        gb_imp = self._gb.feature_importances_
        avg_imp = (rf_imp + gb_imp) / 2.0
        importances = {
            _FEATURE_NAMES[i]: round(float(avg_imp[i]), 4) for i in range(len(_FEATURE_NAMES))
        }
        importances = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))

        return {
            "samples": len(valid),
            "features": len(_FEATURE_NAMES),
            "r_squared": self._r_squared,
            "feature_importances": importances,
        }

    def predict(self, metrics: BenchmarkMetrics) -> float:
        """Predict duration in days for a single project."""
        if not self._is_trained:
            raise RuntimeError("Model not trained")
        vec = _metrics_to_vector(metrics).reshape(1, -1)
        vec = np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)
        rf_pred = float(self._rf.predict(vec)[0])
        gb_pred = float(self._gb.predict(vec)[0])
        return max(0.0, 0.5 * rf_pred + 0.5 * gb_pred)

    def predict_with_confidence(self, metrics: BenchmarkMetrics) -> tuple[float, float, float]:
        """Predict duration with confidence interval from RF tree variance."""
        if not self._is_trained:
            raise RuntimeError("Model not trained")
        vec = _metrics_to_vector(metrics).reshape(1, -1)
        vec = np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)

        # Get predictions from all RF trees
        tree_preds = np.array([tree.predict(vec)[0] for tree in self._rf.estimators_])
        gb_pred = float(self._gb.predict(vec)[0])

        mean_pred = max(0.0, 0.5 * float(np.mean(tree_preds)) + 0.5 * gb_pred)
        low = max(0.0, float(np.percentile(tree_preds, 20)))
        high = max(0.0, float(np.percentile(tree_preds, 80)))

        return mean_pred, low, high

    def get_feature_importances(self) -> dict[str, float]:
        if not self._is_trained:
            return {}
        rf_imp = self._rf.feature_importances_
        gb_imp = self._gb.feature_importances_
        avg_imp = (rf_imp + gb_imp) / 2.0
        result = {
            _FEATURE_NAMES[i]: round(float(avg_imp[i]), 4) for i in range(len(_FEATURE_NAMES))
        }
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def predict_duration(
    schedule: ParsedSchedule,
    benchmarks: list[BenchmarkMetrics],
    *,
    predictor: DurationPredictor | None = None,
) -> DurationPrediction:
    """Predict project duration using ML trained on benchmark data.

    Args:
        schedule: The schedule to predict duration for.
        benchmarks: Benchmark dataset for training.
        predictor: Optional pre-trained predictor.

    Returns:
        A ``DurationPrediction`` with predicted duration and confidence.

    References:
        - AbdElMottaleb (2025) — ML for Construction Scheduling
        - Breiman (2001) — Random Forests
        - Friedman (2001) — Gradient Boosting Machines
    """
    result = DurationPrediction()

    if not _HAS_SKLEARN:
        result.methodology = "scikit-learn not available — install meridianiq[ml]"
        return result

    # Extract current schedule metrics
    project_metrics = extract_benchmark_metrics(schedule)

    # Train if needed
    if predictor is None:
        predictor = DurationPredictor()
    if not predictor.is_trained:
        try:
            training_info = predictor.train(benchmarks)
            logger.info("Duration predictor trained on %d samples", training_info["samples"])
        except ValueError as exc:
            result.methodology = f"Training failed: {exc}"
            return result

    # Predict
    mean_dur, low, high = predictor.predict_with_confidence(project_metrics)
    result.predicted_duration_days = round(mean_dur, 1)
    result.confidence_low = round(low, 1)
    result.confidence_high = round(high, 1)
    result.model_r_squared = predictor._r_squared
    result.training_samples = predictor._training_samples
    result.feature_importances = predictor.get_feature_importances()

    # Compare with actual CPM duration
    from src.analytics.cpm import CPMCalculator

    try:
        cpm = CPMCalculator(schedule).calculate()
        result.actual_duration_days = round(cpm.project_duration, 1)
        result.delta_days = round(mean_dur - cpm.project_duration, 1)
    except Exception:
        pass

    result.methodology = (
        "ML ensemble (Random Forest + Gradient Boosting) trained on "
        f"{predictor._training_samples} benchmark projects "
        f"(R²={predictor._r_squared})"
    )

    result.summary = {
        "predicted_duration_days": result.predicted_duration_days,
        "confidence_interval": {
            "low": result.confidence_low,
            "high": result.confidence_high,
        },
        "actual_duration_days": result.actual_duration_days,
        "delta_days": result.delta_days,
        "model_r_squared": result.model_r_squared,
        "training_samples": result.training_samples,
        "methodology": result.methodology,
        "top_features": dict(list(result.feature_importances.items())[:5]),
        "references": [
            "AbdElMottaleb (2025) — ML for Construction Scheduling",
            "Breiman (2001) — Random Forests",
            "Friedman (2001) — Gradient Boosting Machines",
        ],
    }

    return result
