# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Canonical hash for derived-artifact provenance (ADR-0014).

DO NOT change this implementation without authoring a superseding ADR.
Changing the canonical-JSON algorithm silently invalidates every
historical ``input_hash`` stored in ``schedule_derived_artifacts``,
breaking the forensic reproducibility promised by ADR-0009 Wave 1 and
ADR-0014. Any change requires an ADR-0015 plus a full backfill worker
that re-materializes every prior artifact under the new algorithm.

Standards cited:

- SCL Protocol 2nd ed §4 (chain-of-custody — the hash plus the paired
  ``audit_log`` row together satisfy actor-identifiable recordkeeping)
- AACE RP 14R / 29R / 57R §4.1 / 114R (forensic reproducibility and
  Monte Carlo determinism — hash stability is the precondition)
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.parser.models import ParsedSchedule


def compute_input_hash(schedule: ParsedSchedule, project_id: str) -> str:
    """Return the sha256 hex digest of the canonical JSON of a project-scoped slice.

    Per ADR-0014, the hash input is the project-scoped subset of a
    ``ParsedSchedule`` encoded as canonical JSON. The returned string is a
    lowercase 64-character hex digest.

    Project-scoping rules:

    - Direct ``proj_id`` filter on ``projects``, ``activities``, ``wbs_nodes``,
      ``relationships``, ``activity_code_types``, ``task_resources``.
    - FK-chain filter for tables without ``proj_id``:
      ``calendars`` via ``activities.clndr_id``;
      ``resources`` via ``task_resources.rsrc_id``;
      ``activity_codes`` via ``activity_code_types.actv_code_type_id``;
      ``task_activity_codes`` and ``task_financials`` via ``activities.task_id``.
    - Excluded (W1 scope): ``header`` (XER file-level metadata, volatile),
      ``raw_tables`` (unstructured, cannot safely per-project filter),
      ``unmapped_tables``, ``parser_version``, ``udf_*``, ``financial_periods``.
      If a future engine consumes any of these, a superseding ADR-0015 with
      backfill is required.

    Canonical JSON rules (ADR-0014):

    - Object keys sorted lexicographically at every nesting level.
    - Arrays in document order — NEVER sorted, since ``activities`` and
      ``relationships`` order is semantically meaningful for CPM.
    - ``datetime`` values serialized via ``isoformat(timespec='microseconds')``
      preserving source naivete (XER datetimes are naive local-project).
    - ``str`` values are Unicode-normalized to NFC before serialization. Same
      human-readable content MUST hash identically regardless of whether the
      source XER was authored on a system that emits NFC (Windows default) or
      NFD (macOS default). Silent NFC/NFD divergence would produce two
      artifacts for what a forensic reviewer calls one schedule — breaking
      the reproducibility claim.
    - ``None`` → JSON ``null``.
    - ``separators=(",", ":")`` — no whitespace.
    - Non-finite floats (NaN, +Inf, -Inf) raise ``ValueError`` — a forensic
      hash over corrupted numeric data would be silently misleading.
    - UTF-8 bytes; ``ensure_ascii=False`` to preserve accented project names
      (PT-BR, ES content) post-normalization.

    Raises:
        ValueError: if the schedule contains non-finite floats (NaN/Inf).
        TypeError: if the schedule contains an unserializable type unknown to
            this canonicalizer (a signal that a new type landed in the parser
            and this helper must be updated via ADR-0015).
    """
    sliced = _project_scope(schedule, project_id)
    normalized = _nfc_normalize(sliced)
    canonical = _canonical_json_bytes(normalized)
    return hashlib.sha256(canonical).hexdigest()


def _nfc_normalize(obj: Any) -> Any:
    """Recursively apply Unicode NFC normalization to every ``str`` inside ``obj``.

    Prevents NFC/NFD divergence from silently producing different hashes for
    strings that render identically. Required for forensic reproducibility
    across Windows (NFC default) vs macOS (NFD default) authoring environments
    per ADR-0014.
    """
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, list):
        return [_nfc_normalize(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _nfc_normalize(value) for key, value in obj.items()}
    return obj


def _project_scope(schedule: ParsedSchedule, project_id: str) -> dict[str, Any]:
    """Build the project-scoped slice as a dict of Python-native primitives.

    See ``compute_input_hash`` docstring for the scoping rules.
    """
    projects = [p.model_dump(mode="python") for p in schedule.projects if p.proj_id == project_id]
    activities = [
        t.model_dump(mode="python") for t in schedule.activities if t.proj_id == project_id
    ]
    wbs_nodes = [w.model_dump(mode="python") for w in schedule.wbs_nodes if w.proj_id == project_id]
    relationships = [
        r.model_dump(mode="python") for r in schedule.relationships if r.proj_id == project_id
    ]
    activity_code_types = [
        at.model_dump(mode="python")
        for at in schedule.activity_code_types
        if at.proj_id == project_id
    ]
    task_resources = [
        tr.model_dump(mode="python") for tr in schedule.task_resources if tr.proj_id == project_id
    ]

    task_ids: set[str] = {t["task_id"] for t in activities}
    clndr_ids: set[str] = {t["clndr_id"] for t in activities if t.get("clndr_id")}
    rsrc_ids: set[str] = {tr["rsrc_id"] for tr in task_resources if tr.get("rsrc_id")}
    actv_code_type_ids: set[str] = {at["actv_code_type_id"] for at in activity_code_types}

    task_activity_codes = [
        tac.model_dump(mode="python")
        for tac in schedule.task_activity_codes
        if tac.task_id in task_ids
    ]
    task_financials = [
        tf.model_dump(mode="python") for tf in schedule.task_financials if tf.task_id in task_ids
    ]
    calendars = [c.model_dump(mode="python") for c in schedule.calendars if c.clndr_id in clndr_ids]
    resources = [r.model_dump(mode="python") for r in schedule.resources if r.rsrc_id in rsrc_ids]
    activity_codes = [
        ac.model_dump(mode="python")
        for ac in schedule.activity_codes
        if ac.actv_code_type_id in actv_code_type_ids
    ]

    return {
        "project_id": project_id,
        "projects": projects,
        "activities": activities,
        "wbs_nodes": wbs_nodes,
        "relationships": relationships,
        "activity_code_types": activity_code_types,
        "task_resources": task_resources,
        "task_activity_codes": task_activity_codes,
        "task_financials": task_financials,
        "calendars": calendars,
        "resources": resources,
        "activity_codes": activity_codes,
    }


def _canonical_json_bytes(obj: Any) -> bytes:
    """Serialize obj to canonical JSON bytes per ADR-0014."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        default=_canonical_default,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _canonical_default(obj: Any) -> Any:
    """Handle types that ``json.dumps`` doesn't know by default.

    ``datetime`` is the only supported extension. Any other non-JSON type
    raises ``TypeError`` — intentional, signalling that a new parser type
    landed and the canonicalizer must be updated via ADR-0015 (algorithm
    drift without a superseding ADR is forbidden).
    """
    if isinstance(obj, datetime):
        return obj.isoformat(timespec="microseconds")
    raise TypeError(
        f"Cannot canonicalize {type(obj).__name__} in input_hash (ADR-0014). "
        "If a new ParsedSchedule type is introduced, author ADR-0015 and update "
        "this helper plus the backfill worker."
    )
