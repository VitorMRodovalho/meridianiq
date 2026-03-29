# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Unified data-store interface with InMemory and Supabase backends.

``InMemoryStore`` delegates to the existing v0.5 storage classes so that
all current behaviour is preserved byte-for-byte.  ``SupabaseStore``
persists XER files to Supabase Storage and metadata to PostgreSQL —
no large JSONB blobs.

Use the ``get_store()`` factory to obtain the correct backend based on
the ``ENVIRONMENT`` setting.
"""

from __future__ import annotations

import json
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any

from src.analytics.evm import EVMAnalysisResult
from src.analytics.forensics import ForensicTimeline
from src.analytics.risk import SimulationResult
from src.analytics.tia import TIAAnalysis
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


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
        self._project_owners: dict[str, str] = {}  # project_id -> user_id
        # Programs model
        self._programs: dict[str, dict[str, Any]] = {}  # program_id -> program data
        self._program_counter: int = 0
        self._upload_program: dict[str, str] = {}  # project_id -> program_id
        self._upload_revision: dict[str, int] = {}  # project_id -> revision_number

    # -- programs --------------------------------------------------------

    def get_or_create_program(self, user_id: str, project_name: str) -> str:
        """Find or create a program by name+user_id. Returns program_id."""
        for prog_id, prog in self._programs.items():
            if prog["user_id"] == user_id and prog["name"] == project_name:
                return prog_id
        self._program_counter += 1
        prog_id = f"prog-{self._program_counter:04d}"
        self._programs[prog_id] = {
            "id": prog_id,
            "user_id": user_id,
            "name": project_name,
            "description": "",
            "proj_short_name": project_name,
            "created_at": None,
            "updated_at": None,
        }
        return prog_id

    def get_next_revision_number(self, program_id: str) -> int:
        """Return the next revision number for a program."""
        max_rev = 0
        for pid, prog_id in self._upload_program.items():
            if prog_id == program_id:
                rev = self._upload_revision.get(pid, 0)
                if rev > max_rev:
                    max_rev = rev
        return max_rev + 1

    def get_programs(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """Get all programs for a user with latest revision info."""
        results = []
        for prog_id, prog in self._programs.items():
            if user_id and prog["user_id"] != user_id:
                continue
            # Find all uploads for this program
            upload_pids = [pid for pid, p_id in self._upload_program.items() if p_id == prog_id]
            # Find latest revision
            latest = None
            max_rev = 0
            for pid in upload_pids:
                rev = self._upload_revision.get(pid, 0)
                if rev >= max_rev:
                    max_rev = rev
                    schedule = self._projects.get(pid)
                    if schedule:
                        name = ""
                        if schedule.projects:
                            name = schedule.projects[0].proj_short_name
                        latest = {
                            "id": pid,
                            "filename": f"{name}.xer",
                            "data_date": None,
                            "uploaded_at": None,
                            "revision_number": rev,
                            "activity_count": len(schedule.activities),
                        }
            enriched = {**prog, "latest_revision": latest, "revision_count": len(upload_pids)}
            results.append(enriched)
        return results

    def get_program_revisions(
        self, program_id: str, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return all revisions (uploads) for a given program."""
        if program_id not in self._programs:
            return []
        prog = self._programs[program_id]
        if user_id and prog["user_id"] != user_id:
            return []
        revisions = []
        for pid, p_id in self._upload_program.items():
            if p_id != program_id:
                continue
            schedule = self._projects.get(pid)
            if schedule is None:
                continue
            name = ""
            if schedule.projects:
                name = schedule.projects[0].proj_short_name
            revisions.append(
                {
                    "id": pid,
                    "filename": f"{name}.xer",
                    "data_date": None,
                    "uploaded_at": None,
                    "revision_number": self._upload_revision.get(pid, 0),
                    "activity_count": len(schedule.activities),
                }
            )
        revisions.sort(key=lambda r: r["revision_number"], reverse=True)
        return revisions

    def update_program(
        self, program_id: str, updates: dict[str, Any], user_id: str | None = None
    ) -> dict[str, Any] | None:
        """Update program metadata (e.g. rename). Returns updated program or None."""
        if program_id not in self._programs:
            return None
        prog = self._programs[program_id]
        if user_id and prog["user_id"] != user_id:
            return None
        if "name" in updates:
            prog["name"] = updates["name"]
        if "description" in updates:
            prog["description"] = updates["description"]
        return prog

    # -- upload / project ------------------------------------------------

    def save_upload(
        self,
        filename: str,
        file_bytes: bytes,
        parser_version: str = "0.6.0-dev",
        user_id: str | None = None,
    ) -> str:
        """Store raw file bytes and return an upload_id."""
        upload_id = f"upload-{uuid.uuid4().hex[:8]}"
        return upload_id

    def save_project(
        self,
        upload_id: str,
        schedule: ParsedSchedule,
        xer_bytes: bytes | None = None,
        user_id: str | None = None,
    ) -> str:
        """Persist a parsed schedule and return a project_id."""
        pid = self._projects.add(schedule, xer_bytes or b"")
        if user_id:
            self._project_owners[pid] = user_id
        # Auto-assign program
        proj_name = ""
        if schedule.projects:
            proj_name = schedule.projects[0].proj_short_name
        if proj_name and user_id:
            program_id = self.get_or_create_program(user_id, proj_name)
            rev = self.get_next_revision_number(program_id)
            self._upload_program[pid] = program_id
            self._upload_revision[pid] = rev
        return pid

    def get_projects(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """List all stored projects with summary info, optionally filtered by user."""
        items = self._projects.list_all()
        if user_id:
            owned_pids = {pid for pid, uid in self._project_owners.items() if uid == user_id}
            unowned_pids = {
                pid for pid in self._projects.list_ids() if pid not in self._project_owners
            }
            allowed = owned_pids | unowned_pids
            items = [i for i in items if i["project_id"] in allowed]
        return items

    def get_project(self, project_id: str, user_id: str | None = None) -> ParsedSchedule | None:
        """Retrieve a parsed schedule by project_id."""
        if user_id and project_id in self._project_owners:
            if self._project_owners[project_id] != user_id:
                return None
        return self._projects.get(project_id)

    def get_parsed_schedule(self, project_id: str) -> ParsedSchedule | None:
        """Return the stored ParsedSchedule directly (no re-parse needed in memory)."""
        return self._projects.get(project_id)

    def get_xer_bytes(self, project_id: str) -> bytes | None:
        """Retrieve raw XER bytes by project_id."""
        return self._projects.get_xer_bytes(project_id)

    # -- legacy project-store delegation (used by app.py) ----------------

    def add(self, schedule: ParsedSchedule, xer_bytes: bytes, user_id: str | None = None) -> str:
        """Alias for ``save_project`` matching the v0.5 ProjectStore API."""
        pid = self._projects.add(schedule, xer_bytes)
        if user_id:
            self._project_owners[pid] = user_id
        # Auto-assign program
        proj_name = ""
        if schedule.projects:
            proj_name = schedule.projects[0].proj_short_name
        if proj_name and user_id:
            program_id = self.get_or_create_program(user_id, proj_name)
            rev = self.get_next_revision_number(program_id)
            self._upload_program[pid] = program_id
            self._upload_revision[pid] = rev
        return pid

    def get(self, project_id: str, user_id: str | None = None) -> ParsedSchedule | None:
        """Alias for ``get_project`` matching the v0.5 ProjectStore API."""
        return self.get_project(project_id, user_id=user_id)

    def list_all(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """Alias for ``get_projects`` matching the v0.5 ProjectStore API."""
        return self.get_projects(user_id=user_id)

    def list_ids(self) -> list[str]:
        """Delegate to underlying ProjectStore."""
        return self._projects.list_ids()

    def clear(self) -> None:
        """Clear the underlying project store."""
        self._projects.clear()
        self._project_owners.clear()
        self._programs.clear()
        self._program_counter = 0
        self._upload_program.clear()
        self._upload_revision.clear()

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
            if entry["project_id"] == project_id and entry["analysis_type"] == analysis_type:
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
# SupabaseStore — Storage bucket + PostgreSQL metadata               #
# ------------------------------------------------------------------ #


class SupabaseStore:
    """Supabase backend: XER files in Storage bucket, metadata in PostgreSQL.

    XER binary files are uploaded to the ``xer-files`` Storage bucket.
    Only lightweight metadata (project name, counts, storage path) is
    stored in the ``projects`` table — no large JSONB ``schedule_data``.

    When analysis endpoints need the full ``ParsedSchedule``, the XER is
    downloaded from the bucket and re-parsed on the fly.
    """

    BUCKET = "xer-files"

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
        columns: str = "*",
    ) -> list[dict[str, Any]]:
        """Select rows from a table with optional equality filters."""
        query = self._client.table(table).select(columns)
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
        user_id: str | None = None,
    ) -> str:
        """Persist upload metadata and return the upload_id (UUID)."""
        data: dict[str, Any] = {
            "original_filename": filename,
            "file_size_bytes": len(file_bytes),
            "parser_version": parser_version,
            "status": "parsed",
        }
        if user_id:
            data["user_id"] = user_id
        row = self._insert("schedule_uploads", data)
        return str(row["id"])

    def save_project(
        self,
        upload_id: str,
        schedule: ParsedSchedule,
        xer_bytes: bytes | None = None,
        user_id: str | None = None,
    ) -> str:
        """Persist metadata + upload XER to Storage bucket.  No JSONB blob."""
        proj_name = ""
        data_date = None
        if schedule.projects:
            proj_name = schedule.projects[0].proj_short_name
            dd = schedule.projects[0].last_recalc_date or schedule.projects[0].sum_data_date
            if dd:
                data_date = dd.isoformat()

        # Determine storage path
        user_folder = user_id or "anonymous"
        storage_path = f"{user_folder}/{upload_id}/{proj_name or 'schedule'}.xer"

        # Upload XER binary to Storage bucket
        if xer_bytes:
            try:
                self._client.storage.from_(self.BUCKET).upload(
                    path=storage_path,
                    file=xer_bytes,
                    file_options={"content-type": "application/octet-stream"},
                )
            except Exception as exc:
                logger.warning("Storage upload failed, continuing with metadata only: %s", exc)
                storage_path = ""

        # Auto-assign program and revision number
        program_id = None
        revision_number = None
        if proj_name and user_id:
            try:
                program_id = self.get_or_create_program(user_id, proj_name)
                revision_number = self.get_next_revision_number(program_id)
            except Exception as exc:
                logger.warning("Program assignment failed: %s", exc)

        # Insert metadata only — NO schedule_data JSONB
        data: dict[str, Any] = {
            "upload_id": upload_id,
            "project_name": proj_name,
            "data_date": data_date,
            "activity_count": len(schedule.activities),
            "relationship_count": len(schedule.relationships),
            "calendar_count": len(schedule.calendars),
            "wbs_count": len(schedule.wbs_nodes),
            "storage_path": storage_path,
        }
        if user_id:
            data["user_id"] = user_id
        if program_id:
            data["program_id"] = program_id
        if revision_number is not None:
            data["revision_number"] = revision_number
        row = self._insert("projects", data)
        return str(row["id"])

    def get_parsed_schedule(self, project_id: str) -> ParsedSchedule | None:
        """Download XER from bucket, re-parse, and return ParsedSchedule."""
        rows = self._select(
            "projects",
            {"id": project_id},
            columns="storage_path",
        )
        if not rows or not rows[0].get("storage_path"):
            return None

        storage_path = rows[0]["storage_path"]
        try:
            file_bytes = self._client.storage.from_(self.BUCKET).download(storage_path)
        except Exception as exc:
            logger.error("Failed to download XER from bucket: %s", exc)
            return None

        # Parse from bytes via temp file (XERReader requires a file path)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".xer", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = Path(tmp.name)

            from src.parser.xer_reader import XERReader

            return XERReader(tmp_path).parse()
        except Exception as exc:
            logger.error("Failed to re-parse XER from bucket: %s", exc)
            return None
        finally:
            if tmp_path:
                tmp_path.unlink(missing_ok=True)

    def get_projects(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """List all projects — metadata only (no re-parse)."""
        filters: dict[str, Any] | None = None
        if user_id:
            filters = {"user_id": user_id}
        rows = self._select(
            "projects",
            filters,
            columns="id,project_name,activity_count,relationship_count,storage_path",
        )
        return [
            {
                "project_id": str(r["id"]),
                "name": r.get("project_name", ""),
                "activity_count": r.get("activity_count", 0),
                "relationship_count": r.get("relationship_count", 0),
            }
            for r in rows
            # Guard: skip orphan rows where the XER file was never uploaded
            if r.get("storage_path")
        ]

    def get_project(self, project_id: str, user_id: str | None = None) -> ParsedSchedule | None:
        """Retrieve a parsed schedule by downloading XER from the bucket."""
        # Check ownership if user_id is provided
        if user_id:
            rows = self._select(
                "projects",
                {"id": project_id, "user_id": user_id},
                columns="id",
            )
            if not rows:
                return None
        return self.get_parsed_schedule(project_id)

    def get_xer_bytes(self, project_id: str) -> bytes | None:
        """Download raw XER bytes from the Storage bucket."""
        rows = self._select(
            "projects",
            {"id": project_id},
            columns="storage_path",
        )
        if not rows or not rows[0].get("storage_path"):
            return None
        try:
            return self._client.storage.from_(self.BUCKET).download(rows[0]["storage_path"])
        except Exception as exc:
            logger.error("Failed to download XER bytes: %s", exc)
            return None

    # -- programs --------------------------------------------------------

    def get_or_create_program(self, user_id: str, project_name: str) -> str:
        """Find or create program. Returns program_id."""
        result = (
            self._client.table("programs")
            .select("id")
            .eq("user_id", user_id)
            .eq("name", project_name)
            .execute()
        )
        if result.data:
            return result.data[0]["id"]
        new = (
            self._client.table("programs")
            .insert(
                {
                    "user_id": user_id,
                    "name": project_name,
                    "proj_short_name": project_name,
                }
            )
            .execute()
        )
        return new.data[0]["id"]

    def get_next_revision_number(self, program_id: str) -> int:
        """Return the next revision number for a program."""
        result = (
            self._client.table("schedule_uploads")
            .select("revision_number")
            .eq("program_id", program_id)
            .order("revision_number", desc=True)
            .limit(1)
            .execute()
        )
        if result.data and result.data[0].get("revision_number"):
            return result.data[0]["revision_number"] + 1
        return 1

    def get_programs(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """Get all programs for user with latest revision info."""
        query = self._client.table("programs").select("*").order("updated_at", desc=True)
        if user_id:
            query = query.eq("user_id", user_id)
        programs = query.execute()
        enriched = []
        for prog in programs.data:
            latest = (
                self._client.table("schedule_uploads")
                .select("id, filename, data_date, uploaded_at, revision_number, activity_count")
                .eq("program_id", prog["id"])
                .not_.is_("storage_path", "null")
                .order("revision_number", desc=True)
                .limit(1)
                .execute()
            )
            prog["latest_revision"] = latest.data[0] if latest.data else None
            prog["revision_count"] = len(
                self._client.table("schedule_uploads")
                .select("id")
                .eq("program_id", prog["id"])
                .not_.is_("storage_path", "null")
                .execute()
                .data
            )
            enriched.append(prog)
        return enriched

    def get_program_revisions(
        self, program_id: str, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return all revisions (uploads) for a given program."""
        query = self._client.table("programs").select("id").eq("id", program_id)
        if user_id:
            query = query.eq("user_id", user_id)
        prog = query.execute()
        if not prog.data:
            return []
        return (
            self._client.table("schedule_uploads")
            .select("id, filename, data_date, uploaded_at, revision_number, activity_count")
            .eq("program_id", program_id)
            .not_.is_("storage_path", "null")
            .order("revision_number", desc=True)
            .execute()
            .data
        )

    def update_program(
        self, program_id: str, updates: dict[str, Any], user_id: str | None = None
    ) -> dict[str, Any] | None:
        """Update program metadata (e.g. rename). Returns updated program or None."""
        query = self._client.table("programs").select("id").eq("id", program_id)
        if user_id:
            query = query.eq("user_id", user_id)
        prog = query.execute()
        if not prog.data:
            return None
        allowed = {}
        if "name" in updates:
            allowed["name"] = updates["name"]
        if "description" in updates:
            allowed["description"] = updates["description"]
        if not allowed:
            return prog.data[0]
        result = self._client.table("programs").update(allowed).eq("id", program_id).execute()
        return result.data[0] if result.data else None

    # -- legacy aliases for app.py compatibility -------------------------

    def add(self, schedule: ParsedSchedule, xer_bytes: bytes, user_id: str | None = None) -> str:
        """v0.5-compatible add method."""
        upload_id = self.save_upload("upload.xer", xer_bytes, user_id=user_id)
        return self.save_project(upload_id, schedule, xer_bytes, user_id=user_id)

    def get(self, project_id: str, user_id: str | None = None) -> ParsedSchedule | None:
        """v0.5-compatible get method."""
        return self.get_project(project_id, user_id=user_id)

    def list_all(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """v0.5-compatible list_all method."""
        return self.get_projects(user_id=user_id)

    def list_ids(self) -> list[str]:
        """List all project IDs from Supabase."""
        rows = self._select("projects", columns="id")
        return [str(r["id"]) for r in rows]

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
            if entry["project_id"] == project_id and entry["analysis_type"] == analysis_type:
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
