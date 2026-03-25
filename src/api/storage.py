# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""In-memory storage for parsed projects and forensic timelines (prototype v0.2).

Provides simple dictionary-based stores for parsed schedules, their raw
XER bytes, and forensic analysis timelines.  Designed as a placeholder
until a persistent database layer is introduced.
"""
from __future__ import annotations

import threading
from typing import Any

from src.analytics.forensics import ForensicTimeline
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
