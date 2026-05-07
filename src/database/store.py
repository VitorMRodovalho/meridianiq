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
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from src.analytics.evm import EVMAnalysisResult
from src.analytics.forensics import ForensicTimeline
from src.analytics.risk import SimulationResult
from src.analytics.tia import TIAAnalysis
from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)

# Re-materialization query cap (Cycle 3 W4 / issue #54). PostgREST's silent
# default of 1,000 rows would truncate without warning; raising past 10,000
# crosses into "data has scaled past the operator-script regime" territory
# and deserves a hard pagination strategy, not a single query.
RE_MAT_MAX_ROWS = 10_000


def _json_safe(obj: Any) -> Any:
    """Recursively convert datetime / date to ISO 8601 strings for JSON encoding.

    Engines in ``src/analytics/`` emit payloads containing Python ``datetime``
    objects (activity dates from the parser, computed timestamps). Supabase
    PostgREST uses httpx with the stdlib ``json`` encoder, which rejects
    datetime objects with ``TypeError: Object of type datetime is not JSON
    serializable``. Apply this helper at the store boundary so every engine
    payload + audit_details is JSON-safe without each engine needing to
    serialize defensively.
    """
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_json_safe(x) for x in obj]
    return obj


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
        # CBS cost uploads — per-project history of parsed cost data
        self._cost_uploads: dict[str, list[dict[str, Any]]] = {}
        self._cost_upload_counter: int = 0
        # Risk register entries — per-project risk inventory
        self._risk_entries: dict[str, list[dict[str, Any]]] = {}
        # Cycle 1 Wave 1 — derived-artifact materialization (ADR-0009 + ADR-0014)
        self._derived_artifacts: list[dict[str, Any]] = []
        self._derived_artifact_counter: int = 0
        # Shadow audit_log (in-memory mirror of supabase audit_log for tests)
        self._audit_log: list[dict[str, Any]] = []
        # Cycle 1 Wave 2 — projects.status state machine (ADR-0015).
        # Default 'ready' on save_project here because the InMemoryStore
        # represents the ADR-0015 sync-fast-path (under-threshold schedules
        # materialise inline). Real async behaviour lives in SupabaseStore.
        self._project_statuses: dict[str, str] = {}
        # Cycle 1 Wave 3 — lifecycle_phase lock flag + override log (ADR-0016)
        self._lifecycle_phase_locks: dict[str, bool] = {}
        self._lifecycle_overrides: list[dict[str, Any]] = []
        self._lifecycle_override_counter: int = 0

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
                            "status": self._project_statuses.get(pid, "ready"),
                        }
            enriched = {**prog, "latest_revision": latest, "revision_count": len(upload_pids)}
            results.append(enriched)
        return results

    def get_program_revisions(
        self, program_id: str, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return all revisions (uploads) for a given program.

        Each revision row carries the current ``status`` so reports / BI /
        programs UI can surface failed or pending revisions with an
        explicit marker (SCL §4 chain-of-custody; ADR-0015).
        """
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
                    "status": self._project_statuses.get(pid, "ready"),
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
        # ADR-0015 §2 state machine: InMemoryStore runs the sync-fast-path
        # by design (tests exercise deterministic synchronous behaviour),
        # so the initial status is 'ready'. Real async behaviour in
        # SupabaseStore starts at 'pending' and flips via the materializer.
        self._project_statuses[pid] = "ready"
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

    def set_project_status(self, project_id: str, status: str) -> bool:
        """Set ``projects.status`` to one of 'pending' / 'ready' / 'failed'.

        Returns True if the row exists, False otherwise. Used by the async
        materializer (ADR-0015) to flip 'pending' → 'ready' on success or
        → 'failed' on persist/materialize failure. InMemoryStore parity
        keeps MockSupabaseStore-driven tests honest.
        """
        if status not in {"pending", "ready", "failed"}:
            raise ValueError(
                f"invalid projects.status: {status!r}; must be one of 'pending', 'ready', 'failed'"
            )
        if project_id not in {pid for pid in self._projects.list_ids()}:
            return False
        self._project_statuses[project_id] = status
        return True

    def get_project_status(self, project_id: str) -> str | None:
        """Return the current ``projects.status`` or None if the row is missing.

        Added in ADR-0015 (Wave 2) as the read-side companion of
        ``set_project_status`` — upload responses and polling endpoints use
        this to expose the state machine to the UI without a full
        ``get_projects`` round trip.
        """
        if project_id not in {pid for pid in self._projects.list_ids()}:
            return None
        return self._project_statuses.get(project_id, "ready")

    def get_projects(
        self,
        user_id: str | None = None,
        include_all_statuses: bool = False,
    ) -> list[dict[str, Any]]:
        """List all stored projects with summary info.

        Args:
            user_id: restricts the list to the caller's own projects
                (and pre-ownership legacy rows). Owner-scope sees every
                status so the UI can render status badges (ADR-0015 §3).
            include_all_statuses: when True, non-owner list-all paths
                (``user_id=None``) also return rows whose status is
                'pending' or 'failed'. Reports / BI pass this flag to
                surface ``failed`` rows with an explicit marker per
                SCL §4 chain-of-custody.
        """
        items = self._projects.list_all()
        if user_id:
            owned_pids = {pid for pid, uid in self._project_owners.items() if uid == user_id}
            unowned_pids = {
                pid for pid in self._projects.list_ids() if pid not in self._project_owners
            }
            allowed = owned_pids | unowned_pids
            items = [i for i in items if i["project_id"] in allowed]
        out: list[dict[str, Any]] = []
        for item in items:
            pid = item["project_id"]
            status = self._project_statuses.get(pid, "ready")
            if not include_all_statuses and user_id is None and status != "ready":
                continue
            # Non-destructive copy — ``list_all()`` returns shared dicts.
            out.append({**item, "status": status})
        return out

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

    def list_all(
        self,
        user_id: str | None = None,
        include_all_statuses: bool = False,
    ) -> list[dict[str, Any]]:
        """Alias for ``get_projects`` matching the v0.5 ProjectStore API."""
        return self.get_projects(user_id=user_id, include_all_statuses=include_all_statuses)

    def list_ids(self) -> list[str]:
        """Delegate to underlying ProjectStore."""
        return self._projects.list_ids()

    def clear(self) -> None:
        """Clear the underlying project store."""
        self._projects.clear()
        self._project_owners.clear()
        self._programs.clear()
        self._program_counter = 0
        self._analyses.clear()
        self._comparisons.clear()
        self._upload_program.clear()
        self._upload_revision.clear()
        self._cost_uploads.clear()
        self._cost_upload_counter = 0
        self._risk_entries.clear()

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

    def invalidate_analysis(
        self,
        project_id: str,
        analysis_type_prefix: str | None = None,
    ) -> int:
        """Delete cached analysis rows for a project.

        Args:
            project_id: The project whose cache should be cleared.
            analysis_type_prefix: If given, only invalidate rows whose
                ``analysis_type`` starts with this string (e.g.
                ``"schedule_view:"`` clears every baseline variant).
                If ``None``, invalidates all analysis rows for the project.

        Returns:
            Number of cached rows deleted.
        """
        to_delete: list[str] = []
        for aid, entry in self._analyses.items():
            if entry["project_id"] != project_id:
                continue
            if analysis_type_prefix is not None and not entry["analysis_type"].startswith(
                analysis_type_prefix
            ):
                continue
            to_delete.append(aid)
        for aid in to_delete:
            del self._analyses[aid]
        return len(to_delete)

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

    # -- CBS cost uploads ------------------------------------------------

    def save_cost_upload(
        self,
        project_id: str,
        result: Any,
        user_id: str | None = None,
        source_name: str = "CBS Upload",
    ) -> str:
        """Persist a CBS parse result as a cost snapshot.

        Stores the full ``CostIntegrationResult`` in memory, keyed by
        project and an auto-incremented snapshot id. Supabase backend
        persists to ``cbs_elements`` / ``cost_snapshots`` / ``cbs_wbs_mappings``.

        Args:
            project_id: Target schedule project.
            result: ``CostIntegrationResult`` from ``parse_cbs_excel``.
            user_id: Optional owner (for RLS parity with Supabase).
            source_name: Human-readable source label.

        Returns:
            The snapshot_id.
        """
        self._cost_upload_counter += 1
        snapshot_id = f"cost-{self._cost_upload_counter:04d}"
        payload = {
            "snapshot_id": snapshot_id,
            "project_id": project_id,
            "user_id": user_id,
            "source_name": source_name,
            "budget_date": getattr(result, "budget_date", "") or "",
            "total_budget": float(getattr(result, "total_budget", 0.0) or 0.0),
            "total_contingency": float(getattr(result, "total_contingency", 0.0) or 0.0),
            "total_escalation": float(getattr(result, "total_escalation", 0.0) or 0.0),
            "program_total": float(getattr(result, "program_total", 0.0) or 0.0),
            "cbs_element_count": len(getattr(result, "cbs_elements", [])),
            "wbs_budget_count": len(getattr(result, "wbs_budgets", [])),
            "mapping_count": len(getattr(result, "cbs_wbs_mappings", [])),
            "insights": list(getattr(result, "insights", [])),
            "created_at": datetime.now(UTC).isoformat(),
            "_result": result,  # Keep full result for retrieval
        }
        self._cost_uploads.setdefault(project_id, []).append(payload)
        return snapshot_id

    def list_cost_snapshots(
        self, project_id: str, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """List cost snapshot summaries for a project, newest first."""
        uploads = self._cost_uploads.get(project_id, [])
        if user_id is not None:
            uploads = [u for u in uploads if u.get("user_id") in (None, user_id)]
        return [{k: v for k, v in u.items() if not k.startswith("_")} for u in reversed(uploads)]

    def get_cost_snapshot(
        self, project_id: str, snapshot_id: str, user_id: str | None = None
    ) -> Any | None:
        """Retrieve the full ``CostIntegrationResult`` for a snapshot."""
        for u in self._cost_uploads.get(project_id, []):
            if u["snapshot_id"] == snapshot_id:
                if user_id is not None and u.get("user_id") not in (None, user_id):
                    return None
                return u.get("_result")
        return None

    # -- Risk register --------------------------------------------------

    def save_risk_entry(
        self,
        project_id: str,
        entry: dict[str, Any],
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist a risk register entry for a project.

        Upserts by ``risk_id`` within the project — re-saving the same
        ``risk_id`` replaces the existing record. Returns the stored
        entry with owner/timestamps injected.

        Reference: PMI Practice Standard for Risk Management; ISO 31000.
        """
        entries = self._risk_entries.setdefault(project_id, [])
        risk_id = entry.get("risk_id") or ""
        if not risk_id:
            risk_id = f"R{len(entries) + 1:03d}"
            entry = {**entry, "risk_id": risk_id}

        payload = {
            **entry,
            "project_id": project_id,
            "user_id": user_id,
            "created_at": datetime.now(UTC).isoformat(),
        }

        for i, existing in enumerate(entries):
            if existing.get("risk_id") == risk_id:
                entries[i] = payload
                return payload

        entries.append(payload)
        return payload

    def list_risk_entries(
        self, project_id: str, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return all risk register entries for a project."""
        entries = self._risk_entries.get(project_id, [])
        if user_id is not None:
            entries = [e for e in entries if e.get("user_id") in (None, user_id)]
        return list(entries)

    def delete_risk_entry(self, project_id: str, risk_id: str, user_id: str | None = None) -> bool:
        """Remove a risk entry by ``risk_id``. Returns True when removed."""
        entries = self._risk_entries.get(project_id, [])
        for i, e in enumerate(entries):
            if e.get("risk_id") == risk_id:
                if user_id is not None and e.get("user_id") not in (None, user_id):
                    return False
                entries.pop(i)
                return True
        return False

    # -- derived artifacts (ADR-0009 Wave 1 + ADR-0014) ------------------

    _VALID_STALE_REASONS = frozenset(
        {"input_changed", "engine_upgraded", "ruleset_upgraded", "manual"}
    )
    _VALID_ARTIFACT_KINDS = frozenset(
        {
            "dcma",
            "health",
            "cpm",
            "float_trends",
            "lifecycle_health",
            "lifecycle_phase_inference",
        }
    )

    def save_derived_artifact(
        self,
        project_id: str,
        artifact_kind: str,
        payload: dict[str, Any],
        engine_version: str,
        ruleset_version: str,
        input_hash: str,
        effective_at: datetime,
        computed_by: str | None = None,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
        audit_details_extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Upsert a derived-artifact row and write the paired audit_log row.

        On conflict over the identity tuple
        ``(project_id, artifact_kind, engine_version, ruleset_version, input_hash)``,
        the existing row is refreshed: ``computed_at`` / ``computed_by`` /
        ``payload`` are overwritten and ``is_stale`` is cleared to False (with
        ``stale_reason`` cleared to None). This makes re-materialization after
        a stale-flip idempotently refresh the row.

        The paired ``audit_log`` row with ``action='materialize'`` is written
        on every call irrespective of conflict outcome — each materialization
        attempt is a separate auditable event per ADR-0014 (SCL Protocol 2nd
        ed §4 chain-of-custody). ``audit_details_extra`` merges additional
        keys into ``audit_log.details`` so back-of-house callers such as the
        backfill CLI can inject ``trigger='system_backfill_v2'`` and a
        stable ``backfill_id`` without coupling to this method's signature
        (ADR-0015 §6).

        Raises:
            ValueError: if ``artifact_kind`` is not one of the DB CHECK values.
        """
        if artifact_kind not in self._VALID_ARTIFACT_KINDS:
            raise ValueError(
                f"invalid artifact_kind: {artifact_kind!r}; must be one of "
                f"{sorted(self._VALID_ARTIFACT_KINDS)}"
            )
        now = datetime.now(UTC)
        safe_payload = _json_safe(payload)
        for row in self._derived_artifacts:
            if (
                row["project_id"] == project_id
                and row["artifact_kind"] == artifact_kind
                and row["engine_version"] == engine_version
                and row["ruleset_version"] == ruleset_version
                and row["input_hash"] == input_hash
            ):
                row["payload"] = safe_payload
                row["effective_at"] = effective_at
                row["computed_at"] = now
                row["computed_by"] = computed_by
                row["is_stale"] = False
                row["stale_reason"] = None
                saved = row
                break
        else:
            self._derived_artifact_counter += 1
            saved = {
                "id": f"sda-{self._derived_artifact_counter:06d}",
                "project_id": project_id,
                "artifact_kind": artifact_kind,
                "payload": safe_payload,
                "engine_version": engine_version,
                "ruleset_version": ruleset_version,
                "input_hash": input_hash,
                "effective_at": effective_at,
                "computed_at": now,
                "computed_by": computed_by,
                "is_stale": False,
                "stale_reason": None,
            }
            self._derived_artifacts.append(saved)

        audit_details: dict[str, Any] = {
            "artifact_kind": artifact_kind,
            "artifact_id": saved["id"],
            "engine_version": engine_version,
            "ruleset_version": ruleset_version,
            "input_hash": input_hash,
        }
        if audit_details_extra:
            audit_details.update(_json_safe(audit_details_extra))
        self._audit_log.append(
            {
                "user_id": computed_by,
                "action": "materialize",
                "entity_type": "project",
                "entity_id": project_id,
                "details": audit_details,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "created_at": now,
            }
        )
        return saved

    def get_latest_derived_artifact(
        self,
        project_id: str,
        artifact_kind: str,
        current_engine_version: str,
        current_ruleset_version: str,
    ) -> dict[str, Any] | None:
        """Return the most recent non-stale artifact of the given kind for the project.

        Returns None when no non-stale artifact exists, when the latest stored
        ``engine_version`` differs from ``current_engine_version``, or when the
        latest stored ``ruleset_version`` differs from ``current_ruleset_version``.
        The version-mismatch path forces re-materialization under the current
        engine per ADR-0014.
        """
        candidates = [
            r
            for r in self._derived_artifacts
            if r["project_id"] == project_id
            and r["artifact_kind"] == artifact_kind
            and not r["is_stale"]
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda r: r["computed_at"], reverse=True)
        latest = candidates[0]
        if latest["engine_version"] != current_engine_version:
            return None
        if latest["ruleset_version"] != current_ruleset_version:
            return None
        return latest

    def get_projects_at_engine_version(
        self, engine_version: str, *, include_stale: bool = False
    ) -> list[str]:
        """Return distinct project IDs with at least one derived artifact at
        the given ``engine_version``.

        ``include_stale=False`` (default) — driver query for the re-mat
        workflow. Used by ``src/materializer/backfill.py
        --re-materialize-version <ver>`` to enumerate projects whose existing
        non-stale rows predate the current ``_ENGINE_VERSION``. Cycle 3 W4
        use case: 88 production rows at ``engine_version='4.0'`` after PR #50.

        ``include_stale=True`` — diagnostic query. When the re-mat CLI finds
        0 candidates at a non-current version, it re-queries with
        ``include_stale=True`` to detect "Option B (migration 027) already
        ran" — the tombstone scenario where rows exist but all are stale.
        Tells the operator their candidate-list is empty NOT because the
        re-mat already ran, but because the inputs were tombstoned.

        Sorted for deterministic batch ordering across runs.
        """
        pids: set[str] = set()
        for row in self._derived_artifacts:
            if row["engine_version"] != engine_version:
                continue
            if not include_stale and row["is_stale"]:
                continue
            pids.add(row["project_id"])
        return sorted(pids)

    def mark_stale(
        self,
        project_id: str,
        stale_reason: str = "input_changed",
    ) -> int:
        """Flip ``is_stale=True`` and set ``stale_reason`` on every artifact of a project.

        Returns the number of rows affected. Called from the upload happy-path
        alongside ``invalidate_namespace("schedule:kpis")``. Default reason is
        ``'input_changed'`` for the common upload case; callers pass explicit
        ``'engine_upgraded'`` / ``'ruleset_upgraded'`` / ``'manual'`` for
        targeted re-materialization workflows (AACE RP 114R determinism).
        """
        if stale_reason not in self._VALID_STALE_REASONS:
            raise ValueError(
                f"invalid stale_reason: {stale_reason!r}; must be one of {sorted(self._VALID_STALE_REASONS)}"
            )
        affected = 0
        for row in self._derived_artifacts:
            if row["project_id"] == project_id:
                row["is_stale"] = True
                row["stale_reason"] = stale_reason
                affected += 1
        return affected

    # -- lifecycle phase lock + override log (ADR-0016) -------------------

    def set_lifecycle_phase_lock(self, project_id: str, locked: bool) -> bool:
        """Flip ``projects.lifecycle_phase_locked``. Returns True if the row exists.

        Used by the API override / revert paths and by tests. Materializer
        consults :meth:`get_lifecycle_phase_lock` before running the
        ``lifecycle_phase_inference`` engine so a manual override sticks
        across subsequent uploads (Cost Engineer JTBD per ADR-0016).
        """
        if project_id not in {pid for pid in self._projects.list_ids()}:
            return False
        self._lifecycle_phase_locks[project_id] = bool(locked)
        return True

    def get_lifecycle_phase_lock(self, project_id: str) -> bool:
        """Return the lock flag (defaults to False for missing rows / pre-W3 rows)."""
        return bool(self._lifecycle_phase_locks.get(project_id, False))

    def save_lifecycle_override(
        self,
        project_id: str,
        override_phase: str,
        override_reason: str,
        *,
        inferred_phase: str | None = None,
        overridden_by: str | None = None,
        engine_version: str,
        ruleset_version: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Append a ``lifecycle_override_log`` row + flip the lock + audit_log.

        Per ADR-0016 §3 the override row is forensic — append only — and
        composes with the ``projects.lifecycle_phase_locked`` flag flipped
        in the same call so the materializer skips re-inference until the
        user explicitly reverts. The paired ``audit_log`` row uses
        ``action='lifecycle_override'`` (BR P1#8 council fix).

        Raises:
            ValueError: if the phase vocabulary or empty reason violate the
                contract enforced symmetrically in DB CHECK constraints.
        """
        from src.analytics.lifecycle_types import LIFECYCLE_PHASES

        if override_phase not in LIFECYCLE_PHASES:
            raise ValueError(
                f"invalid override_phase: {override_phase!r}; "
                f"must be one of {list(LIFECYCLE_PHASES)}"
            )
        if inferred_phase is not None and inferred_phase not in LIFECYCLE_PHASES:
            raise ValueError(
                f"invalid inferred_phase: {inferred_phase!r}; "
                f"must be one of {list(LIFECYCLE_PHASES)} or None"
            )
        if not override_reason or not override_reason.strip():
            raise ValueError("override_reason must be non-empty")

        now = datetime.now(UTC)
        self._lifecycle_override_counter += 1
        row: dict[str, Any] = {
            "id": f"lol-{self._lifecycle_override_counter:06d}",
            "project_id": project_id,
            "inferred_phase": inferred_phase,
            "override_phase": override_phase,
            "override_reason": override_reason,
            "overridden_by": overridden_by,
            "overridden_at": now,
            "engine_version": engine_version,
            "ruleset_version": ruleset_version,
        }
        self._lifecycle_overrides.append(row)
        # Flip the lock — same logical user action.
        self._lifecycle_phase_locks[project_id] = True
        # Audit trail (BR P1#8).
        self._audit_log.append(
            {
                "user_id": overridden_by,
                "action": "lifecycle_override",
                "entity_type": "project",
                "entity_id": project_id,
                "details": {
                    "override_id": row["id"],
                    "inferred_phase": inferred_phase,
                    "override_phase": override_phase,
                    "engine_version": engine_version,
                    "ruleset_version": ruleset_version,
                    "reason_length": len(override_reason),
                },
                "ip_address": ip_address,
                "user_agent": user_agent,
                "created_at": now,
            }
        )
        return row

    def list_lifecycle_overrides(self, project_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return overrides for a project ordered ``overridden_at DESC``."""
        rows = [r for r in self._lifecycle_overrides if r["project_id"] == project_id]
        rows.sort(key=lambda r: r["overridden_at"], reverse=True)
        return rows[: max(0, limit)]

    def get_latest_lifecycle_override(self, project_id: str) -> dict[str, Any] | None:
        """Return the most-recent override for a project or None."""
        rows = self.list_lifecycle_overrides(project_id, limit=1)
        return rows[0] if rows else None


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

    BATCH_SIZE = 500  # Max rows per insert to avoid payload limits

    def _insert(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        """Insert a row and return the inserted data."""
        result = self._client.table(table).insert(data).execute()
        return result.data[0] if result.data else {}

    def _batch_insert(self, table: str, rows: list[dict[str, Any]]) -> None:
        """Insert rows in chunks of BATCH_SIZE."""
        if not rows:
            return
        for i in range(0, len(rows), self.BATCH_SIZE):
            chunk = rows[i : i + self.BATCH_SIZE]
            self._client.table(table).insert(chunk).execute()

    def _delete(self, table: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Delete rows matching equality filters and return the deleted rows.

        PostgREST returns ``[]`` (no error) when RLS denies a DELETE or the row
        does not exist — callers that need to detect silent no-ops must inspect
        the returned list length.
        """
        query = self._client.table(table).delete()
        for col, val in filters.items():
            query = query.eq(col, val)
        result = query.execute()
        deleted: list[dict[str, Any]] = result.data or []
        return deleted

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

    def _select_all(
        self,
        table: str,
        project_id: str,
        columns: str = "*",
    ) -> list[dict[str, Any]]:
        """Select all rows for a project, paginating past Supabase 1000-row default."""
        all_rows: list[dict[str, Any]] = []
        offset = 0
        page_size = 1000
        while True:
            result = (
                self._client.table(table)
                .select(columns)
                .eq("project_id", project_id)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            batch = result.data or []
            all_rows.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return all_rows

    def _upsert(
        self,
        table: str,
        data: dict[str, Any],
        on_conflict: str,
    ) -> dict[str, Any]:
        """Upsert a row using the given ON CONFLICT target.

        ``on_conflict`` is a comma-separated list of column names matching a
        unique constraint (e.g. ``"project_id,artifact_kind,engine_version"``).
        Returns the upserted row. Added Wave 1 Cycle 1 v4.0 (ADR-0014).
        """
        result = self._client.table(table).upsert(data, on_conflict=on_conflict).execute()
        upserted: list[dict[str, Any]] = result.data or []
        return upserted[0] if upserted else {}

    def _update(
        self,
        table: str,
        data: dict[str, Any],
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Update rows matching equality filters. Returns the updated rows.

        PostgREST silently returns ``[]`` when RLS denies the UPDATE (same
        pattern as ``_delete`` in ADR-0012 amendment #2). Callers that need
        to detect silent no-ops inspect the returned list length.
        """
        query = self._client.table(table).update(data)
        for col, val in filters.items():
            query = query.eq(col, val)
        result = query.execute()
        updated: list[dict[str, Any]] = result.data or []
        return updated

    @staticmethod
    def _dt_iso(dt: datetime | None) -> str | None:
        """Convert datetime to ISO string for Supabase, or None."""
        return dt.isoformat() if dt else None

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

        # Insert metadata only — NO schedule_data JSONB. ``status='pending'``
        # reflects ADR-0015's async-materialization contract: the row exists
        # but its derived artifacts have not been computed yet. The async
        # materializer flips to 'ready' on completion or to 'failed' on
        # persist/materialize failure. Migration 024 and this assignment ship
        # in the same commit — a code edit without the migration references
        # a missing column; a migration without this edit would leave new
        # rows at DEFAULT 'ready' during the pending window.
        #
        # ``revision_date`` (Cycle 4 W1, ADR-0022) is the WALL-CLOCK at upload
        # time — distinct from ``data_date`` (the schedule effective date
        # sourced from XER ``proj.last_recalc_date``).  The two diverge by
        # months on stale-XER re-imports; W2 multi-rev-overlay uses
        # ``revision_date`` for upload-ordering and ``data_date`` for
        # x-axis chart positioning.  ALWAYS UTC ISO-8601 (matches the
        # ``TIMESTAMPTZ`` column shape in migration 028).
        data: dict[str, Any] = {
            "upload_id": upload_id,
            "project_name": proj_name,
            "data_date": data_date,
            "revision_date": datetime.now(UTC).isoformat(),
            "activity_count": len(schedule.activities),
            "relationship_count": len(schedule.relationships),
            "calendar_count": len(schedule.calendars),
            "wbs_count": len(schedule.wbs_nodes),
            "storage_path": storage_path,
            "status": "pending",
        }
        if user_id:
            data["user_id"] = user_id
        if program_id:
            data["program_id"] = program_id
        if revision_number is not None:
            data["revision_number"] = revision_number
        row = self._insert("projects", data)
        project_uuid = str(row["id"])

        # Persist full schedule data to relational tables. On failure the
        # compensating path (see ``_persist_schedule_data``) flips
        # ``status='failed'`` rather than deleting the row, preserving the
        # forensic audit trail and leaving the Storage XER blob reachable
        # for recovery/re-materialization.
        self._persist_schedule_data(project_uuid, schedule)

        return project_uuid

    # Child tables persisted by _persist_schedule_data. Kept as a class
    # attribute so the retry-idempotence pre-delete loop and any future
    # schema probes share a single source of truth.
    _PERSIST_CHILD_TABLES: tuple[str, ...] = (
        "wbs_elements",
        "activities",
        "predecessors",
        "calendars",
        "resources",
        "resource_assignments",
        "activity_code_types",
        "activity_codes",
        "task_activity_codes",
        "udf_types",
        "udf_values",
        "financial_periods",
        "task_financials",
    )

    def _persist_schedule_data(self, project_id: str, schedule: ParsedSchedule) -> None:
        """Batch-insert all parsed schedule entities into relational tables.

        Atomicity contract (ADR-0012 d→c, closed by ADR-0015): on any
        batch-insert failure, flip ``projects.status`` from ``'pending'`` to
        ``'failed'`` and re-raise the original exception so the caller
        observes an honest error. The ``projects`` row is retained (not
        deleted as in Wave 0) so the forensic audit trail survives and so
        the Storage XER blob remains reachable for re-materialization.

        Retry idempotence (council W2 P1#3): the child tables below do not
        enforce UNIQUE on ``(project_id, …)``; a naive re-run after a
        previous ``failed`` would leave both sets of partial rows visible
        to ``_reconstruct_from_db`` and CPM would trip. Before inserting we
        explicitly ``DELETE`` every child row scoped to this ``project_id``
        so the retry is deterministic. FK ``ON DELETE CASCADE`` on
        ``projects(id)`` continues to cover the whole-project teardown
        path; the per-child pre-delete here is the per-row-scoped sibling
        that keeps retries clean without requiring the projects row to be
        removed.
        """
        for table in self._PERSIST_CHILD_TABLES:
            try:
                self._delete(table, {"project_id": project_id})
            except Exception:
                # Pre-delete is best-effort. If it fails, the retry may
                # dupe — log and continue; the subsequent INSERT will
                # surface any uniqueness violation cleanly.
                logger.warning(
                    "Pre-insert cleanup of %s for project %s failed; "
                    "continuing with retry at risk of duplicate rows",
                    table,
                    project_id,
                )

        try:
            # WBS elements
            self._batch_insert(
                "wbs_elements",
                [
                    {
                        "project_id": project_id,
                        "wbs_id": w.wbs_id,
                        "parent_wbs_id": w.parent_wbs_id or None,
                        "wbs_short_name": w.wbs_short_name,
                        "wbs_name": w.wbs_name,
                        "seq_num": w.seq_num,
                        "proj_node_flag": w.proj_node_flag,
                    }
                    for w in schedule.wbs_nodes
                ],
            )

            # Activities — overflow fields go into extra_data JSONB
            self._batch_insert(
                "activities",
                [
                    {
                        "project_id": project_id,
                        "task_id": t.task_id,
                        "task_code": t.task_code,
                        "task_name": t.task_name,
                        "task_type": t.task_type,
                        "status_code": t.status_code,
                        "wbs_id": t.wbs_id,
                        "clndr_id": t.clndr_id,
                        "total_float_hr_cnt": t.total_float_hr_cnt,
                        "free_float_hr_cnt": t.free_float_hr_cnt,
                        "remain_drtn_hr_cnt": t.remain_drtn_hr_cnt,
                        "target_drtn_hr_cnt": t.target_drtn_hr_cnt,
                        "act_start_date": self._dt_iso(t.act_start_date),
                        "act_end_date": self._dt_iso(t.act_end_date),
                        "early_start_date": self._dt_iso(t.early_start_date),
                        "early_end_date": self._dt_iso(t.early_end_date),
                        "late_start_date": self._dt_iso(t.late_start_date),
                        "late_end_date": self._dt_iso(t.late_end_date),
                        "target_start_date": self._dt_iso(t.target_start_date),
                        "target_end_date": self._dt_iso(t.target_end_date),
                        "phys_complete_pct": t.phys_complete_pct,
                        "extra_data": {
                            "restart_date": self._dt_iso(t.restart_date),
                            "reend_date": self._dt_iso(t.reend_date),
                            "complete_pct_type": t.complete_pct_type,
                            "duration_type": t.duration_type,
                            "cstr_date": self._dt_iso(t.cstr_date),
                            "cstr_type": t.cstr_type,
                            "cstr_date2": self._dt_iso(t.cstr_date2),
                            "cstr_type2": t.cstr_type2,
                            "float_path": t.float_path,
                            "float_path_order": t.float_path_order,
                            "driving_path_flag": t.driving_path_flag,
                            "priority_type": t.priority_type,
                            "act_work_qty": t.act_work_qty,
                            "remain_work_qty": t.remain_work_qty,
                            "target_work_qty": t.target_work_qty,
                            "act_equip_qty": t.act_equip_qty,
                            "remain_equip_qty": t.remain_equip_qty,
                            "target_equip_qty": t.target_equip_qty,
                            "task_id_key": t.task_id_key,
                            "proj_id": t.proj_id,
                        },
                    }
                    for t in schedule.activities
                ],
            )

            # Predecessors (relationships)
            self._batch_insert(
                "predecessors",
                [
                    {
                        "project_id": project_id,
                        "task_pred_id": r.task_pred_id,
                        "task_id": r.task_id,
                        "pred_task_id": r.pred_task_id,
                        "pred_type": r.pred_type,
                        "lag_hr_cnt": r.lag_hr_cnt,
                    }
                    for r in schedule.relationships
                ],
            )

            # Calendars
            self._batch_insert(
                "calendars",
                [
                    {
                        "project_id": project_id,
                        "clndr_id": c.clndr_id,
                        "clndr_name": c.clndr_name,
                        "day_hr_cnt": c.day_hr_cnt,
                        "week_hr_cnt": c.week_hr_cnt,
                        "clndr_type": c.clndr_type,
                        "default_flag": c.default_flag,
                        "clndr_data": c.clndr_data,
                    }
                    for c in schedule.calendars
                ],
            )

            # Resources
            self._batch_insert(
                "resources",
                [
                    {
                        "project_id": project_id,
                        "rsrc_id": r.rsrc_id,
                        "rsrc_name": r.rsrc_name,
                        "rsrc_type": r.rsrc_type,
                    }
                    for r in schedule.resources
                ],
            )

            # Resource assignments
            self._batch_insert(
                "resource_assignments",
                [
                    {
                        "project_id": project_id,
                        "taskrsrc_id": tr.taskrsrc_id,
                        "task_id": tr.task_id,
                        "rsrc_id": tr.rsrc_id,
                        "proj_id": tr.proj_id,
                        "target_qty": tr.target_qty,
                        "act_reg_qty": tr.act_reg_qty,
                        "remain_qty": tr.remain_qty,
                        "target_cost": tr.target_cost,
                        "act_reg_cost": tr.act_reg_cost,
                        "remain_cost": tr.remain_cost,
                    }
                    for tr in schedule.task_resources
                ],
            )

            # Activity code types
            self._batch_insert(
                "activity_code_types",
                [
                    {
                        "project_id": project_id,
                        "actv_code_type_id": act.actv_code_type_id,
                        "actv_code_type": act.actv_code_type,
                    }
                    for act in schedule.activity_code_types
                ],
            )

            # Activity codes
            self._batch_insert(
                "activity_codes",
                [
                    {
                        "project_id": project_id,
                        "actv_code_id": ac.actv_code_id,
                        "actv_code_type_id": ac.actv_code_type_id,
                        "actv_code_name": ac.actv_code_name,
                        "short_name": ac.short_name,
                    }
                    for ac in schedule.activity_codes
                ],
            )

            # Task activity codes
            self._batch_insert(
                "task_activity_codes",
                [
                    {
                        "project_id": project_id,
                        "task_id": tac.task_id,
                        "actv_code_id": tac.actv_code_id,
                    }
                    for tac in schedule.task_activity_codes
                ],
            )

            # UDF types
            self._batch_insert(
                "udf_types",
                [
                    {
                        "project_id": project_id,
                        "udf_type_id": ut.udf_type_id,
                        "table_name": ut.table_name,
                        "udf_type_label": ut.udf_type_label,
                    }
                    for ut in schedule.udf_types
                ],
            )

            # UDF values
            self._batch_insert(
                "udf_values",
                [
                    {
                        "project_id": project_id,
                        "udf_type_id": uv.udf_type_id,
                        "fk_id": uv.fk_id,
                        "udf_text": uv.udf_text,
                        "udf_number": uv.udf_number,
                        "udf_date": self._dt_iso(uv.udf_date),
                    }
                    for uv in schedule.udf_values
                ],
            )

            # Financial periods
            self._batch_insert(
                "financial_periods",
                [
                    {
                        "project_id": project_id,
                        "fin_dates_id": fp.fin_dates_id,
                        "fin_dates_name": fp.fin_dates_name,
                        "start_date": self._dt_iso(fp.start_date),
                        "end_date": self._dt_iso(fp.end_date),
                    }
                    for fp in schedule.financial_periods
                ],
            )

            # Task financials
            self._batch_insert(
                "task_financials",
                [
                    {
                        "project_id": project_id,
                        "task_id": tf.task_id,
                        "fin_dates_id": tf.fin_dates_id,
                        "target_cost": tf.target_cost,
                        "act_cost": tf.act_cost,
                    }
                    for tf in schedule.task_financials
                ],
            )

            logger.info(
                "Persisted schedule data for project %s: %d activities, %d WBS, %d relationships",
                project_id,
                len(schedule.activities),
                len(schedule.wbs_nodes),
                len(schedule.relationships),
            )
        except Exception:
            logger.error(
                "Schedule data persistence failed for project %s; flipping status to failed",
                project_id,
                exc_info=True,
            )
            # ADR-0015 §2 state machine: flip status to 'failed' so the row
            # remains visible to owners + reports/BI with an explicit marker
            # (SCL §4 chain-of-custody; AACE MIP 3.6). The Storage XER blob
            # is preserved — it is the source for re-materialization. The
            # partially-written child rows (if any) are left in place; they
            # are project-scoped and will be overwritten on retry or removed
            # by project deletion (FK CASCADE topology unchanged).
            try:
                updated_rows = self._update(
                    "projects",
                    {"status": "failed"},
                    {"id": project_id},
                )
                if not updated_rows:
                    # PostgREST returns [] on RLS denial OR on row-not-found.
                    # Either way the compensating update did NOT take effect;
                    # surface as WARN so the operator can reconcile (e.g.
                    # service_role auth broken, row already gone, or the
                    # migration 024 column missing).
                    logger.warning(
                        "Compensating status flip for projects/%s affected 0 rows "
                        "(RLS denial, row missing, or migration 024 not applied)",
                        project_id,
                    )
            except Exception as cleanup_exc:
                logger.error(
                    "Compensating status flip also failed for project %s: %s",
                    project_id,
                    cleanup_exc,
                )

            # Bare re-raise — preserves the original persist exception as the
            # caller-visible error. Intentional: do NOT change to
            # ``raise original from cleanup_exc``; the belt-and-braces test
            # asserts the original propagates even when the cleanup path fails.
            raise

    def get_parsed_schedule(self, project_id: str) -> ParsedSchedule | None:
        """Reconstruct ParsedSchedule from DB, falling back to XER re-parse."""
        # Try DB reconstruction first (fast path — no bucket download)
        schedule = self._reconstruct_from_db(project_id)
        if schedule and schedule.activities:
            return schedule

        # Fallback: download XER from bucket and re-parse
        # (for projects uploaded before migration 018)
        return self._download_and_reparse(project_id)

    def _download_and_reparse(self, project_id: str) -> ParsedSchedule | None:
        """Download XER from Storage bucket, re-parse, return ParsedSchedule."""
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

    def _reconstruct_from_db(self, project_id: str) -> ParsedSchedule | None:
        """Rebuild a ParsedSchedule from the relational tables.

        Returns None if the project has no persisted schedule data (pre-018).
        """
        from src.parser.models import (
            ActivityCode,
            ActivityCodeType,
            Calendar,
            FinancialPeriod,
            Project as P6Project,
            Relationship,
            Resource,
            Task,
            TaskActivityCode,
            TaskFinancial,
            TaskResource,
            UDFType,
            UDFValue,
            WBS,
            XERHeader,
        )

        try:
            # Check if activities exist (fast existence check)
            probe = (
                self._client.table("activities")
                .select("id")
                .eq("project_id", project_id)
                .limit(1)
                .execute()
            )
            if not probe.data:
                return None

            # Get project metadata
            proj_rows = self._select("projects", {"id": project_id})
            if not proj_rows:
                return None
            proj_meta = proj_rows[0]

            # Build the P6 Project model from metadata
            p6_project = P6Project(
                proj_id=project_id,
                proj_short_name=proj_meta.get("project_name", ""),
                last_recalc_date=_parse_dt(proj_meta.get("data_date")),
                sum_data_date=_parse_dt(proj_meta.get("data_date")),
            )

            # Query all entity tables
            wbs_rows = self._select_all("wbs_elements", project_id)
            act_rows = self._select_all("activities", project_id)
            rel_rows = self._select_all("predecessors", project_id)
            cal_rows = self._select_all("calendars", project_id)
            rsrc_rows = self._select_all("resources", project_id)
            ra_rows = self._select_all("resource_assignments", project_id)
            act_type_rows = self._select_all("activity_code_types", project_id)
            ac_rows = self._select_all("activity_codes", project_id)
            tac_rows = self._select_all("task_activity_codes", project_id)
            udf_t_rows = self._select_all("udf_types", project_id)
            udf_v_rows = self._select_all("udf_values", project_id)
            fp_rows = self._select_all("financial_periods", project_id)
            tf_rows = self._select_all("task_financials", project_id)

            # Map rows → Pydantic models
            wbs_nodes = [
                WBS(
                    wbs_id=r["wbs_id"],
                    proj_id=project_id,
                    parent_wbs_id=r.get("parent_wbs_id") or "",
                    wbs_short_name=r.get("wbs_short_name") or "",
                    wbs_name=r.get("wbs_name") or "",
                    seq_num=r.get("seq_num") or 0,
                    proj_node_flag=r.get("proj_node_flag") or "N",
                )
                for r in wbs_rows
            ]

            activities = []
            for r in act_rows:
                extra = r.get("extra_data") or {}
                activities.append(
                    Task(
                        task_id=r["task_id"],
                        proj_id=extra.get("proj_id") or "",
                        wbs_id=r.get("wbs_id") or "",
                        clndr_id=r.get("clndr_id") or "",
                        task_code=r.get("task_code") or "",
                        task_name=r.get("task_name") or "",
                        task_type=r.get("task_type") or "",
                        status_code=r.get("status_code") or "",
                        total_float_hr_cnt=r.get("total_float_hr_cnt"),
                        free_float_hr_cnt=r.get("free_float_hr_cnt"),
                        remain_drtn_hr_cnt=r.get("remain_drtn_hr_cnt") or 0.0,
                        target_drtn_hr_cnt=r.get("target_drtn_hr_cnt") or 0.0,
                        act_start_date=_parse_dt(r.get("act_start_date")),
                        act_end_date=_parse_dt(r.get("act_end_date")),
                        early_start_date=_parse_dt(r.get("early_start_date")),
                        early_end_date=_parse_dt(r.get("early_end_date")),
                        late_start_date=_parse_dt(r.get("late_start_date")),
                        late_end_date=_parse_dt(r.get("late_end_date")),
                        target_start_date=_parse_dt(r.get("target_start_date")),
                        target_end_date=_parse_dt(r.get("target_end_date")),
                        restart_date=_parse_dt(extra.get("restart_date")),
                        reend_date=_parse_dt(extra.get("reend_date")),
                        phys_complete_pct=r.get("phys_complete_pct") or 0.0,
                        complete_pct_type=extra.get("complete_pct_type") or "",
                        duration_type=extra.get("duration_type") or "",
                        cstr_date=_parse_dt(extra.get("cstr_date")),
                        cstr_type=extra.get("cstr_type") or "",
                        cstr_date2=_parse_dt(extra.get("cstr_date2")),
                        cstr_type2=extra.get("cstr_type2") or "",
                        float_path=extra.get("float_path"),
                        float_path_order=extra.get("float_path_order"),
                        driving_path_flag=extra.get("driving_path_flag") or "",
                        priority_type=extra.get("priority_type") or "",
                        act_work_qty=extra.get("act_work_qty") or 0.0,
                        remain_work_qty=extra.get("remain_work_qty") or 0.0,
                        target_work_qty=extra.get("target_work_qty") or 0.0,
                        act_equip_qty=extra.get("act_equip_qty") or 0.0,
                        remain_equip_qty=extra.get("remain_equip_qty") or 0.0,
                        target_equip_qty=extra.get("target_equip_qty") or 0.0,
                        task_id_key=extra.get("task_id_key") or "",
                    )
                )

            relationships = [
                Relationship(
                    task_pred_id=r.get("task_pred_id") or "",
                    task_id=r["task_id"],
                    pred_task_id=r["pred_task_id"],
                    pred_type=r.get("pred_type") or "PR_FS",
                    lag_hr_cnt=r.get("lag_hr_cnt") or 0.0,
                )
                for r in rel_rows
            ]

            calendars = [
                Calendar(
                    clndr_id=r["clndr_id"],
                    clndr_name=r.get("clndr_name") or "",
                    day_hr_cnt=r.get("day_hr_cnt") or 8.0,
                    week_hr_cnt=r.get("week_hr_cnt") or 40.0,
                    clndr_type=r.get("clndr_type") or "",
                    default_flag=r.get("default_flag") or "N",
                    clndr_data=r.get("clndr_data") or "",
                )
                for r in cal_rows
            ]

            resources = [
                Resource(
                    rsrc_id=r["rsrc_id"],
                    rsrc_name=r.get("rsrc_name") or "",
                    rsrc_type=r.get("rsrc_type") or "",
                )
                for r in rsrc_rows
            ]

            task_resources = [
                TaskResource(
                    taskrsrc_id=r.get("taskrsrc_id") or "",
                    task_id=r["task_id"],
                    rsrc_id=r.get("rsrc_id") or "",
                    proj_id=r.get("proj_id") or "",
                    target_qty=r.get("target_qty") or 0.0,
                    act_reg_qty=r.get("act_reg_qty") or 0.0,
                    remain_qty=r.get("remain_qty") or 0.0,
                    target_cost=r.get("target_cost") or 0.0,
                    act_reg_cost=r.get("act_reg_cost") or 0.0,
                    remain_cost=r.get("remain_cost") or 0.0,
                )
                for r in ra_rows
            ]

            activity_code_types = [
                ActivityCodeType(
                    actv_code_type_id=r["actv_code_type_id"],
                    actv_code_type=r.get("actv_code_type") or "",
                )
                for r in act_type_rows
            ]

            activity_codes = [
                ActivityCode(
                    actv_code_id=r["actv_code_id"],
                    actv_code_type_id=r.get("actv_code_type_id") or "",
                    actv_code_name=r.get("actv_code_name") or "",
                    short_name=r.get("short_name") or "",
                )
                for r in ac_rows
            ]

            task_activity_codes = [
                TaskActivityCode(
                    task_id=r["task_id"],
                    actv_code_id=r["actv_code_id"],
                )
                for r in tac_rows
            ]

            udf_types = [
                UDFType(
                    udf_type_id=r["udf_type_id"],
                    table_name=r.get("table_name") or "",
                    udf_type_label=r.get("udf_type_label") or "",
                )
                for r in udf_t_rows
            ]

            udf_values = [
                UDFValue(
                    udf_type_id=r["udf_type_id"],
                    fk_id=r.get("fk_id") or "",
                    udf_text=r.get("udf_text"),
                    udf_number=r.get("udf_number"),
                    udf_date=_parse_dt(r.get("udf_date")),
                )
                for r in udf_v_rows
            ]

            financial_periods = [
                FinancialPeriod(
                    fin_dates_id=r["fin_dates_id"],
                    fin_dates_name=r.get("fin_dates_name") or "",
                    start_date=_parse_dt(r.get("start_date")),
                    end_date=_parse_dt(r.get("end_date")),
                )
                for r in fp_rows
            ]

            task_financials = [
                TaskFinancial(
                    task_id=r["task_id"],
                    fin_dates_id=r.get("fin_dates_id") or "",
                    target_cost=r.get("target_cost") or 0.0,
                    act_cost=r.get("act_cost") or 0.0,
                )
                for r in tf_rows
            ]

            return ParsedSchedule(
                header=XERHeader(),
                projects=[p6_project],
                calendars=calendars,
                wbs_nodes=wbs_nodes,
                activities=activities,
                relationships=relationships,
                resources=resources,
                task_resources=task_resources,
                activity_codes=activity_codes,
                activity_code_types=activity_code_types,
                task_activity_codes=task_activity_codes,
                udf_types=udf_types,
                udf_values=udf_values,
                financial_periods=financial_periods,
                task_financials=task_financials,
            )

        except Exception as exc:
            logger.warning("DB reconstruction failed for %s: %s", project_id, exc)
            return None

    def get_projects(
        self,
        user_id: str | None = None,
        include_all_statuses: bool = False,
    ) -> list[dict[str, Any]]:
        """List all projects — metadata only (no re-parse).

        Args:
            user_id: restricts to the caller's own projects. Owner-scope
                always returns every status so the UI can render badges
                (ADR-0015 §3).
            include_all_statuses: when True, non-owner list-all paths
                (``user_id=None``) return 'pending' / 'failed' rows too.
                Reports / BI / admin enumerate-with-marker paths pass
                this flag per SCL §4.
        """
        filters: dict[str, Any] | None = None
        if user_id:
            filters = {"user_id": user_id}
        rows = self._select(
            "projects",
            filters,
            columns="id,project_name,activity_count,relationship_count,storage_path,status",
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            # Guard: skip orphan rows where the XER file was never uploaded.
            if not r.get("storage_path"):
                continue
            status = r.get("status") or "ready"
            if not include_all_statuses and user_id is None and status != "ready":
                continue
            out.append(
                {
                    "project_id": str(r["id"]),
                    "name": r.get("project_name", ""),
                    "activity_count": r.get("activity_count", 0),
                    "relationship_count": r.get("relationship_count", 0),
                    "status": status,
                }
            )
        return out

    def set_project_status(self, project_id: str, status: str) -> bool:
        """Flip ``projects.status`` to one of 'pending' / 'ready' / 'failed'.

        Used by the async materializer (ADR-0015) and by the compensating
        path of ``_persist_schedule_data``. Returns True on success, False
        on silent-no-op (RLS denial, row missing, or migration 024 not
        applied). The silent-no-op case logs at WARNING so operators can
        reconcile.
        """
        if status not in {"pending", "ready", "failed"}:
            raise ValueError(
                f"invalid projects.status: {status!r}; must be one of 'pending', 'ready', 'failed'"
            )
        updated = self._update("projects", {"status": status}, {"id": project_id})
        if not updated:
            logger.warning(
                "set_project_status(%s, %s) affected 0 rows "
                "(RLS denial, row missing, or migration 024 not applied)",
                project_id,
                status,
            )
            return False
        return True

    def get_project_status(self, project_id: str) -> str | None:
        """Return the current ``projects.status`` or None if the row is missing.

        Upload responses and polling endpoints call this so the UI can
        render the ``pending`` / ``ready`` / ``failed`` badge without a
        full ``get_projects`` round trip (ADR-0015).
        """
        rows = self._select("projects", {"id": project_id}, columns="status")
        if not rows:
            return None
        return rows[0].get("status") or "ready"

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
        """Atomic upsert of the (user_id, lower(name)) program row.

        Calls Postgres RPC ``upsert_program`` (see migration 022) which
        performs ``INSERT ... ON CONFLICT (user_id, lower(name)) DO UPDATE``.
        Under concurrency two callers with the same (user_id, project_name)
        resolve to the same row — the previous select-then-insert pattern
        raced and produced duplicates. Case of the first insert is preserved
        for display; match is case-insensitive.

        Returns:
            The program UUID as a string.

        Reference: ADR-0009 Wave 0 item #5.
        """
        result = self._client.rpc(
            "upsert_program",
            {"p_user_id": user_id, "p_name": project_name},
        ).execute()
        data = result.data
        if not data:
            raise RuntimeError(f"upsert_program returned empty payload for user={user_id}")
        # PostgREST serialises a ``RETURNS UUID`` scalar as a bare string.
        # Older supabase-py versions sometimes wrap it; be defensive.
        if isinstance(data, str):
            return data
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                return str(first.get("upsert_program") or first.get("id") or first)
            return str(first)
        if isinstance(data, dict):
            return str(data.get("upsert_program") or data.get("id") or data)
        return str(data)

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
        """Get all programs for user with latest revision info.

        The inner ``projects`` subqueries include ``status`` so reports / BI
        paths can render ``failed`` revisions with an explicit marker per
        SCL §4 chain-of-custody (ADR-0015).
        """
        query = self._client.table("programs").select("*").order("updated_at", desc=True)
        if user_id:
            query = query.eq("user_id", user_id)
        programs = query.execute()
        enriched = []
        for prog in programs.data:
            # Get latest revision from projects (not schedule_uploads)
            try:
                latest = (
                    self._client.table("projects")
                    .select(
                        "id, project_name, data_date, created_at, "
                        "revision_number, activity_count, status"
                    )
                    .eq("program_id", prog["id"])
                    .order("revision_number", desc=True)
                    .limit(1)
                    .execute()
                )
                prog["latest_revision"] = latest.data[0] if latest.data else None
                rev_count = (
                    self._client.table("projects")
                    .select("id", count="exact")
                    .eq("program_id", prog["id"])
                    .execute()
                )
                prog["revision_count"] = rev_count.count or 0
            except Exception:
                prog["latest_revision"] = None
                prog["revision_count"] = 0
            enriched.append(prog)
        return enriched

    def get_program_revisions(
        self, program_id: str, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return all revisions (uploads) for a given program.

        Includes ``status`` on every row so the caller can render a badge
        or marker per revision. Failed revisions are retained intentionally
        (ADR-0015 §2) — they are part of the forensic trail, not dead data.
        """
        query = self._client.table("programs").select("id").eq("id", program_id)
        if user_id:
            query = query.eq("user_id", user_id)
        prog = query.execute()
        if not prog.data:
            return []
        return (
            self._client.table("projects")
            .select(
                "id, project_name, data_date, created_at, revision_number, activity_count, status"
            )
            .eq("program_id", program_id)
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

    def list_all(
        self,
        user_id: str | None = None,
        include_all_statuses: bool = False,
    ) -> list[dict[str, Any]]:
        """v0.5-compatible list_all method."""
        return self.get_projects(user_id=user_id, include_all_statuses=include_all_statuses)

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

    def invalidate_analysis(
        self,
        project_id: str,
        analysis_type_prefix: str | None = None,
    ) -> int:
        """Delete cached analysis rows for a project.

        Best-effort against Supabase; falls back to clearing the local
        in-memory mirror if the remote call fails. See the
        ``InMemoryStore`` docstring for semantics.
        """
        removed = 0

        # Remote delete — Supabase requires us to match rows first when
        # doing a prefix match, since PostgREST `.like()` is supported via
        # the query builder.
        try:
            query = self._client.table("analysis_results").delete().eq("project_id", project_id)
            if analysis_type_prefix is not None:
                query = query.like("analysis_type", f"{analysis_type_prefix}%")
            result = query.execute()
            removed = len(result.data or [])
        except Exception as exc:
            logger.warning("invalidate_analysis Supabase delete failed: %s", exc)

        # Always mirror the purge locally so cached fallbacks don't win.
        to_delete = [
            aid
            for aid, entry in self._analyses.items()
            if entry["project_id"] == project_id
            and (
                analysis_type_prefix is None
                or entry["analysis_type"].startswith(analysis_type_prefix)
            )
        ]
        for aid in to_delete:
            del self._analyses[aid]
        return max(removed, len(to_delete))

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

    # -- CBS cost uploads ------------------------------------------------

    def save_cost_upload(
        self,
        project_id: str,
        result: Any,
        user_id: str | None = None,
        source_name: str = "CBS Upload",
    ) -> str:
        """Persist parsed CBS to erp_sources + cbs_elements + cost_snapshots.

        Each upload creates one ``erp_sources`` row (source_system='manual'),
        N ``cbs_elements`` rows, and matching ``cost_snapshots`` for the
        budget date. Returns the erp_source id as the snapshot_id.

        Best-effort: on failure, logs and returns empty string so the
        caller can still return parsed data to the user.
        """
        snapshot_date = getattr(result, "budget_date", "") or datetime.now(UTC).date().isoformat()
        try:
            src = self._insert(
                "erp_sources",
                {
                    "project_id": project_id,
                    "source_system": "manual",
                    "display_name": source_name,
                    "sync_status": "success",
                    "last_sync_at": datetime.now(UTC).isoformat(),
                },
            )
            erp_source_id = src.get("id", "")
            cbs_element_rows = [
                {
                    "project_id": project_id,
                    "erp_source_id": erp_source_id,
                    "cbs_code": e.cbs_code,
                    "cbs_description": e.scope or e.cbs_level2 or e.cbs_level1,
                    "cbs_level": 2 if e.cbs_level2 else 1,
                    "coding_system": "custom",
                    "sort_order": i,
                }
                for i, e in enumerate(getattr(result, "cbs_elements", []))
            ]
            if cbs_element_rows:
                self._batch_insert("cbs_elements", cbs_element_rows)

            # After insert, fetch ids to build cost_snapshots
            inserted = self._select(
                "cbs_elements",
                filters={"erp_source_id": erp_source_id},
                columns="id,cbs_code",
            )
            code_to_id = {r["cbs_code"]: r["id"] for r in inserted}
            snapshot_rows = []
            for e in getattr(result, "cbs_elements", []):
                cid = code_to_id.get(e.cbs_code)
                if not cid:
                    continue
                snapshot_rows.append(
                    {
                        "project_id": project_id,
                        "cbs_element_id": cid,
                        "erp_source_id": erp_source_id,
                        "snapshot_date": snapshot_date,
                        "original_budget": float(e.estimate or 0.0),
                        "current_budget": float(e.budget or 0.0),
                        "contingency_original": float(e.contingency or 0.0),
                        "escalation": float(e.escalation or 0.0),
                    }
                )
            if snapshot_rows:
                self._batch_insert("cost_snapshots", snapshot_rows)
            return erp_source_id
        except Exception as exc:
            logger.warning("save_cost_upload failed (best-effort): %s", exc)
            return ""

    def list_cost_snapshots(
        self, project_id: str, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """List distinct cost upload sources for a project, newest first."""
        try:
            rows = self._select(
                "erp_sources",
                filters={"project_id": project_id},
                columns="id,display_name,last_sync_at,created_at",
            )
            return sorted(
                [
                    {
                        "snapshot_id": r.get("id", ""),
                        "source_name": r.get("display_name", ""),
                        "created_at": r.get("last_sync_at") or r.get("created_at", ""),
                    }
                    for r in rows
                ],
                key=lambda r: r["created_at"],
                reverse=True,
            )
        except Exception as exc:
            logger.warning("list_cost_snapshots failed: %s", exc)
            return []

    def get_cost_snapshot(
        self, project_id: str, snapshot_id: str, user_id: str | None = None
    ) -> Any | None:
        """Reconstruct a ``CostIntegrationResult`` from persisted DB rows.

        Joins ``cbs_elements`` + ``cost_snapshots`` for the given
        ``erp_sources.id`` (which is what ``save_cost_upload`` returns
        as snapshot_id). Fields that are not persisted (``cbs_level1``,
        ``cbs_level2``, ``design_package``, ``wbs_code``) are best-effort
        rehydrated from ``cbs_description`` / ``cbs_level``.

        Returns None when the snapshot is not found or the project_id
        does not match — mirrors the InMemoryStore behaviour.
        """
        from src.analytics.cost_integration import CBSElement, CostIntegrationResult

        try:
            src_rows = self._select(
                "erp_sources",
                filters={"id": snapshot_id, "project_id": project_id},
                columns="id,display_name,last_sync_at",
            )
            if not src_rows:
                return None

            element_rows = self._select(
                "cbs_elements",
                filters={"erp_source_id": snapshot_id},
                columns="id,cbs_code,cbs_description,cbs_level,sort_order",
            )
            if not element_rows:
                return CostIntegrationResult()

            snapshot_rows = self._select(
                "cost_snapshots",
                filters={"erp_source_id": snapshot_id},
                columns=(
                    "cbs_element_id,snapshot_date,original_budget,current_budget,"
                    "contingency_original,escalation"
                ),
            )
            budgets_by_element: dict[str, dict[str, Any]] = {
                r["cbs_element_id"]: r for r in snapshot_rows
            }

            result = CostIntegrationResult()
            budget_date = ""
            for row in sorted(element_rows, key=lambda r: r.get("sort_order") or 0):
                budget_row = budgets_by_element.get(row["id"], {})
                estimate = float(budget_row.get("original_budget") or 0.0)
                contingency = float(budget_row.get("contingency_original") or 0.0)
                escalation = float(budget_row.get("escalation") or 0.0)
                budget = float(budget_row.get("current_budget") or 0.0) or (
                    estimate + contingency + escalation
                )

                description = row.get("cbs_description") or ""
                level = int(row.get("cbs_level") or 1)
                element = CBSElement(
                    cbs_code=row.get("cbs_code") or "",
                    cbs_level1=description if level == 1 else "",
                    cbs_level2=description if level == 2 else "",
                    scope=description,
                    estimate=estimate,
                    contingency=contingency,
                    escalation=escalation,
                    budget=budget,
                )
                result.cbs_elements.append(element)

                if not budget_date and budget_row.get("snapshot_date"):
                    budget_date = str(budget_row["snapshot_date"])

                result.total_budget += estimate
                result.total_contingency += contingency
                result.total_escalation += escalation

            result.program_total = (
                result.total_budget + result.total_contingency + result.total_escalation
            )
            result.budget_date = budget_date

            from src.analytics.cost_integration import _generate_insights

            _generate_insights(result)
            return result
        except Exception as exc:
            logger.warning("get_cost_snapshot failed: %s", exc)
            return None

    # -- derived artifacts (ADR-0009 Wave 1 + ADR-0014) ------------------

    _VALID_STALE_REASONS = frozenset(
        {"input_changed", "engine_upgraded", "ruleset_upgraded", "manual"}
    )
    _VALID_ARTIFACT_KINDS = frozenset(
        {
            "dcma",
            "health",
            "cpm",
            "float_trends",
            "lifecycle_health",
            "lifecycle_phase_inference",
        }
    )

    def save_derived_artifact(
        self,
        project_id: str,
        artifact_kind: str,
        payload: dict[str, Any],
        engine_version: str,
        ruleset_version: str,
        input_hash: str,
        effective_at: datetime,
        computed_by: str | None = None,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
        audit_details_extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Upsert a ``schedule_derived_artifacts`` row + write the paired audit_log row.

        On conflict over the identity tuple
        ``(project_id, artifact_kind, engine_version, ruleset_version, input_hash)``
        the existing row is refreshed: ``payload`` / ``computed_at`` /
        ``computed_by`` are overwritten and ``is_stale`` cleared to False with
        ``stale_reason=NULL``. This makes re-materialization after a stale-flip
        idempotently refresh the row.

        The paired ``audit_log`` row with ``action='materialize'`` is written
        unconditionally per ADR-0014 (SCL Protocol 2nd ed §4 chain-of-custody).
        Each materialization attempt is a separate auditable event even if the
        identity tuple already exists; the audit row details.artifact_id points
        to the refreshed row's id. If the audit insert fails (transient 5xx,
        cold-start 502, or RLS denial), the exception is caught and logged at
        ERROR with structured fields so operators can reconcile via a future
        reaper — the artifact row stays saved because it is still valid data.
        A future ADR-0016 may wrap both writes in a Postgres RPC for strict
        atomicity; W1 scope follows the ADR-0012 precedent of best-effort plus
        compensating-action-on-failure over transactional-RPC-on-hot-path.

        Raises:
            ValueError: if ``artifact_kind`` is not one of the DB CHECK values
                (``dcma``, ``health``, ``cpm``, ``float_trends``, ``lifecycle_health``).
        """
        if artifact_kind not in self._VALID_ARTIFACT_KINDS:
            raise ValueError(
                f"invalid artifact_kind: {artifact_kind!r}; must be one of "
                f"{sorted(self._VALID_ARTIFACT_KINDS)}"
            )
        now_iso = datetime.now(UTC).isoformat()
        row = {
            "project_id": project_id,
            "artifact_kind": artifact_kind,
            "payload": _json_safe(payload),
            "engine_version": engine_version,
            "ruleset_version": ruleset_version,
            "input_hash": input_hash,
            "effective_at": effective_at.isoformat(),
            "computed_at": now_iso,
            "computed_by": computed_by,
            "is_stale": False,
            "stale_reason": None,
        }
        saved = self._upsert(
            "schedule_derived_artifacts",
            row,
            on_conflict="project_id,artifact_kind,engine_version,ruleset_version,input_hash",
        )
        audit_details: dict[str, Any] = {
            "artifact_kind": artifact_kind,
            "artifact_id": saved.get("id"),
            "engine_version": engine_version,
            "ruleset_version": ruleset_version,
            "input_hash": input_hash,
        }
        if audit_details_extra:
            audit_details.update(_json_safe(audit_details_extra))
        try:
            self._insert(
                "audit_log",
                {
                    "user_id": computed_by,
                    "action": "materialize",
                    "entity_type": "project",
                    "entity_id": project_id,
                    "details": audit_details,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                },
            )
        except Exception as exc:
            logger.error(
                "audit_log_insert_failed action=materialize project_id=%s "
                "artifact_id=%s artifact_kind=%s error=%s",
                project_id,
                saved.get("id"),
                artifact_kind,
                exc,
            )
        return saved

    def get_latest_derived_artifact(
        self,
        project_id: str,
        artifact_kind: str,
        current_engine_version: str,
        current_ruleset_version: str,
    ) -> dict[str, Any] | None:
        """Return the most recent non-stale artifact of the given kind for the project.

        Reads via the partial index ``idx_sda_latest_fresh``
        ``(project_id, artifact_kind, computed_at DESC) WHERE is_stale=false``.

        Returns None when:
        - no non-stale artifact exists for ``(project_id, artifact_kind)``
        - stored ``engine_version`` differs from ``current_engine_version``
        - stored ``ruleset_version`` differs from ``current_ruleset_version``

        Version-mismatch → None forces re-materialization under the current
        engine on the next read-path invocation per ADR-0014.
        """
        result = (
            self._client.table("schedule_derived_artifacts")
            .select("*")
            .eq("project_id", project_id)
            .eq("artifact_kind", artifact_kind)
            .eq("is_stale", False)
            .order("computed_at", desc=True)
            .limit(1)
            .execute()
        )
        rows: list[dict[str, Any]] = result.data or []
        if not rows:
            return None
        latest = rows[0]
        if latest.get("engine_version") != current_engine_version:
            return None
        if latest.get("ruleset_version") != current_ruleset_version:
            return None
        return latest

    def get_projects_at_engine_version(
        self, engine_version: str, *, include_stale: bool = False
    ) -> list[str]:
        """Return distinct project IDs with at least one derived artifact at
        the given ``engine_version`` — driver query for the re-materialization
        workflow (Cycle 3 W4).

        ``include_stale=False`` (default): only fresh rows. Used by
        ``src/materializer/backfill.py --re-materialize-version <ver>``.

        ``include_stale=True``: diagnostic query for the CLI's "0 candidates
        + Option-B-already-ran" detection — see InMemoryStore docstring above
        for the full rationale.

        Pagination: explicit ``range(0, RE_MAT_MAX_ROWS - 1)`` cap of
        10,000 rows. PostgREST's silent default of 1,000 would silently
        truncate above that; raising past 10k crosses into
        "data has scaled past the operator-script regime" territory and
        deserves a hard error, not silent truncation. Logged warning fires
        if the query hits the cap so the operator knows pagination is
        needed.
        """
        query = (
            self._client.table("schedule_derived_artifacts")
            .select("project_id")
            .eq("engine_version", engine_version)
        )
        if not include_stale:
            query = query.eq("is_stale", False)
        result = query.range(0, RE_MAT_MAX_ROWS - 1).execute()
        rows: list[dict[str, Any]] = result.data or []
        if len(rows) >= RE_MAT_MAX_ROWS:
            logger.warning(
                "get_projects_at_engine_version(%r, include_stale=%s): hit "
                "row cap of %d — result may be truncated; operator must "
                "paginate via an alternative query path before running "
                "re-materialization.",
                engine_version,
                include_stale,
                RE_MAT_MAX_ROWS,
            )
        return sorted({row["project_id"] for row in rows})

    def mark_stale(
        self,
        project_id: str,
        stale_reason: str = "input_changed",
    ) -> int:
        """Flip ``is_stale=True`` and set ``stale_reason`` on all artifacts of a project.

        Returns the number of rows affected. Called from the upload happy-path
        alongside ``invalidate_namespace("schedule:kpis")``. Default reason is
        ``'input_changed'`` for the upload case; callers pass explicit
        ``'engine_upgraded'`` / ``'ruleset_upgraded'`` / ``'manual'`` for
        targeted re-materialization (AACE RP 114R determinism).

        Under the ``authenticated`` role the UPDATE requires the
        ``sda_update_own`` RLS policy (migration 023); a silent-no-op return
        of 0 rows signals the policy is missing or the caller lacks ownership.

        Raises:
            ValueError: if ``stale_reason`` is not one of the CHECK values.
        """
        if stale_reason not in self._VALID_STALE_REASONS:
            raise ValueError(
                f"invalid stale_reason: {stale_reason!r}; must be one of {sorted(self._VALID_STALE_REASONS)}"
            )
        updated = self._update(
            "schedule_derived_artifacts",
            {"is_stale": True, "stale_reason": stale_reason},
            {"project_id": project_id},
        )
        count = len(updated)
        if count == 0:
            logger.warning(
                "mark_stale affected 0 rows for project_id=%s reason=%s "
                "(no artifacts yet, all already stale, or RLS denial under authenticated role)",
                project_id,
                stale_reason,
            )
        return count

    # -- lifecycle phase lock + override log (ADR-0016) -------------------

    def set_lifecycle_phase_lock(self, project_id: str, locked: bool) -> bool:
        """Flip ``projects.lifecycle_phase_locked``. Returns True on success.

        Symmetric with :meth:`InMemoryStore.set_lifecycle_phase_lock`.
        Silent-no-op (RLS denial, row missing, migration 025 not applied)
        logs at WARNING and returns False.
        """
        updated = self._update(
            "projects",
            {"lifecycle_phase_locked": bool(locked)},
            {"id": project_id},
        )
        if not updated:
            logger.warning(
                "set_lifecycle_phase_lock(%s, %s) affected 0 rows "
                "(RLS denial, row missing, or migration 025 not applied)",
                project_id,
                locked,
            )
            return False
        return True

    def get_lifecycle_phase_lock(self, project_id: str) -> bool:
        """Return ``projects.lifecycle_phase_locked``; False if row missing."""
        rows = self._select("projects", {"id": project_id}, columns="lifecycle_phase_locked")
        if not rows:
            return False
        return bool(rows[0].get("lifecycle_phase_locked", False))

    def save_lifecycle_override(
        self,
        project_id: str,
        override_phase: str,
        override_reason: str,
        *,
        inferred_phase: str | None = None,
        overridden_by: str | None = None,
        engine_version: str,
        ruleset_version: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Append a ``lifecycle_override_log`` row + flip lock + audit_log entry.

        Per ADR-0016 §3 the override row is forensic — append-only RLS
        contract, no UPDATE / no DELETE policies. The lock flip and the
        audit_log row land via separate writes (best-effort, following
        the W1 ADR-0014 precedent — atomicity-via-RPC is W4+ scope if
        operational evidence justifies). The audit row is written under
        ``action='lifecycle_override'`` per BR P1#8.

        Raises:
            ValueError: if the phase vocabulary or empty reason violate
                the contract enforced symmetrically in DB CHECK constraints.
        """
        from src.analytics.lifecycle_types import LIFECYCLE_PHASES

        if override_phase not in LIFECYCLE_PHASES:
            raise ValueError(
                f"invalid override_phase: {override_phase!r}; "
                f"must be one of {list(LIFECYCLE_PHASES)}"
            )
        if inferred_phase is not None and inferred_phase not in LIFECYCLE_PHASES:
            raise ValueError(
                f"invalid inferred_phase: {inferred_phase!r}; "
                f"must be one of {list(LIFECYCLE_PHASES)} or None"
            )
        if not override_reason or not override_reason.strip():
            raise ValueError("override_reason must be non-empty")

        row = {
            "project_id": project_id,
            "inferred_phase": inferred_phase,
            "override_phase": override_phase,
            "override_reason": override_reason,
            "overridden_by": overridden_by,
            "engine_version": engine_version,
            "ruleset_version": ruleset_version,
        }
        saved = self._insert("lifecycle_override_log", row)
        # Side-effect: flip the lock so the materializer skips re-inference.
        # Council end-of-wave (BR P1-3): if the lock flip fails (RLS denial
        # / row missing / migration drift), the override row is already
        # written but the lock is not set — Cost Engineer JTBD silently
        # breaks. Log at ERROR so an operator can reconcile via a periodic
        # reaper. Mirrors the audit_log try/except pattern below (W1
        # ADR-0014 precedent).
        lock_ok = self.set_lifecycle_phase_lock(project_id, True)
        if not lock_ok:
            logger.error(
                "lifecycle_lock_flip_failed override_id=%s project_id=%s "
                "(override row written but projects.lifecycle_phase_locked NOT set; "
                "next materializer run will overwrite the override)",
                saved.get("id"),
                project_id,
            )
        # Audit trail (BR P1#8).
        try:
            self._insert(
                "audit_log",
                {
                    "user_id": overridden_by,
                    "action": "lifecycle_override",
                    "entity_type": "project",
                    "entity_id": project_id,
                    "details": {
                        "override_id": saved.get("id"),
                        "inferred_phase": inferred_phase,
                        "override_phase": override_phase,
                        "engine_version": engine_version,
                        "ruleset_version": ruleset_version,
                        "reason_length": len(override_reason),
                    },
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                },
            )
        except Exception as exc:
            logger.error(
                "audit_log_insert_failed action=lifecycle_override project_id=%s "
                "override_id=%s error=%s",
                project_id,
                saved.get("id"),
                exc,
            )
        return saved

    def list_lifecycle_overrides(self, project_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return overrides for a project ordered ``overridden_at DESC``.

        Hits ``idx_lifecycle_override_log_project_recent`` (migration 025).
        """
        result = (
            self._client.table("lifecycle_override_log")
            .select("*")
            .eq("project_id", project_id)
            .order("overridden_at", desc=True)
            .limit(max(0, limit))
            .execute()
        )
        rows: list[dict[str, Any]] = result.data or []
        return rows

    def get_latest_lifecycle_override(self, project_id: str) -> dict[str, Any] | None:
        """Return the most-recent override row for a project or None."""
        rows = self.list_lifecycle_overrides(project_id, limit=1)
        return rows[0] if rows else None


# ------------------------------------------------------------------ #
# Helpers                                                            #
# ------------------------------------------------------------------ #


def _parse_dt(value: str | datetime | None) -> datetime | None:
    """Parse an ISO-8601 string or passthrough a datetime. Returns None on failure."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


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
