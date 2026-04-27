# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""ADR-0019 §"W2 — B2" — authoritative ``is_construction_active`` boolean
on the lifecycle summary surface.

The W4 calibration (see ``docs/adr/0009-w4-outcome.md``) validated the
binary "construction-vs-non-construction" classification but did NOT
validate the full 5+1 phase taxonomy. This module exercises the
contract that powers the honesty-debt closure: the summary endpoint
exposes the authoritative boolean alongside the preview-flagged 5+1
phase, and the boolean is tri-state so "we don't know" never silently
collapses into "not in construction".
"""

from __future__ import annotations

import os

os.environ["ENVIRONMENT"] = "development"

from src.api.routers.lifecycle import _inference_from_artifact  # noqa: E402


def _artifact(phase: str, confidence: float = 0.75) -> dict:
    """Synthetic ``schedule_derived_artifacts`` row for a given phase."""
    return {
        "payload": {
            "phase": phase,
            "confidence": confidence,
            "rationale": {"rule": "test"},
        },
        "engine_version": "4.0",
        "ruleset_version": "lifecycle_phase-v1-2026-04",
        "effective_at": None,
        "computed_at": None,
    }


class TestIsConstructionActiveDerivation:
    """``_inference_from_artifact`` derives the boolean from ``phase``."""

    def test_construction_phase_yields_true(self) -> None:
        inf = _inference_from_artifact(_artifact("construction"))
        assert inf.is_construction_active is True

    def test_design_phase_yields_false(self) -> None:
        inf = _inference_from_artifact(_artifact("design"))
        assert inf.is_construction_active is False

    def test_planning_phase_yields_false(self) -> None:
        inf = _inference_from_artifact(_artifact("planning"))
        assert inf.is_construction_active is False

    def test_procurement_phase_yields_false(self) -> None:
        inf = _inference_from_artifact(_artifact("procurement"))
        assert inf.is_construction_active is False

    def test_closeout_phase_yields_false(self) -> None:
        inf = _inference_from_artifact(_artifact("closeout"))
        assert inf.is_construction_active is False

    def test_unknown_phase_yields_none_not_false(self) -> None:
        """Critical contract: ``unknown`` MUST map to ``None``, never
        ``False``. The W4 honesty-debt closure exists precisely so the
        UI can render a tri-state ("we don't know" ≠ "not in
        construction"). A regression here re-introduces the silent
        coercion the post-mortem documented as wrong."""
        inf = _inference_from_artifact(_artifact("unknown"))
        assert inf.is_construction_active is None

    def test_unknown_via_drift_recovery_yields_none(self) -> None:
        """``_inference_from_artifact`` coerces unknown payload-shape
        drift to ``phase='unknown'``. The boolean must follow."""
        inf = _inference_from_artifact(_artifact("not-a-real-phase"))
        assert inf.phase == "unknown"
        assert inf.is_construction_active is None


class TestEffectiveIsConstructionActive:
    """``_build_summary`` propagates ``effective_is_construction_active``
    across the inference / override / lock-without-override paths.

    The store is stubbed at the methods ``_build_summary`` actually
    calls — ``get_latest_derived_artifact``, ``get_lifecycle_phase_lock``,
    ``get_latest_lifecycle_override`` — so the test pins the contract
    without requiring a full in-memory store fixture.
    """

    @staticmethod
    def _stub_store(
        artifact: dict | None = None,
        lock: bool = False,
        override: dict | None = None,
    ):
        class _Stub:
            def get_latest_derived_artifact(self, **_kwargs: object) -> dict | None:
                return artifact

            def get_lifecycle_phase_lock(self, _project_id: str) -> bool:
                return lock

            def get_latest_lifecycle_override(self, _project_id: str) -> dict | None:
                return override

        return _Stub()

    def test_inferred_construction_yields_true(self) -> None:
        from src.api.routers.lifecycle import _build_summary

        store = self._stub_store(artifact=_artifact("construction"))
        s = _build_summary(store, "p1")
        assert s.effective_phase == "construction"
        assert s.effective_is_construction_active is True
        assert s.source == "inferred"

    def test_inferred_design_yields_false(self) -> None:
        from src.api.routers.lifecycle import _build_summary

        store = self._stub_store(artifact=_artifact("design"))
        s = _build_summary(store, "p1")
        assert s.effective_phase == "design"
        assert s.effective_is_construction_active is False

    def test_locked_override_construction_over_inferred_design_yields_true(
        self,
    ) -> None:
        """A Cost Engineer override authoritatively flips the boolean.
        Provenance is ``source=='manual'``; consumers that need to
        distinguish calibrated from manual MUST read ``source``."""
        from src.api.routers.lifecycle import _build_summary

        store = self._stub_store(
            artifact=_artifact("design"),
            lock=True,
            override={
                "id": "ov-1",
                "project_id": "p1",
                "inferred_phase": "design",
                "override_phase": "construction",
                "override_reason": "I know better",
                "overridden_by": "u1",
                "overridden_at": None,
                "engine_version": "4.0",
                "ruleset_version": "lifecycle_phase-v1-2026-04",
            },
        )
        s = _build_summary(store, "p1")
        assert s.effective_phase == "construction"
        assert s.effective_is_construction_active is True
        assert s.source == "manual"

    def test_locked_no_override_no_inference_yields_none(self) -> None:
        """Locked + no override + no inference is the cold-start edge:
        ``effective_phase`` falls back to ``'unknown'`` and the boolean
        MUST be ``None``, never ``False``."""
        from src.api.routers.lifecycle import _build_summary

        store = self._stub_store(artifact=None, lock=True, override=None)
        s = _build_summary(store, "p1")
        assert s.effective_phase == "unknown"
        assert s.effective_is_construction_active is None

    def test_no_artifact_no_lock_yields_none(self) -> None:
        """Pre-materialization edge: nothing in any source. The boolean
        must propagate as ``None``."""
        from src.api.routers.lifecycle import _build_summary

        store = self._stub_store(artifact=None, lock=False, override=None)
        s = _build_summary(store, "p1")
        assert s.effective_phase == "unknown"
        assert s.effective_is_construction_active is None
        assert s.source is None

    def test_summary_serializes_none_as_null_not_missing(self) -> None:
        """Pydantic v2 ``model_dump_json()`` must include the field as
        explicit ``null`` for the unknown path — a missing key would
        let a stale TS client treat it as ``undefined`` and fall back
        to truthy/falsy coercion."""
        import json

        from src.api.routers.lifecycle import _build_summary

        store = self._stub_store(artifact=None, lock=False, override=None)
        s = _build_summary(store, "p1")
        body = json.loads(s.model_dump_json())
        assert "effective_is_construction_active" in body
        assert body["effective_is_construction_active"] is None
