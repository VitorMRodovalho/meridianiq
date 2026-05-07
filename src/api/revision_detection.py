# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Revision detection heuristic + content_hash helper for Cycle 4 W2 PR-A.

Implements the v1 heuristic per ADR-0022 §"Wave plan W2" + Amendment 2:
same ``project_name`` (case-insensitive) + same ``program_id`` (already
auto-assigned at upload by ``store.save_project`` via
``get_or_create_program``) + different ``data_date`` (avoid duplicates).

## Why ``project_name + program_id + data_date`` and NOT ADR-0022's
## original ``proj_short_name + proj_id + content_hash``

Backend-reviewer entry council (PR-A) flagged that ADR-0022's original
spec assumed no auto-grouping at upload. In reality, ``save_project``
already groups uploads with matching ``proj_short_name`` into the same
``programs`` row. The detect endpoint's job is therefore to find
SIBLINGS within the auto-assigned program, NOT to find a parent across
programs. ADR-0022 Amendment 2 codifies this scope-fix-up.

``proj_id`` (P6 internal) is parsed but not stored as a top-level
``projects`` column — adding it to the heuristic requires a parser-
side breakout (out of W2 scope). XER content_hash similarity is more
powerful but more complex (exact equality is trivial; near-equality
needs LSH/Jaccard); deferred to W3 or Cycle 5+ on demand evidence.

## Why ``compute_xer_content_hash`` lives here, NOT in canonical_hash.py

``src/database/canonical_hash.py`` is the frozen ADR-0014 forensic
primitive over canonical-JSON of ``ParsedSchedule``. Conflating it
with the XER-bytes-sha256 used here for revision identity would risk
future contributors importing the wrong helper. Cross-reference both
ways via docstrings.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


_HEURISTIC_CONFIDENCE_HIGH = 0.9
"""Confidence assigned when the v1 heuristic finds an exact name+program match.

NOT a calibrated probability — UI prioritization signal only. Bumping or
recalibrating this requires ADR-0022 Amendment N or a successor ADR for
revision detection (per the calibration discipline of ADR-0009 Amendment 2).
"""


def compute_xer_content_hash(xer_bytes: bytes) -> str:
    """Return sha256 hex digest of XER bytes (lowercase 64-char hex).

    Matches migration 028 ``CHECK (content_hash ~ '^[0-9a-f]{64}$')``.
    ``hashlib.sha256(...).hexdigest()`` is lowercase by contract — never
    uppercase via ``.hex().upper()`` (would silently break the CHECK
    constraint at INSERT time).

    Distinct from ``src.database.canonical_hash.compute_input_hash`` which
    hashes the canonical-JSON of the parsed-schedule slice (ADR-0014).
    Same storage shape (sha256 hex 64 chars), different semantic content.
    Use THIS helper for revision_history.content_hash; use the canonical_
    hash one for schedule_derived_artifacts.input_hash.
    """
    return hashlib.sha256(xer_bytes).hexdigest()


def _normalise_name(name: str | None) -> str:
    """Case-insensitive, whitespace-trimmed name for heuristic comparison."""
    if not name:
        return ""
    return name.strip().lower()


def detect_candidate_parent(
    store: Any,
    user_id: str,
    project_id: str,
) -> dict[str, Any]:
    """Heuristic v1: find the most-recent sibling project as candidate parent.

    Returns a dict with the same field shape as ``DetectRevisionOfResponse``
    (router lifts to Pydantic). All numeric defaults to 0; all string
    defaults to None when no candidate found.

    ## Heuristic logic

    1. Load the current project. If not found OR not owned by ``user_id``
       OR has no ``program_id``, return no candidate.
    2. Load all of the caller's projects in the same program (excluding
       the current project itself) ordered by ``data_date DESC NULLS LAST``.
       Note ``project_name`` is auto-shared within a program because
       ``save_project`` groups by name; the program filter alone is
       sufficient. The case-insensitive name check below is defensive
       against future drift in the auto-grouping rule.
    3. Filter: candidate.``data_date`` MUST differ from current.``data_date``
       (avoid duplicates of the same XER).
    4. Take the most recent. If found, return high confidence + reasoning.

    ## Defensive contract

    Heuristic must NEVER raise — it is a read-only diagnostic. Failures
    log a warning and return the no-candidate shape.
    """
    no_candidate: dict[str, Any] = {
        "candidate_project_id": None,
        "candidate_project_name": None,
        "candidate_data_date": None,
        "candidate_revision_count": 0,
        "confidence": 0.0,
        "reasoning": "no candidate found",
    }

    try:
        current = store.get_project_meta(project_id, user_id=user_id)
    except Exception as exc:  # noqa: BLE001 — diagnostic must not raise
        logger.warning("detect: get_project_meta failed for %s: %s", project_id, exc)
        return no_candidate

    if current is None:
        return {**no_candidate, "reasoning": "current project not found"}
    if current.get("user_id") not in (None, user_id):
        # RLS belt-and-suspenders — store layer should already have filtered.
        return {**no_candidate, "reasoning": "current project not owned by caller"}

    program_id = current.get("program_id")
    if not program_id:
        return {
            **no_candidate,
            "reasoning": "current project has no program_id (anonymous upload?)",
        }

    current_name = _normalise_name(current.get("project_name"))
    current_data_date = current.get("data_date")

    try:
        siblings = store.list_projects_in_program(program_id, user_id=user_id)
    except Exception as exc:  # noqa: BLE001 — diagnostic must not raise
        logger.warning("detect: list_projects_in_program failed for %s: %s", program_id, exc)
        return no_candidate

    candidates = [
        s
        for s in siblings
        if s.get("project_id") != project_id
        and _normalise_name(s.get("project_name")) == current_name
        and s.get("data_date") != current_data_date
    ]
    if not candidates:
        return {**no_candidate, "reasoning": "no sibling with different data_date"}

    candidates.sort(
        key=lambda r: (r.get("data_date") or "", r.get("revision_date") or ""),
        reverse=True,
    )
    top = candidates[0]

    try:
        revision_count = store.count_active_revisions_in_program(program_id, user_id=user_id)
    except Exception as exc:  # noqa: BLE001 — diagnostic must not raise
        logger.warning(
            "detect: count_active_revisions_in_program failed for %s: %s", program_id, exc
        )
        revision_count = 0

    return {
        "candidate_project_id": top.get("project_id"),
        "candidate_project_name": top.get("project_name"),
        "candidate_data_date": top.get("data_date"),
        "candidate_revision_count": revision_count,
        "confidence": _HEURISTIC_CONFIDENCE_HIGH,
        "reasoning": (
            f"matched on project_name + program_id; sibling has different data_date "
            f"({top.get('data_date')} vs current {current_data_date})"
        ),
    }
