# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Backfill CLI for projects predating the Wave 2 async materializer.

Usage::

    python -m src.materializer.backfill [options]

Options:

``--limit N``
    Stop after materializing N projects.

``--project-id UUID``
    Target a single project. Useful for diagnosing one-off backfill
    failures without running the full batch.

``--dry-run``
    Print the candidate count without materializing anything.

Selection: ``projects`` rows with ``status='ready'`` whose ``dcma`` artifact
returns ``None`` from ``get_latest_derived_artifact`` (the common miss case
— covers both "never materialized" AND "materialized under an older engine
version"). Running in serial on a Fly.io VM via ``fly ssh console`` keeps
the HTTP worker responsive (ADR-0015 §6).

Idempotence: ``save_derived_artifact`` upserts on the uniqueness tuple, so
re-running an overlapping batch is safe. Audit trail: every artifact write
logs an ``audit_log`` row with ``user_id=NULL`` + ``details.trigger =
'system_backfill_v2'`` + ``details.backfill_id = <uuid>``.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from typing import Any

from src.materializer.runtime import Materializer, _RULESET_VERSIONS

logger = logging.getLogger("src.materializer.backfill")


def _re_materialization_candidates(
    store: Any,
    old_engine_version: str,
    limit: int | None,
) -> list[str]:
    """Enumerate projects whose artifacts predate the current engine version.

    Cycle 3 W4 use case: PR #50 migrated ``_ENGINE_VERSION`` from hardcoded
    ``"4.0"`` to source from ``src/__about__.py::__version__`` (currently
    ``"4.1.0"``). The 88 production rows at ``engine_version="4.0"`` become
    invisible to ``get_latest_derived_artifact`` per ADR-0014 §"Decision
    Outcome" (version mismatch → forced re-mat). This helper drives the
    one-shot bulk re-materialization that closes the visibility gap.

    Calls ``store.get_projects_at_engine_version(old_engine_version)``,
    which both ``InMemoryStore`` and ``SupabaseStore`` implement against
    ``schedule_derived_artifacts``.
    """
    if not hasattr(store, "get_projects_at_engine_version"):
        raise NotImplementedError(
            "Store must implement `get_projects_at_engine_version(engine_version, "
            "*, include_stale=False)` for re-materialization mode. "
            "See src/database/store.py InMemoryStore + SupabaseStore."
        )
    pids = store.get_projects_at_engine_version(old_engine_version)
    if limit is not None:
        return pids[:limit]
    return pids


def _diagnose_zero_candidates(
    store: Any,
    old_engine_version: str,
) -> str | None:
    """Return a diagnostic warning string when re-mat finds 0 candidates,
    or None if no diagnostic applies.

    Per Cycle 3 W4 §W4 runbook + ADR-0014: Option A (bulk re-mat) and
    Option B (migration 027 tombstone) silently neutralize each other if
    applied in the wrong order. After Option B runs, the fresh-rows query
    returns 0 candidates — the CLI would otherwise return rc=0 with no
    signal, leading the operator to believe the re-mat succeeded.

    This diagnostic checks for stale rows at the same engine_version
    (i.e., Option B already applied). When found, returns a multi-line
    warning the CLI logs at WARNING level so 2-AM operators see the
    ordering trap before they reach the verification step.
    """
    if not hasattr(store, "get_projects_at_engine_version"):
        return None
    try:
        stale_pids = store.get_projects_at_engine_version(old_engine_version, include_stale=True)
    except TypeError:
        # Older store implementation without `include_stale` keyword; skip.
        return None
    if not stale_pids:
        return None
    # We have rows at this engine_version, but all are stale → Option B
    # has already been applied (or some other process tombstoned them).
    return (
        f"Re-mat found 0 candidates at engine_version={old_engine_version!r}, "
        f"but {len(stale_pids)} project(s) have STALE rows at that version. "
        "This is the Option-B-already-ran case (migration 027 tombstoned "
        "the rows). Re-mat candidates are filtered to non-stale only — see "
        "docs/operator-runbooks/cycle3.md §W4. If you intended Option A "
        "(bulk re-mat) but Option B already ran, the read-path forces re-mat "
        "on first read of each project — no further operator action needed. "
        "If you intended Option B and ran the migration, this WARNING is "
        "informational; you can ignore."
    )


def _candidate_project_ids(
    store: Any,
    limit: int | None,
    explicit_project_id: str | None,
    kind: str = "dcma",
) -> list[str]:
    """Enumerate backfill candidates — projects with status=ready whose
    artifact of ``kind`` is missing or version-stale.

    Default ``kind='dcma'`` keeps W2 behaviour: DCMA acts as a proxy for
    "never materialized by the current engine version". When a new
    artifact kind ships post-W2 (W3 introduces ``'lifecycle_phase_inference'``
    per ADR-0016), operators can target the specific gap with
    ``--kind <new_kind>`` so already-materialized projects pick up the
    new artifact without re-running every other engine's heuristic.

    For ``kind='lifecycle_phase_inference'`` the helper additionally skips
    projects with ``lifecycle_phase_locked=true`` (Cost Engineer override
    stickiness per ADR-0016) — the materializer would no-op them anyway,
    but skipping here avoids per-run reselection noise in the logs.
    """
    if explicit_project_id is not None:
        return [explicit_project_id]

    if kind not in _RULESET_VERSIONS:
        raise ValueError(
            f"unknown artifact kind: {kind!r}; must be one of {sorted(_RULESET_VERSIONS)}"
        )

    # Single-source the engine version from runtime so a future bump
    # cannot silently drift between the producer (runtime.py write
    # path) and the backfill consumer (this module, which queries
    # existing rows for staleness against ``current_engine_version``).
    # Pre-dedup the literal was duplicated here as ``"4.0"``; the
    # write-side value lives at ``src/materializer/runtime.py`` and
    # is the canonical contract per ADR-0014.
    from .runtime import _ENGINE_VERSION

    engine_version = _ENGINE_VERSION
    ruleset = _RULESET_VERSIONS[kind]
    skip_locked = kind == "lifecycle_phase_inference"
    lock_getter = getattr(store, "get_lifecycle_phase_lock", None)
    rows = store.get_projects(include_all_statuses=False)
    out: list[str] = []
    for row in rows:
        pid = row["project_id"]
        if skip_locked and lock_getter is not None:
            try:
                if lock_getter(pid):
                    continue
            except Exception:
                logger.exception(
                    "Backfill: failed to read lock for %s; treating as unlocked",
                    pid,
                )
        latest = store.get_latest_derived_artifact(
            project_id=pid,
            artifact_kind=kind,
            current_engine_version=engine_version,
            current_ruleset_version=ruleset,
        )
        if latest is None:
            out.append(pid)
            if limit is not None and len(out) >= limit:
                break
    return out


async def _run_batch(
    materializer: Materializer,
    project_ids: list[str],
    backfill_id: str,
) -> dict[str, int]:
    """Run the materializer serially over every candidate.

    Returns a dict of ``{"ok": N, "failed": N, "skipped": N}`` so the
    caller can emit a tidy summary on exit.

    Each materialization writes an ``audit_log`` row whose ``details``
    carries ``trigger='system_backfill_v2'`` and the shared
    ``backfill_id`` so SCL §4 chain-of-custody distinguishes system-
    initiated runs from user-initiated uploads (ADR-0015 §6).
    """
    stats = {"ok": 0, "failed": 0, "skipped": 0}
    audit_extra = {
        "trigger": "system_backfill_v2",
        "backfill_id": backfill_id,
    }
    for pid in project_ids:
        logger.info("Backfill %s → materializing %s", backfill_id, pid)
        try:
            await materializer.materialize(
                pid,
                audit_details_extra=audit_extra,
            )
            stats["ok"] += 1
        except Exception:
            logger.exception("Backfill %s failed for project %s", backfill_id, pid)
            stats["failed"] += 1
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="src.materializer.backfill")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after materializing N projects.",
    )
    parser.add_argument(
        "--project-id",
        dest="project_id",
        type=str,
        default=None,
        help="Target a single project UUID.",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Print candidate count without running.",
    )
    parser.add_argument(
        "--kind",
        type=str,
        default="dcma",
        help=(
            "Artifact kind used as the missing-proxy for candidate selection. "
            "Default 'dcma' covers the W2 first-time-materialization case. "
            "Use 'lifecycle_phase_inference' (ADR-0016) post-W3 to backfill "
            "the new kind onto already-materialized projects."
        ),
    )
    parser.add_argument(
        "--re-materialize-version",
        dest="re_materialize_version",
        type=str,
        default=None,
        help=(
            "Re-materialization mode (Cycle 3 W4 / criterion #7): select projects "
            "that have at least one non-stale derived artifact at this OLD "
            "engine_version (e.g., '4.0'), and re-run the materializer to produce "
            "fresh rows at the current engine_version per ADR-0014 §'Decision "
            "Outcome' provenance contract. Designed for the post-PR-#50 88-row "
            "re-mat. Re-mat covers all kinds for the affected projects — "
            "passing --kind alongside --re-materialize-version is a hard error. "
            "Mutually exclusive with --project-id."
        ),
    )
    args = parser.parse_args(argv)

    if args.re_materialize_version is not None and args.project_id is not None:
        parser.error("--re-materialize-version and --project-id are mutually exclusive")

    if args.re_materialize_version is not None and args.kind != "dcma":
        parser.error(
            "--kind is incompatible with --re-materialize-version "
            "(re-mat covers all kinds for the affected projects)"
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    backfill_id = str(uuid.uuid4())
    logger.info("Backfill %s starting", backfill_id)

    # Import lazily so `--help` works even when the store cannot be
    # instantiated (e.g. missing Supabase credentials on a dev box).
    from src.api.deps import get_materializer, get_store

    store = get_store()
    if args.re_materialize_version is not None:
        candidates = _re_materialization_candidates(store, args.re_materialize_version, args.limit)
        logger.info(
            "Backfill %s → %d candidate project(s) for re-mat from engine_version=%r",
            backfill_id,
            len(candidates),
            args.re_materialize_version,
        )
        # Order-of-operations diagnostic — see _diagnose_zero_candidates docstring.
        if not candidates:
            diagnostic = _diagnose_zero_candidates(store, args.re_materialize_version)
            if diagnostic is not None:
                logger.warning("Backfill %s — %s", backfill_id, diagnostic)
    else:
        candidates = _candidate_project_ids(store, args.limit, args.project_id, kind=args.kind)
        logger.info(
            "Backfill %s → %d candidate project(s) for kind=%s",
            backfill_id,
            len(candidates),
            args.kind,
        )

    if args.dry_run:
        for pid in candidates:
            print(pid)
        return 0

    if not candidates:
        logger.info("Backfill %s → nothing to materialize", backfill_id)
        return 0

    materializer = get_materializer()
    stats = asyncio.run(_run_batch(materializer, candidates, backfill_id))
    logger.info(
        "Backfill %s done: ok=%d failed=%d skipped=%d",
        backfill_id,
        stats["ok"],
        stats["failed"],
        stats["skipped"],
    )
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":  # pragma: no cover — exercised via CLI integration tests
    sys.exit(main())
