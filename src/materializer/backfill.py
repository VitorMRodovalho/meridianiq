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


def _candidate_project_ids(
    store: Any,
    limit: int | None,
    explicit_project_id: str | None,
) -> list[str]:
    """Enumerate backfill candidates — projects with status=ready whose
    ``dcma`` artifact is missing or version-stale.

    The ``dcma`` slot is used as a proxy for "this project was never
    materialized by the current engine version"; if dcma is fresh we
    trust the rest are (or will be re-computed under the same run).
    """
    if explicit_project_id is not None:
        return [explicit_project_id]

    engine_version = "4.0"
    dcma_ruleset = _RULESET_VERSIONS["dcma"]
    rows = store.get_projects(include_all_statuses=False)
    out: list[str] = []
    for row in rows:
        pid = row["project_id"]
        latest = store.get_latest_derived_artifact(
            project_id=pid,
            artifact_kind="dcma",
            current_engine_version=engine_version,
            current_ruleset_version=dcma_ruleset,
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
    args = parser.parse_args(argv)

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
    candidates = _candidate_project_ids(store, args.limit, args.project_id)
    logger.info("Backfill %s → %d candidate project(s)", backfill_id, len(candidates))

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
