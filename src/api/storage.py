# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""In-memory storage for parsed projects, forensic timelines, TIA analyses, EVM analyses, risk simulations, and reports.

Provides simple dictionary-based stores for parsed schedules, their raw
XER bytes, forensic analysis timelines, and TIA analyses.  Designed as
a placeholder until a persistent database layer is introduced.

Analysis results are owned (ADR-0030 §5): every entry records the user
it was produced for, and reads, listings and lookups are filtered by that
owner. Result ids are random (``<prefix>-<32 hex>``), so one tenant cannot
enumerate another's results by counting.
"""

from __future__ import annotations

import builtins
import threading
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

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

    def add(self, schedule: ParsedSchedule, xer_bytes: bytes, user_id: str | None = None) -> str:
        """Store a parsed schedule and return its project_id.

        Args:
            schedule: The parsed schedule to store.
            xer_bytes: The raw XER file bytes.
            user_id: Optional user identifier (ignored in memory store).

        Returns:
            A unique project_id string.
        """
        with self._lock:
            self._counter += 1
            project_id = f"proj-{self._counter:04d}"
            self._projects[project_id] = schedule
            self._xer_data[project_id] = xer_bytes
        return project_id

    def get(self, project_id: str, user_id: str | None = None) -> ParsedSchedule | None:
        """Retrieve a parsed schedule by project_id.

        Args:
            project_id: The identifier returned by ``add()``.
            user_id: Optional user identifier (ignored in memory store).

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

    def list_ids(self) -> list[str]:
        """Return all stored project IDs.

        Returns:
            A list of project_id strings.
        """
        with self._lock:
            return list(self._projects.keys())

    def list_all(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """List all stored projects with summary info.

        Args:
            user_id: Optional user identifier (ignored in memory store).

        Returns:
            A list of dictionaries with ``project_id``, ``name``,
            ``activity_count``, and ``relationship_count``.
        """
        result: list[dict[str, Any]] = []
        for pid, schedule in self._projects.items():
            name = ""
            if schedule.projects:
                name = schedule.projects[0].proj_short_name
            result.append(
                {
                    "project_id": pid,
                    "name": name,
                    "activity_count": len(schedule.activities),
                    "relationship_count": len(schedule.relationships),
                }
            )
        return result

    def clear(self) -> None:
        """Remove all stored projects."""
        with self._lock:
            self._projects.clear()
            self._xer_data.clear()
            self._counter = 0


# ------------------------------------------------------------------ #
# Owned result stores (ADR-0030 §5)                                   #
# ------------------------------------------------------------------ #

T = TypeVar("T")

#: Reports kept per owner before the oldest are evicted. A report is a
#: whole PDF held in process memory, and the UI downloads it right after
#: generating it, so a small window is enough and bounds what one tenant
#: can pin in RAM.
REPORTS_PER_OWNER = 50


@dataclass(frozen=True)
class _Entry(Generic[T]):
    """One stored result together with who it belongs to."""

    value: T
    owner_id: str
    project_ids: tuple[str, ...]
    created_at: datetime


class OwnedResultStore(Generic[T]):
    """Thread-safe in-memory store whose entries are visible only to their owner.

    Each entry records ``owner_id`` (the ``Principal.user_id`` of the
    request that produced it), the project ids it was computed from, and
    its creation time. There is no unfiltered read: :meth:`get`,
    :meth:`list`, :meth:`latest` and :meth:`summaries` all take the owner,
    and an entry owned by someone else answers exactly like a missing one.

    Ids are ``f"{prefix}-{uuid4().hex}"``. Not durable: all data is lost
    when the process exits.
    """

    #: Id prefix: ``"risk"`` gives ``risk-<32 hex>``.
    prefix: str = "result"
    #: Beyond this many entries per owner the oldest are evicted (``None``: no cap).
    max_per_owner: int | None = None

    def __init__(self) -> None:
        """Initialise an empty store."""
        self._entries: dict[str, _Entry[T]] = {}
        self._lock = threading.Lock()

    # -- hooks for subclasses -------------------------------------------

    def _stamp(self, value: T, result_id: str) -> None:
        """Write the new id into ``value`` when the result carries its own id."""

    def _summary(self, result_id: str, value: T) -> dict[str, Any]:
        """Return the listing row for one entry."""
        return {"id": result_id}

    def _forget(self, result_ids: builtins.list[str]) -> None:
        """Drop secondary indexes of removed entries. Called with the lock held."""

    # -- public API -----------------------------------------------------

    def add(self, value: T, *, owner_id: str, project_ids: Iterable[str]) -> str:
        """Store ``value`` for ``owner_id`` and return its new random id.

        Args:
            value: The result to store.
            owner_id: The principal the result belongs to (required).
            project_ids: The project ids the result was computed from.

        Raises:
            ValueError: If ``owner_id`` is empty.
            TypeError: If ``project_ids`` is a single string.
        """
        if not owner_id:
            raise ValueError("owner_id is required")
        if isinstance(project_ids, str):
            raise TypeError("project_ids must be an iterable of ids, not a string")
        result_id = f"{self.prefix}-{uuid.uuid4().hex}"
        self._stamp(value, result_id)
        entry = _Entry(
            value=value,
            owner_id=owner_id,
            project_ids=tuple(pid for pid in project_ids if pid),
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._entries[result_id] = entry
            if self.max_per_owner is not None:
                owned = [rid for rid, e in self._entries.items() if e.owner_id == owner_id]
                evicted = owned[: max(0, len(owned) - self.max_per_owner)]
                for rid in evicted:
                    del self._entries[rid]
                if evicted:
                    self._forget(evicted)
        return result_id

    def get(self, result_id: str, *, owner_id: str) -> T | None:
        """Return the result if it exists and belongs to ``owner_id``, else ``None``."""
        with self._lock:
            entry = self._entries.get(result_id)
        if entry is None or entry.owner_id != owner_id:
            return None
        return entry.value

    def list(self, owner_id: str, project_id: str | None = None) -> builtins.list[T]:
        """Return the owner's results, oldest first.

        Args:
            owner_id: Only this principal's results are returned.
            project_id: When given, only results computed from this project.
        """
        with self._lock:
            return [
                e.value
                for e in self._entries.values()
                if e.owner_id == owner_id and (project_id is None or project_id in e.project_ids)
            ]

    def latest(self, owner_id: str, project_id: str) -> T | None:
        """Return the owner's most recent result for ``project_id``, or ``None``."""
        items = self.list(owner_id, project_id)
        return items[-1] if items else None

    def summaries(
        self, owner_id: str, project_id: str | None = None
    ) -> builtins.list[dict[str, Any]]:
        """Return listing rows for the owner's results, oldest first."""
        with self._lock:
            rows = [
                (rid, e.value)
                for rid, e in self._entries.items()
                if e.owner_id == owner_id and (project_id is None or project_id in e.project_ids)
            ]
        return [self._summary(rid, value) for rid, value in rows]

    def purge_owner(self, owner_id: str) -> int:
        """Delete every result of ``owner_id`` (right to erasure); return how many."""
        with self._lock:
            doomed = [rid for rid, e in self._entries.items() if e.owner_id == owner_id]
            for rid in doomed:
                del self._entries[rid]
            if doomed:
                self._forget(doomed)
        return len(doomed)

    def clear(self) -> None:
        """Remove all stored results."""
        with self._lock:
            ids = builtins.list(self._entries)
            self._entries.clear()
            if ids:
                self._forget(ids)


class TimelineStore(OwnedResultStore[ForensicTimeline]):
    """Owned in-memory storage for forensic timelines (ids ``timeline-<hex>``)."""

    prefix = "timeline"

    def _stamp(self, value: ForensicTimeline, result_id: str) -> None:
        value.timeline_id = result_id

    def _summary(self, result_id: str, value: ForensicTimeline) -> dict[str, Any]:
        return {
            "timeline_id": value.timeline_id,
            "project_name": value.project_name,
            "schedule_count": value.schedule_count,
            "total_delay_days": value.total_delay_days,
            "window_count": len(value.windows),
        }


class TIAStore(OwnedResultStore[TIAAnalysis]):
    """Owned in-memory storage for TIA analyses (ids ``tia-<hex>``)."""

    prefix = "tia"

    def _stamp(self, value: TIAAnalysis, result_id: str) -> None:
        value.analysis_id = result_id

    def _summary(self, result_id: str, value: TIAAnalysis) -> dict[str, Any]:
        return {
            "analysis_id": value.analysis_id,
            "project_name": value.project_name,
            "fragment_count": len(value.fragments),
            "net_delay": value.net_delay,
            "total_owner_delay": value.total_owner_delay,
            "total_contractor_delay": value.total_contractor_delay,
        }


class EVMStore(OwnedResultStore[EVMAnalysisResult]):
    """Owned in-memory storage for EVM analyses (ids ``evm-<hex>``)."""

    prefix = "evm"

    def _stamp(self, value: EVMAnalysisResult, result_id: str) -> None:
        value.analysis_id = result_id

    def _summary(self, result_id: str, value: EVMAnalysisResult) -> dict[str, Any]:
        return {
            "analysis_id": value.analysis_id,
            "project_name": value.project_name,
            "project_id": value.project_id,
            "bac": value.metrics.bac,
            "pv": round(value.metrics.pv, 2),
            "ev": round(value.metrics.ev, 2),
            "ac": round(value.metrics.ac, 2),
            "eac": round(value.metrics.eac_cpi, 2),
            "spi": round(value.metrics.spi, 3),
            "cpi": round(value.metrics.cpi, 3),
            "schedule_health": value.schedule_health.status,
            "cost_health": value.cost_health.status,
        }


class RiskStore(OwnedResultStore[SimulationResult]):
    """Owned in-memory storage for Monte Carlo results (ids ``risk-<hex>``).

    Also keeps the ``job_id -> simulation_id`` index used by the WebSocket
    recovery poller; a lookup answers only for the simulation's owner.
    """

    prefix = "risk"

    def __init__(self) -> None:
        """Initialise an empty store and job index."""
        super().__init__()
        self._jobs: dict[str, str] = {}

    def _stamp(self, value: SimulationResult, result_id: str) -> None:
        value.simulation_id = result_id

    def _summary(self, result_id: str, value: SimulationResult) -> dict[str, Any]:
        p50 = 0.0
        p80 = 0.0
        for pv in value.p_values:
            if pv.percentile == 50:
                p50 = pv.duration_days
            if pv.percentile == 80:
                p80 = pv.duration_days
        return {
            "simulation_id": value.simulation_id,
            "project_name": value.project_name,
            "project_id": value.project_id,
            "iterations": value.iterations,
            "deterministic_days": value.deterministic_days,
            "mean_days": value.mean_days,
            "p50_days": p50,
            "p80_days": p80,
        }

    def _forget(self, result_ids: builtins.list[str]) -> None:
        gone = set(result_ids)
        for job_id in [j for j, sid in self._jobs.items() if sid in gone]:
            del self._jobs[job_id]

    def bind_job(self, job_id: str, simulation_id: str) -> None:
        """Index a completed simulation by its progress channel job_id.

        Per ADR-0019 §"W1 — D4". Enables
        ``GET /api/v1/risk/simulations/by-job/{job_id}`` lookups for the
        WebSocket recovery poller. Last bind wins.

        **Atomicity caveat:** ``add()`` and ``bind_job()`` are each
        thread-safe but the pair is not jointly atomic. A poller that
        looks the job up between the two calls sees ``None`` and simply
        polls again (5s default cadence).

        Args:
            job_id: Progress channel id from ``POST /jobs/progress/start``.
            simulation_id: Identifier returned by ``add()``.
        """
        with self._lock:
            self._jobs[job_id] = simulation_id

    def get_simulation_id_by_job(self, job_id: str, *, owner_id: str) -> str | None:
        """Return the simulation id bound to ``job_id`` if ``owner_id`` owns it.

        Used by the frontend ``recoveryPoller`` to learn whether a
        simulation completed after a transient WebSocket disconnect.

        Returns:
            The bound simulation_id, or ``None`` when nothing is bound yet
            (still running, never started, store cleared) or when the bound
            simulation belongs to someone else.
        """
        with self._lock:
            sid = self._jobs.get(job_id)
            entry = self._entries.get(sid) if sid else None
        if entry is None or entry.owner_id != owner_id:
            return None
        return sid

    def clear(self) -> None:
        """Remove all stored simulations and the job index."""
        super().clear()
        with self._lock:
            self._jobs.clear()


class ReportStore(OwnedResultStore[dict[str, Any]]):
    """Owned in-memory storage for generated reports (ids ``report-<hex>``).

    Each value is ``{"bytes": <pdf or html>, **metadata}``. At most
    :data:`REPORTS_PER_OWNER` reports are kept per owner; that owner's
    oldest are evicted first.

    Usage::

        store = ReportStore()
        rid = store.add(
            {"bytes": pdf, "report_type": "health", "project_id": pid},
            owner_id=user_id,
            project_ids=[pid],
        )
        report = store.get(rid, owner_id=user_id)
    """

    prefix = "report"
    max_per_owner = REPORTS_PER_OWNER

    def _summary(self, result_id: str, value: dict[str, Any]) -> dict[str, Any]:
        return {
            "report_id": result_id,
            "report_type": value.get("report_type", "unknown"),
            "project_id": value.get("project_id", "unknown"),
            "generated_at": value.get("generated_at", ""),
            "size_bytes": len(value.get("bytes", b"")),
        }
