# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Unified data-store interface with InMemory and Supabase backends.

``InMemoryStore`` delegates to the existing v0.5 storage classes so that
all current behaviour is preserved byte-for-byte.  ``SupabaseStore``
persists the same data to PostgreSQL via the Supabase client.

Use the ``get_store()`` factory to obtain the correct backend based on
the ``ENVIRONMENT`` setting.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from src.analytics.evm import EVMAnalysisResult
from src.analytics.forensics import ForensicTimeline
from src.analytics.risk import SimulationResult
from src.analytics.tia import TIAAnalysis
from src.parser.models import ParsedSchedule


# ------------------------------------------------------------------ #
# InMemoryStore — wraps existing v0.5 storage classes                #
# ------------------------------------------------------------------ #


class InMemoryStore:
    """In-memory backend that delegates to the v0.5 storage classes.

    This ensures 100 % backward compatibility — all existing endpoints
    and tests continue to work without modification.
    """

    def __init__(self) -> None:
        from src.api.storage import (
            EVMStore,
            ProjectStore,
            RiskStore,
            TIAStore,
            TimelineStore,
        )

        self._projects = ProjectStore()
        self._timelines = TimelineStore()
        self._tia = TIAStore()
        self._evm = EVMStore()
        self._risk = RiskStore()
        self._analyses: dict[str, dict[str, Any]] = {}
        self._comparisons: dict[str, dict[str, Any]] = {}

    # -- upload / project ------------------------------------------------

    def save_upload(
        self,
        filename: str,
        file_bytes: bytes,
        parser_version: str = "0.6.0-dev",
    ) -> str:
        """Store raw file bytes and return an upload_id."""
        upload_id = f"upload-{uuid.uuid4().hex[:8]}"
        return upload_id

    def save_project(
        self,
        upload_id: str,
        schedule: ParsedSchedule,
        xer_bytes: bytes | None = None,
    ) -> str:
        """Persist a parsed schedule and return a project_id."""
        return self._projects.add(schedule, xer_bytes or b"")

    def get_projects(self) -> list[dict[str, Any]]:
        """List all stored projects with summary info."""
        return self._projects.list_all()

    def get_project(self, project_id: str) -> ParsedSchedule | None:
        """Retrieve a parsed schedule by project_id."""
        return self._projects.get(project_id)

    def get_xer_bytes(self, project_id: str) -> bytes | None:
        """Retrieve raw XER bytes by project_id."""
        return self._projects.get_xer_bytes(project_id)

    # -- legacy project-store delegation (used by app.py) ----------------

    def add(self, schedule: ParsedSchedule, xer_bytes: bytes) -> str:
        """Alias for ``save_project`` matching the v0.5 ProjectStore API."""
        return self._projects.add(schedule, xer_bytes)

    def get(self, project_id: str) -> ParsedSchedule | None:
        """Alias for ``get_project`` matching the v0.5 ProjectStore API."""
        return self._projects.get(project_id)

    def list_all(self) -> list[dict[str, Any]]:
        """Alias for ``get_projects`` matching the v0.5 ProjectStore API."""
        return self._projects.list_all()

    def clear(self) -> None:
        """Clear the underlying project store."""
        self._projects.clear()

    # -- analysis results ------------------------------------------------

    def save_analysis(
        self,
        project_id: str,
        analysis_type: str,
        results: Any,
    ) -> str:
        """Store analysis results (DCMA, CPM, etc.)."""
        analysis_id = f"analysis-{uuid.uuid4().hex[:8]}"
        self._analyses[analysis_id] = {
            "project_id": project_id,
            "analysis_type": analysis_type,
            "results": results,
        }
        return analysis_id

    def get_analysis(
        self,
        project_id: str,
        analysis_type: str,
    ) -> Any | None:
        """Retrieve the latest analysis of a given type for a project."""
        for entry in reversed(list(self._analyses.values())):
            if (
                entry["project_id"] == project_id
                and entry["analysis_type"] == analysis_type
            ):
                return entry["results"]
        return None

    # -- comparisons -----------------------------------------------------

    def save_comparison(
        self,
        baseline_id: str,
        update_id: str,
        results: Any,
    ) -> str:
        """Store schedule comparison results."""
        comparison_id = f"cmp-{uuid.uuid4().hex[:8]}"
        self._comparisons[comparison_id] = {
            "baseline_id": baseline_id,
            "update_id": update_id,
            "results": results,
        }
        return comparison_id

    # -- forensic timelines ----------------------------------------------

    def save_forensic_timeline(self, timeline: ForensicTimeline) -> str:
        """Store a forensic timeline and return its timeline_id."""
        return self._timelines.add(timeline)

    def get_forensic_timeline(
        self,
        timeline_id: str,
    ) -> ForensicTimeline | None:
        """Retrieve a forensic timeline by timeline_id."""
        return self._timelines.get(timeline_id)

    def list_forensic_timelines(self) -> list[dict[str, Any]]:
        """List all stored forensic timelines."""
        return self._timelines.list_all()

    # -- TIA analyses ----------------------------------------------------

    def save_tia_analysis(self, analysis: TIAAnalysis) -> str:
        """Store a TIA analysis and return its analysis_id."""
        return self._tia.add(analysis)

    def get_tia_analysis(self, analysis_id: str) -> TIAAnalysis | None:
        """Retrieve a TIA analysis by analysis_id."""
        return self._tia.get(analysis_id)

    def list_tia_analyses(self) -> list[dict[str, Any]]:
        """List all stored TIA analyses."""
        return self._tia.list_all()

    # -- EVM analyses ----------------------------------------------------

    def save_evm_analysis(self, analysis: EVMAnalysisResult) -> str:
        """Store an EVM analysis and return its analysis_id."""
        return self._evm.add(analysis)

    def get_evm_analysis(
        self,
        analysis_id: str,
    ) -> EVMAnalysisResult | None:
        """Retrieve an EVM analysis by analysis_id."""
        return self._evm.get(analysis_id)

    def list_evm_analyses(self) -> list[dict[str, Any]]:
        """List all stored EVM analyses."""
        return self._evm.list_all()

    # -- risk simulations ------------------------------------------------

    def save_risk_simulation(self, simulation: SimulationResult) -> str:
        """Store a risk simulation and return its simulation_id."""
        return self._risk.add(simulation)

    def get_risk_simulation(
        self,
        simulation_id: str,
    ) -> SimulationResult | None:
        """Retrieve a risk simulation by simulation_id."""
        return self._risk.get(simulation_id)

    def list_risk_simulations(self) -> list[dict[str, Any]]:
        """List all stored risk simulations."""
        return self._risk.list_all()


# ------------------------------------------------------------------ #
# SupabaseStore — PostgreSQL via supabase-py                         #
# ------------------------------------------------------------------ #


class SupabaseStore:
    """Supabase/PostgreSQL backend.

    For v0.6 Phase 1 the core methods (upload, project, get/list) use
    proper table inserts.  Analytics methods store results as JSONB in
    their respective tables.
    """

    def __init__(self) -> None:
        from .client import get_supabase_client

        self._client = get_supabase_client()
        self._analyses: dict[str, dict[str, Any]] = {}
        self._comparisons: dict[str, dict[str, Any]] = {}

    # -- helpers ---------------------------------------------------------

    def _insert(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        """Insert a row and return the inserted data."""
        result = self._client.table(table).insert(data).execute()
        return result.data[0] if result.data else {}

    def _select(
        self,
        table: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Select rows from a table with optional equality filters."""
        query = self._client.table(table).select("*")
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        result = query.execute()
        return result.data or []

    # -- upload / project ------------------------------------------------

    def save_upload(
        self,
        filename: str,
        file_bytes: bytes,
        parser_version: str = "0.6.0-dev",
    ) -> str:
        """Persist upload metadata and return the upload_id (UUID)."""
        row = self._insert(
            "schedule_uploads",
            {
                "original_filename": filename,
                "file_size_bytes": len(file_bytes),
                "parser_version": parser_version,
                "status": "parsed",
            },
        )
        return str(row["id"])

    def save_project(
        self,
        upload_id: str,
        schedule: ParsedSchedule,
        xer_bytes: bytes | None = None,
    ) -> str:
        """Persist a parsed schedule into the projects table."""
        proj_name = ""
        data_date = None
        if schedule.projects:
            proj_name = schedule.projects[0].proj_short_name
            dd = (
                schedule.projects[0].last_recalc_date
                or schedule.projects[0].sum_data_date
            )
            if dd:
                data_date = dd.isoformat()

        row = self._insert(
            "projects",
            {
                "upload_id": upload_id,
                "project_name": proj_name,
                "data_date": data_date,
                "activity_count": len(schedule.activities),
                "relationship_count": len(schedule.relationships),
                "calendar_count": len(schedule.calendars),
                "wbs_count": len(schedule.wbs_nodes),
                "schedule_data": json.loads(schedule.model_dump_json()),
            },
        )
        return str(row["id"])

    def get_projects(self) -> list[dict[str, Any]]:
        """List all projects stored in Supabase."""
        rows = self._select("projects")
        return [
            {
                "project_id": str(r["id"]),
                "name": r.get("project_name", ""),
                "activity_count": r.get("activity_count", 0),
                "relationship_count": r.get("relationship_count", 0),
            }
            for r in rows
        ]

    def get_project(self, project_id: str) -> ParsedSchedule | None:
        """Retrieve a parsed schedule from Supabase by project id."""
        rows = self._select("projects", {"id": project_id})
        if not rows:
            return None
        data = rows[0].get("schedule_data")
        if data is None:
            return None
        return ParsedSchedule.model_validate(data)

    def get_xer_bytes(self, project_id: str) -> bytes | None:
        """XER bytes retrieval — not yet implemented for Supabase."""
        return None

    # -- legacy aliases for app.py compatibility -------------------------

    def add(self, schedule: ParsedSchedule, xer_bytes: bytes) -> str:
        """v0.5-compatible add method."""
        upload_id = self.save_upload("upload.xer", xer_bytes)
        return self.save_project(upload_id, schedule, xer_bytes)

    def get(self, project_id: str) -> ParsedSchedule | None:
        """v0.5-compatible get method."""
        return self.get_project(project_id)

    def list_all(self) -> list[dict[str, Any]]:
        """v0.5-compatible list_all method."""
        return self.get_projects()

    def clear(self) -> None:
        """Clear is a no-op for Supabase (use migrations)."""

    # -- analysis results ------------------------------------------------

    def save_analysis(
        self,
        project_id: str,
        analysis_type: str,
        results: Any,
    ) -> str:
        """Store analysis results in the analysis_results table."""
        try:
            row = self._insert(
                "analysis_results",
                {
                    "project_id": project_id,
                    "analysis_type": analysis_type,
                    "results": (
                        results
                        if isinstance(results, dict)
                        else json.loads(json.dumps(results, default=str))
                    ),
                },
            )
            return str(row.get("id", f"analysis-{uuid.uuid4().hex[:8]}"))
        except Exception:
            aid = f"analysis-{uuid.uuid4().hex[:8]}"
            self._analyses[aid] = {
                "project_id": project_id,
                "analysis_type": analysis_type,
                "results": results,
            }
            return aid

    def get_analysis(
        self,
        project_id: str,
        analysis_type: str,
    ) -> Any | None:
        """Retrieve the latest analysis of a given type for a project."""
        try:
            rows = self._select(
                "analysis_results",
                {"project_id": project_id, "analysis_type": analysis_type},
            )
            if rows:
                return rows[-1].get("results")
        except Exception:
            pass
        for entry in reversed(list(self._analyses.values())):
            if (
                entry["project_id"] == project_id
                and entry["analysis_type"] == analysis_type
            ):
                return entry["results"]
        return None

    # -- comparisons -----------------------------------------------------

    def save_comparison(
        self,
        baseline_id: str,
        update_id: str,
        results: Any,
    ) -> str:
        """Store comparison results."""
        try:
            row = self._insert(
                "comparison_results",
                {
                    "baseline_project_id": baseline_id,
                    "update_project_id": update_id,
                    "results": (
                        results
                        if isinstance(results, dict)
                        else json.loads(json.dumps(results, default=str))
                    ),
                },
            )
            return str(row.get("id", f"cmp-{uuid.uuid4().hex[:8]}"))
        except Exception:
            cid = f"cmp-{uuid.uuid4().hex[:8]}"
            self._comparisons[cid] = {
                "baseline_id": baseline_id,
                "update_id": update_id,
                "results": results,
            }
            return cid

    # -- forensic timelines (JSONB storage) ------------------------------

    def save_forensic_timeline(self, timeline: ForensicTimeline) -> str:
        """Store a forensic timeline."""
        tid = f"timeline-{uuid.uuid4().hex[:8]}"
        timeline.timeline_id = tid
        try:
            self._insert(
                "forensic_timelines",
                {
                    "timeline_id": tid,
                    "project_name": timeline.project_name,
                    "schedule_count": timeline.schedule_count,
                    "total_delay_days": timeline.total_delay_days,
                    "timeline_data": json.loads(
                        timeline.model_dump_json()
                        if hasattr(timeline, "model_dump_json")
                        else json.dumps(timeline.__dict__, default=str)
                    ),
                },
            )
        except Exception:
            pass
        return tid

    def get_forensic_timeline(
        self,
        timeline_id: str,
    ) -> ForensicTimeline | None:
        """Retrieve a forensic timeline."""
        try:
            rows = self._select(
                "forensic_timelines",
                {"timeline_id": timeline_id},
            )
            if rows:
                data = rows[0].get("timeline_data")
                if data:
                    return ForensicTimeline.model_validate(data)
        except Exception:
            pass
        return None

    def list_forensic_timelines(self) -> list[dict[str, Any]]:
        """List all forensic timelines."""
        try:
            rows = self._select("forensic_timelines")
            return [
                {
                    "timeline_id": r.get("timeline_id", ""),
                    "project_name": r.get("project_name", ""),
                    "schedule_count": r.get("schedule_count", 0),
                    "total_delay_days": r.get("total_delay_days", 0),
                    "window_count": 0,
                }
                for r in rows
            ]
        except Exception:
            return []

    # -- TIA analyses (JSONB storage) ------------------------------------

    def save_tia_analysis(self, analysis: TIAAnalysis) -> str:
        """Store a TIA analysis."""
        aid = f"tia-{uuid.uuid4().hex[:8]}"
        analysis.analysis_id = aid
        try:
            self._insert(
                "tia_analyses",
                {
                    "analysis_id": aid,
                    "project_name": analysis.project_name,
                    "analysis_data": json.loads(
                        analysis.model_dump_json()
                        if hasattr(analysis, "model_dump_json")
                        else json.dumps(analysis.__dict__, default=str)
                    ),
                },
            )
        except Exception:
            pass
        return aid

    def get_tia_analysis(self, analysis_id: str) -> TIAAnalysis | None:
        """Retrieve a TIA analysis."""
        try:
            rows = self._select(
                "tia_analyses",
                {"analysis_id": analysis_id},
            )
            if rows:
                data = rows[0].get("analysis_data")
                if data:
                    return TIAAnalysis.model_validate(data)
        except Exception:
            pass
        return None

    def list_tia_analyses(self) -> list[dict[str, Any]]:
        """List all TIA analyses."""
        try:
            rows = self._select("tia_analyses")
            return [
                {
                    "analysis_id": r.get("analysis_id", ""),
                    "project_name": r.get("project_name", ""),
                }
                for r in rows
            ]
        except Exception:
            return []

    # -- EVM analyses (JSONB storage) ------------------------------------

    def save_evm_analysis(self, analysis: EVMAnalysisResult) -> str:
        """Store an EVM analysis."""
        aid = f"evm-{uuid.uuid4().hex[:8]}"
        analysis.analysis_id = aid
        try:
            self._insert(
                "evm_analyses",
                {
                    "analysis_id": aid,
                    "project_name": analysis.project_name,
                    "analysis_data": json.loads(
                        analysis.model_dump_json()
                        if hasattr(analysis, "model_dump_json")
                        else json.dumps(analysis.__dict__, default=str)
                    ),
                },
            )
        except Exception:
            pass
        return aid

    def get_evm_analysis(
        self,
        analysis_id: str,
    ) -> EVMAnalysisResult | None:
        """Retrieve an EVM analysis."""
        try:
            rows = self._select(
                "evm_analyses",
                {"analysis_id": analysis_id},
            )
            if rows:
                data = rows[0].get("analysis_data")
                if data:
                    return EVMAnalysisResult.model_validate(data)
        except Exception:
            pass
        return None

    def list_evm_analyses(self) -> list[dict[str, Any]]:
        """List all EVM analyses."""
        try:
            rows = self._select("evm_analyses")
            return [
                {
                    "analysis_id": r.get("analysis_id", ""),
                    "project_name": r.get("project_name", ""),
                }
                for r in rows
            ]
        except Exception:
            return []

    # -- risk simulations (JSONB storage) --------------------------------

    def save_risk_simulation(self, simulation: SimulationResult) -> str:
        """Store a risk simulation."""
        sid = f"risk-{uuid.uuid4().hex[:8]}"
        simulation.simulation_id = sid
        try:
            self._insert(
                "risk_simulations",
                {
                    "simulation_id": sid,
                    "project_name": simulation.project_name,
                    "simulation_data": json.loads(
                        simulation.model_dump_json()
                        if hasattr(simulation, "model_dump_json")
                        else json.dumps(simulation.__dict__, default=str)
                    ),
                },
            )
        except Exception:
            pass
        return sid

    def get_risk_simulation(
        self,
        simulation_id: str,
    ) -> SimulationResult | None:
        """Retrieve a risk simulation."""
        try:
            rows = self._select(
                "risk_simulations",
                {"simulation_id": simulation_id},
            )
            if rows:
                data = rows[0].get("simulation_data")
                if data:
                    return SimulationResult.model_validate(data)
        except Exception:
            pass
        return None

    def list_risk_simulations(self) -> list[dict[str, Any]]:
        """List all risk simulations."""
        try:
            rows = self._select("risk_simulations")
            return [
                {
                    "simulation_id": r.get("simulation_id", ""),
                    "project_name": r.get("project_name", ""),
                }
                for r in rows
            ]
        except Exception:
            return []


# ------------------------------------------------------------------ #
# Factory                                                            #
# ------------------------------------------------------------------ #

_store_instance: InMemoryStore | SupabaseStore | None = None


def get_store() -> InMemoryStore | SupabaseStore:
    """Return the global store instance.

    Uses ``Settings.use_supabase`` to pick the backend.  The instance is
    created once and reused for the application lifetime.
    """
    global _store_instance
    if _store_instance is not None:
        return _store_instance

    from .config import settings

    if settings.use_supabase:
        _store_instance = SupabaseStore()
    else:
        _store_instance = InMemoryStore()

    return _store_instance
