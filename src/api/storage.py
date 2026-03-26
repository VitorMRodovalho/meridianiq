# MIT License
# Copyright (c) 2025 Vitor Maia Rodovalho
"""In-memory storage for parsed projects, forensic timelines, TIA analyses, EVM analyses, and risk simulations (v0.5).

Provides simple dictionary-based stores for parsed schedules, their raw
XER bytes, forensic analysis timelines, and TIA analyses.  Designed as
a placeholder until a persistent database layer is introduced.
"""
from __future__ import annotations

import threading
from typing import Any

from src.analytics.evm import EVMAnalysisResult
from src.analytics.forensics import ForensicTimeline
from src.analytics.risk import SimulationResult
from src.analytics.tia import TIAAnalysis
from src.parser.models import ParsedSchedule


class ProjectStore:
    """In-memory storage for parsed projects.

    Thread-safe via a simple lock.  Not intended for production use --
    all data is lost when the process exits.

    Usage::

        store = ProjectStore()
        pid = store.add(schedule, raw_bytes)
        schedule = store.get(pid)
    """

    def __init__(self) -> None:
        """Initialise an empty store."""
        self._projects: dict[str, ParsedSchedule] = {}
        self._xer_data: dict[str, bytes] = {}
        self._counter: int = 0
        self._lock = threading.Lock()

    def add(self, schedule: ParsedSchedule, xer_bytes: bytes) -> str:
        """Store a parsed schedule and return its project_id.

        Args:
            schedule: The parsed schedule to store.
            xer_bytes: The raw XER file bytes.

        Returns:
            A unique project_id string.
        """
        with self._lock:
            self._counter += 1
            project_id = f"proj-{self._counter:04d}"
            self._projects[project_id] = schedule
            self._xer_data[project_id] = xer_bytes
        return project_id

    def get(self, project_id: str) -> ParsedSchedule | None:
        """Retrieve a parsed schedule by project_id.

        Args:
            project_id: The identifier returned by ``add()``.

        Returns:
            The stored ``ParsedSchedule``, or ``None`` if not found.
        """
        return self._projects.get(project_id)

    def get_xer_bytes(self, project_id: str) -> bytes | None:
        """Retrieve raw XER bytes by project_id.

        Args:
            project_id: The identifier returned by ``add()``.

        Returns:
            The raw bytes, or ``None`` if not found.
        """
        return self._xer_data.get(project_id)

    def list_all(self) -> list[dict[str, Any]]:
        """List all stored projects with summary info.

        Returns:
            A list of dictionaries with ``project_id``, ``name``,
            ``activity_count``, and ``relationship_count``.
        """
        result: list[dict[str, Any]] = []
        for pid, schedule in self._projects.items():
            name = ""
            if schedule.projects:
                name = schedule.projects[0].proj_short_name
            result.append({
                "project_id": pid,
                "name": name,
                "activity_count": len(schedule.activities),
                "relationship_count": len(schedule.relationships),
            })
        return result

    def clear(self) -> None:
        """Remove all stored projects."""
        with self._lock:
            self._projects.clear()
            self._xer_data.clear()
            self._counter = 0


class TimelineStore:
    """In-memory storage for forensic timelines.

    Thread-safe via a simple lock.  Not intended for production use --
    all data is lost when the process exits.

    Usage::

        store = TimelineStore()
        tid = store.add(timeline)
        timeline = store.get(tid)
    """

    def __init__(self) -> None:
        """Initialise an empty store."""
        self._timelines: dict[str, ForensicTimeline] = {}
        self._counter: int = 0
        self._lock = threading.Lock()

    def add(self, timeline: ForensicTimeline) -> str:
        """Store a forensic timeline and return its timeline_id.

        Args:
            timeline: The forensic timeline to store.

        Returns:
            A unique timeline_id string.
        """
        with self._lock:
            self._counter += 1
            tid = f"timeline-{self._counter:04d}"
            timeline.timeline_id = tid
            self._timelines[tid] = timeline
        return tid

    def get(self, timeline_id: str) -> ForensicTimeline | None:
        """Retrieve a forensic timeline by timeline_id.

        Args:
            timeline_id: The identifier returned by ``add()``.

        Returns:
            The stored ``ForensicTimeline``, or ``None`` if not found.
        """
        return self._timelines.get(timeline_id)

    def list_all(self) -> list[dict[str, Any]]:
        """List all stored timelines with summary info.

        Returns:
            A list of dictionaries with key timeline metadata.
        """
        return [
            {
                "timeline_id": t.timeline_id,
                "project_name": t.project_name,
                "schedule_count": t.schedule_count,
                "total_delay_days": t.total_delay_days,
                "window_count": len(t.windows),
            }
            for t in self._timelines.values()
        ]

    def clear(self) -> None:
        """Remove all stored timelines."""
        with self._lock:
            self._timelines.clear()
            self._counter = 0


class TIAStore:
    """In-memory storage for TIA analyses.

    Thread-safe via a simple lock.  Not intended for production use --
    all data is lost when the process exits.

    Usage::

        store = TIAStore()
        aid = store.add(analysis)
        analysis = store.get(aid)
    """

    def __init__(self) -> None:
        """Initialise an empty store."""
        self._analyses: dict[str, TIAAnalysis] = {}
        self._counter: int = 0
        self._lock = threading.Lock()

    def add(self, analysis: TIAAnalysis) -> str:
        """Store a TIA analysis and return its analysis_id.

        Args:
            analysis: The TIA analysis to store.

        Returns:
            A unique analysis_id string.
        """
        with self._lock:
            self._counter += 1
            aid = f"tia-{self._counter:04d}"
            analysis.analysis_id = aid
            self._analyses[aid] = analysis
        return aid

    def get(self, analysis_id: str) -> TIAAnalysis | None:
        """Retrieve a TIA analysis by analysis_id.

        Args:
            analysis_id: The identifier returned by ``add()``.

        Returns:
            The stored ``TIAAnalysis``, or ``None`` if not found.
        """
        return self._analyses.get(analysis_id)

    def list_all(self) -> list[dict[str, Any]]:
        """List all stored TIA analyses with summary info.

        Returns:
            A list of dictionaries with key analysis metadata.
        """
        return [
            {
                "analysis_id": a.analysis_id,
                "project_name": a.project_name,
                "fragment_count": len(a.fragments),
                "net_delay": a.net_delay,
                "total_owner_delay": a.total_owner_delay,
                "total_contractor_delay": a.total_contractor_delay,
            }
            for a in self._analyses.values()
        ]

    def clear(self) -> None:
        """Remove all stored analyses."""
        with self._lock:
            self._analyses.clear()
            self._counter = 0


class EVMStore:
    """In-memory storage for EVM analyses.

    Thread-safe via a simple lock.  Not intended for production use --
    all data is lost when the process exits.

    Usage::

        store = EVMStore()
        eid = store.add(result)
        result = store.get(eid)
    """

    def __init__(self) -> None:
        """Initialise an empty store."""
        self._analyses: dict[str, EVMAnalysisResult] = {}
        self._counter: int = 0
        self._lock = threading.Lock()

    def add(self, result: EVMAnalysisResult) -> str:
        """Store an EVM analysis result and return its analysis_id.

        Args:
            result: The EVM analysis result to store.

        Returns:
            A unique analysis_id string.
        """
        with self._lock:
            self._counter += 1
            aid = f"evm-{self._counter:04d}"
            result.analysis_id = aid
            self._analyses[aid] = result
        return aid

    def get(self, analysis_id: str) -> EVMAnalysisResult | None:
        """Retrieve an EVM analysis result by analysis_id.

        Args:
            analysis_id: The identifier returned by ``add()``.

        Returns:
            The stored ``EVMAnalysisResult``, or ``None`` if not found.
        """
        return self._analyses.get(analysis_id)

    def list_all(self) -> list[dict[str, Any]]:
        """List all stored EVM analyses with summary info.

        Returns:
            A list of dictionaries with key analysis metadata.
        """
        return [
            {
                "analysis_id": a.analysis_id,
                "project_name": a.project_name,
                "project_id": a.project_id,
                "bac": a.metrics.bac,
                "spi": round(a.metrics.spi, 3),
                "cpi": round(a.metrics.cpi, 3),
                "schedule_health": a.schedule_health.status,
                "cost_health": a.cost_health.status,
            }
            for a in self._analyses.values()
        ]

    def clear(self) -> None:
        """Remove all stored EVM analyses."""
        with self._lock:
            self._analyses.clear()
            self._counter = 0


class RiskStore:
    """In-memory storage for Monte Carlo risk simulation results.

    Thread-safe via a simple lock.  Not intended for production use --
    all data is lost when the process exits.

    Usage::

        store = RiskStore()
        sid = store.add(result)
        result = store.get(sid)
    """

    def __init__(self) -> None:
        """Initialise an empty store."""
        self._simulations: dict[str, SimulationResult] = {}
        self._counter: int = 0
        self._lock = threading.Lock()

    def add(self, result: SimulationResult) -> str:
        """Store a simulation result and return its simulation_id.

        Args:
            result: The simulation result to store.

        Returns:
            A unique simulation_id string.
        """
        with self._lock:
            self._counter += 1
            sid = f"risk-{self._counter:04d}"
            result.simulation_id = sid
            self._simulations[sid] = result
        return sid

    def get(self, simulation_id: str) -> SimulationResult | None:
        """Retrieve a simulation result by simulation_id.

        Args:
            simulation_id: The identifier returned by ``add()``.

        Returns:
            The stored ``SimulationResult``, or ``None`` if not found.
        """
        return self._simulations.get(simulation_id)

    def list_all(self) -> list[dict[str, Any]]:
        """List all stored simulations with summary info.

        Returns:
            A list of dictionaries with key simulation metadata.
        """
        results: list[dict[str, Any]] = []
        for s in self._simulations.values():
            p50 = 0.0
            p80 = 0.0
            for pv in s.p_values:
                if pv.percentile == 50:
                    p50 = pv.duration_days
                if pv.percentile == 80:
                    p80 = pv.duration_days
            results.append({
                "simulation_id": s.simulation_id,
                "project_name": s.project_name,
                "project_id": s.project_id,
                "iterations": s.iterations,
                "deterministic_days": s.deterministic_days,
                "mean_days": s.mean_days,
                "p50_days": p50,
                "p80_days": p80,
            })
        return results

    def clear(self) -> None:
        """Remove all stored simulations."""
        with self._lock:
            self._simulations.clear()
            self._counter = 0
