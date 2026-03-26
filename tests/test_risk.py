# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for Monte Carlo schedule risk simulation engine.

Verifies sampling distributions, simulation correctness, criticality
indices, sensitivity analysis, histogram shape, S-curve monotonicity,
risk events, seed reproducibility, and default uncertainty.

References:
    - AACE RP 57R-09: Integrated Cost and Schedule Risk Analysis
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.analytics.risk import (
    DistributionType,
    DurationRisk,
    MonteCarloSimulator,
    RiskEvent,
    SimulationConfig,
    _rank_array,
)
from src.parser.xer_reader import XERReader
from tests.fixtures.sample_xer_generator import generate_sample_xer


@pytest.fixture()
def schedule():
    """Parse the sample XER and return a ParsedSchedule."""
    with tempfile.TemporaryDirectory() as tmpdir:
        xer_path = generate_sample_xer(Path(tmpdir) / "sample.xer")
        reader = XERReader(xer_path)
        return reader.parse()


# ── Sampling tests ────────────────────────────────────────────────


class TestTriangularSampling:
    """Test triangular distribution sampling."""

    def test_output_within_range(self, schedule) -> None:
        """Triangular samples should be within [min, max]."""
        config = SimulationConfig(iterations=500, seed=42, default_uncertainty=0)
        sim = MonteCarloSimulator(schedule, config)

        # Pick the first real activity
        key = list(sim._activities.keys())[0]
        task = sim._activities[key]
        orig = task.target_drtn_hr_cnt

        risk = DurationRisk(
            activity_id=key,
            distribution=DistributionType.TRIANGULAR,
            min_duration=orig * 0.5,
            most_likely=orig,
            max_duration=orig * 2.0,
        )

        rng = np.random.default_rng(42)
        samples = [sim._sample_duration(risk, rng) for _ in range(1000)]
        assert all(risk.min_duration <= s <= risk.max_duration for s in samples)


class TestPERTSampling:
    """Test PERT-Beta distribution sampling."""

    def test_mean_approximation(self, schedule) -> None:
        """PERT mean should approximate (min + 4*mode + max) / 6."""
        config = SimulationConfig(iterations=500, seed=42, default_uncertainty=0)
        sim = MonteCarloSimulator(schedule, config)

        lo, ml, hi = 20.0, 40.0, 80.0
        risk = DurationRisk(
            activity_id="test",
            distribution=DistributionType.PERT,
            min_duration=lo,
            most_likely=ml,
            max_duration=hi,
        )
        expected_mean = (lo + 4 * ml + hi) / 6

        rng = np.random.default_rng(42)
        samples = [sim._sample_duration(risk, rng) for _ in range(5000)]
        actual_mean = np.mean(samples)

        # Should be within 5% of the theoretical PERT mean
        assert abs(actual_mean - expected_mean) / expected_mean < 0.05


class TestUniformSampling:
    """Test uniform distribution sampling."""

    def test_uniform_distribution(self, schedule) -> None:
        """Uniform samples should be spread across [min, max]."""
        config = SimulationConfig(iterations=500, seed=42, default_uncertainty=0)
        sim = MonteCarloSimulator(schedule, config)

        risk = DurationRisk(
            activity_id="test",
            distribution=DistributionType.UNIFORM,
            min_duration=10.0,
            most_likely=20.0,
            max_duration=30.0,
        )

        rng = np.random.default_rng(42)
        samples = [sim._sample_duration(risk, rng) for _ in range(2000)]
        assert all(10.0 <= s <= 30.0 for s in samples)
        # Mean should be ~20
        assert abs(np.mean(samples) - 20.0) < 1.0


# ── Simulation tests ─────────────────────────────────────────────


class TestSimulationDeterministic:
    """All FIXED activities should give deterministic completion."""

    def test_completion_matches_deterministic(self, schedule) -> None:
        """With FIXED durations, every iteration should match the CPM result."""
        config = SimulationConfig(
            iterations=100, seed=42, default_uncertainty=0
        )
        sim = MonteCarloSimulator(schedule, config)

        # Create FIXED risks for all activities (using remaining durations
        # to match how CPM builds the graph)
        risks = [
            DurationRisk(
                activity_id=key,
                distribution=DistributionType.FIXED,
                most_likely=task.remain_drtn_hr_cnt,
            )
            for key, task in sim._activities.items()
        ]

        result = sim.simulate(duration_risks=risks)
        det = result.deterministic_days

        # All P-values should equal deterministic
        for pv in result.p_values:
            assert abs(pv.duration_days - det) < 0.01, (
                f"P{pv.percentile} = {pv.duration_days}, expected {det}"
            )


class TestSimulationWithUncertainty:
    """Verify P50 near deterministic and P90 > P50."""

    def test_p_value_ordering(self, schedule) -> None:
        """P50 should be approximately deterministic; P90 > P50."""
        config = SimulationConfig(
            iterations=1000,
            seed=42,
            default_uncertainty=0.2,
            default_distribution=DistributionType.PERT,
        )
        sim = MonteCarloSimulator(schedule, config)
        result = sim.simulate()

        p50 = next(pv for pv in result.p_values if pv.percentile == 50)
        p90 = next(pv for pv in result.p_values if pv.percentile == 90)
        p10 = next(pv for pv in result.p_values if pv.percentile == 10)

        # P50 should be within ~20% of deterministic
        assert abs(p50.duration_days - result.deterministic_days) / result.deterministic_days < 0.2

        # P90 > P50 > P10
        assert p90.duration_days > p50.duration_days
        assert p50.duration_days > p10.duration_days


class TestCriticalityIndex:
    """Critical path activities should have high criticality."""

    def test_cp_activity_high_criticality(self, schedule) -> None:
        """An activity on the deterministic CP should have high criticality."""
        config = SimulationConfig(
            iterations=500, seed=42, default_uncertainty=0.1
        )
        sim = MonteCarloSimulator(schedule, config)
        result = sim.simulate()

        # Get deterministic CP activities
        base_cp = set()
        for tid in sim._base_result.critical_path:
            key = sim._task_id_to_key.get(tid)
            if key:
                base_cp.add(key)

        # At least one CP activity should have >50% criticality
        cp_crits = [
            c for c in result.criticality
            if c.activity_id in base_cp and c.criticality_pct > 50
        ]
        assert len(cp_crits) > 0, (
            f"No CP activities with >50% criticality. "
            f"CP activities: {base_cp}. "
            f"Top criticalities: {[(c.activity_id, c.criticality_pct) for c in result.criticality[:5]]}"
        )


class TestSensitivityPositive:
    """Longer durations should correlate with later completion."""

    def test_positive_correlation(self, schedule) -> None:
        """At least one activity should have positive sensitivity."""
        config = SimulationConfig(
            iterations=500, seed=42, default_uncertainty=0.2
        )
        sim = MonteCarloSimulator(schedule, config)
        result = sim.simulate()

        positive = [s for s in result.sensitivity if s.correlation > 0.1]
        assert len(positive) > 0, (
            f"No activities with positive correlation > 0.1. "
            f"Top sensitivities: {[(s.activity_id, s.correlation) for s in result.sensitivity[:5]]}"
        )


class TestHistogramShape:
    """Verify histogram bins and counts."""

    def test_histogram_bins_and_counts(self, schedule) -> None:
        """Histogram should have 30 bins with counts summing to iterations."""
        config = SimulationConfig(iterations=1000, seed=42)
        sim = MonteCarloSimulator(schedule, config)
        result = sim.simulate()

        assert len(result.histogram) == 30
        total_count = sum(b.count for b in result.histogram)
        assert total_count == 1000

        # All frequencies should be non-negative
        assert all(b.frequency >= 0 for b in result.histogram)
        # Frequencies should sum to ~1.0
        assert abs(sum(b.frequency for b in result.histogram) - 1.0) < 0.01


class TestSCurveMonotonic:
    """Cumulative probability should be monotonically increasing."""

    def test_monotonic_increase(self, schedule) -> None:
        """S-curve cumulative probability should only increase."""
        config = SimulationConfig(iterations=1000, seed=42)
        sim = MonteCarloSimulator(schedule, config)
        result = sim.simulate()

        assert len(result.s_curve) > 2

        for i in range(1, len(result.s_curve)):
            assert result.s_curve[i].cumulative_probability >= result.s_curve[i - 1].cumulative_probability
            assert result.s_curve[i].duration_days >= result.s_curve[i - 1].duration_days


class TestRiskEvents:
    """Discrete risk events with 100% probability."""

    def test_always_fires(self, schedule) -> None:
        """A 100% probability event should always add impact."""
        config = SimulationConfig(
            iterations=200, seed=42, default_uncertainty=0
        )
        sim = MonteCarloSimulator(schedule, config)

        # Use FIXED durations so the only variability is the risk event
        key = list(sim._activities.keys())[0]
        task = sim._activities[key]

        risks = [
            DurationRisk(
                activity_id=k,
                distribution=DistributionType.FIXED,
                most_likely=sim._activities[k].remain_drtn_hr_cnt,
            )
            for k in sim._activities.keys()
        ]

        # Without event
        result_no_event = sim.simulate(duration_risks=risks)

        # With 100% probability event on ALL CP activities
        # to ensure it extends the critical path regardless of parallel paths
        cp_keys = []
        for tid in sim._base_result.critical_path:
            k = sim._task_id_to_key.get(tid)
            if k:
                cp_keys.append(k)
        assert len(cp_keys) > 0

        event = RiskEvent(
            risk_id="RE-TEST",
            name="Test Event",
            probability=1.0,
            impact_hours=400.0,  # 50 working days -- large enough to extend any path
            affected_activities=cp_keys,
        )

        result_with_event = sim.simulate(duration_risks=risks, risk_events=[event])

        # The mean completion should be higher with the event
        assert result_with_event.mean_days > result_no_event.mean_days


class TestSeedReproducibility:
    """Same seed should produce identical results."""

    def test_same_seed_same_results(self, schedule) -> None:
        """Two runs with the same seed should produce identical P-values."""
        config = SimulationConfig(iterations=500, seed=12345)

        sim1 = MonteCarloSimulator(schedule, config)
        result1 = sim1.simulate()

        sim2 = MonteCarloSimulator(schedule, config)
        result2 = sim2.simulate()

        for pv1, pv2 in zip(result1.p_values, result2.p_values):
            assert pv1.percentile == pv2.percentile
            assert abs(pv1.duration_days - pv2.duration_days) < 0.001


class TestDefaultUncertainty:
    """Default uncertainty should spread results around deterministic."""

    def test_default_creates_spread(self, schedule) -> None:
        """With default 20% uncertainty, std dev should be positive."""
        config = SimulationConfig(
            iterations=500, seed=42, default_uncertainty=0.2
        )
        sim = MonteCarloSimulator(schedule, config)
        result = sim.simulate()

        assert result.std_days > 0
        assert result.mean_days > 0


class TestRankArray:
    """Test the internal rank array function."""

    def test_basic_ranking(self) -> None:
        """Verify correct ranking with and without ties."""
        arr = np.array([3.0, 1.0, 4.0, 1.0, 5.0])
        ranks = _rank_array(arr)
        # 1.0 appears twice -> ranks 1, 2 -> average 1.5
        # 3.0 -> rank 3
        # 4.0 -> rank 4
        # 5.0 -> rank 5
        assert ranks[0] == 3.0  # value 3.0
        assert ranks[1] == 1.5  # value 1.0 (tie)
        assert ranks[2] == 4.0  # value 4.0
        assert ranks[3] == 1.5  # value 1.0 (tie)
        assert ranks[4] == 5.0  # value 5.0
