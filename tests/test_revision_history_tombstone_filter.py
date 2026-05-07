# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tombstone-filter regression — Cycle 4 W2 PR-A / ADR-0022 §"AST regression test".

Pins the HB-C contract: every SELECT path on ``revision_history`` MUST
filter ``tombstoned_at IS NULL`` so default reads do not return
tombstoned rows. Migration 028's RLS quadruple SELECT policy enforces
this at the DB layer (``rh_select_own_active``); this test guards
against application-layer drift that could bypass the policy via
service-role credentials (e.g., the materializer or cron writers).

## Scan scope

Recursively scans ``src/`` (excluding ``tests/`` and ``tools/``) for any
reference to ``revision_history`` AND a select-shaped pattern within
the same statement:

- supabase-py client form: ``.table("revision_history").select(...)``
- raw SQL form: ``FROM revision_history`` (case-insensitive)

For each match, asserts a tombstone filter is applied within ~15 lines
of the match — either ``.is_("tombstoned_at", "null")`` for supabase-py
OR ``tombstoned_at IS NULL`` in raw SQL strings.

## Approved exceptions

Call sites that legitimately read tombstoned rows (e.g., admin tooling
opted-in via ``include_tombstoned=True``) belong in
``APPROVED_EXCEPTIONS`` with rationale.

## What this test does NOT enforce

- INSERT and UPDATE on revision_history are not SELECT paths and are
  exempt — the migration's append-only trigger guards UPDATE; the cap
  trigger guards INSERT.
- DELETE policies are validated by ``tests/test_rls_policy.py``.
- Cross-table joins that mention ``revision_history`` only via FK
  (e.g., a JOIN ON projects.id = revision_history.project_id) without
  selecting from revision_history are not flagged here.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "src"

# (file_path_substring, line_anchor_substring, rationale)
APPROVED_EXCEPTIONS: list[tuple[str, str, str]] = [
    (
        "src/database/store.py",
        "include_tombstoned",
        "list_revision_history_by_program supports include_tombstoned=True for "
        "admin tooling (audit / forensic review). The default branch DOES filter; "
        "the include-branch is the explicit opt-in.",
    ),
    (
        "src/database/store.py",
        "Read pre-tombstone state",
        "tombstone_revision MUST read the row's current state including "
        "tombstoned_at to support idempotent re-tombstone — filtering "
        "tombstoned_at IS NULL would make the function unable to detect a "
        "row that's already tombstoned, defeating the idempotency contract.",
    ),
]

_SUPABASE_SELECT_RE = re.compile(
    r'\.table\(\s*[\'"]revision_history[\'"]\s*\)\s*\.select\b',
    re.IGNORECASE,
)
_RAW_SELECT_RE = re.compile(
    r"\bFROM\s+revision_history\b",
    re.IGNORECASE,
)
_TOMBSTONE_FILTER_RE = re.compile(
    r'\.is_\(\s*[\'"]tombstoned_at[\'"]\s*,\s*[\'"]null[\'"]\s*\)|tombstoned_at\s+IS\s+NULL',
    re.IGNORECASE,
)


def _python_files() -> list[Path]:
    return [p for p in SRC_DIR.rglob("*.py") if "__pycache__" not in p.parts]


def _read(path: Path) -> str:
    return path.read_text()


def _has_filter_within_window(text: str, match_start: int, lines_window: int = 15) -> bool:
    """Return True if a tombstone filter regex matches within ``lines_window``
    lines AFTER the SELECT match. Window expressed in newlines from the match.
    """
    end = match_start
    line_count = 0
    while line_count < lines_window and end < len(text):
        end = text.find("\n", end + 1)
        if end == -1:
            end = len(text)
            break
        line_count += 1
    window = text[match_start:end]
    return bool(_TOMBSTONE_FILTER_RE.search(window))


def _is_approved(path: Path, line_text: str) -> tuple[bool, str | None]:
    """Return (approved, rationale-or-None) for the given match."""
    rel = str(path.relative_to(SRC_DIR.parent))
    for path_sub, anchor_sub, rationale in APPROVED_EXCEPTIONS:
        if path_sub in rel and anchor_sub in line_text:
            return True, rationale
    return False, None


def _scan_violations() -> list[tuple[str, int, str, str]]:
    """Return list of (rel_path, line_no, line_text, kind) for non-compliant matches."""
    violations: list[tuple[str, int, str, str]] = []
    for path in _python_files():
        text = _read(path)
        # Don't enforce on tests or tools (excluded above by SRC_DIR).
        # Don't enforce on the test scaffolding for revisions / audit / etc.
        for kind, regex in (
            ("supabase-py", _SUPABASE_SELECT_RE),
            ("raw-sql", _RAW_SELECT_RE),
        ):
            for m in regex.finditer(text):
                if _has_filter_within_window(text, m.start()):
                    continue
                # Get the surrounding line for context + approval check.
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.start())
                if line_end == -1:
                    line_end = len(text)
                line_text = text[line_start:line_end].strip()
                line_no = text[: m.start()].count("\n") + 1
                # Approval check — uses surrounding ~3 lines as anchor context.
                window_start = text.rfind("\n", 0, max(0, m.start() - 200)) + 1
                window_end = text.find("\n", m.end() + 200)
                if window_end == -1:
                    window_end = len(text)
                ctx = text[window_start:window_end]
                approved, _rationale = _is_approved(path, ctx)
                if approved:
                    continue
                rel = str(path.relative_to(SRC_DIR.parent))
                violations.append((rel, line_no, line_text, kind))
    return violations


def test_every_revision_history_select_filters_tombstone() -> None:
    """HB-C contract: every SELECT-shape on revision_history must filter
    ``tombstoned_at IS NULL`` within 15 lines of the match.

    Approved exceptions live in ``APPROVED_EXCEPTIONS`` with rationale.
    """
    violations = _scan_violations()
    if violations:
        bullet = "\n".join(
            f"  - {path}:{line} [{kind}] {text}" for path, line, text, kind in violations
        )
        raise AssertionError(
            "SELECT-shape paths on revision_history without tombstone filter:\n"
            f"{bullet}\n\n"
            "Fix: add ``.is_('tombstoned_at', 'null')`` within 15 lines of the "
            ".table('revision_history').select(...) call OR include "
            "``tombstoned_at IS NULL`` in the WHERE clause of any raw SQL. "
            "Service-role admin tooling that legitimately reads tombstoned "
            "rows belongs in APPROVED_EXCEPTIONS with rationale."
        )


def test_approved_exceptions_have_rationale() -> None:
    """Every entry in APPROVED_EXCEPTIONS must have a non-empty rationale."""
    for path_sub, anchor_sub, rationale in APPROVED_EXCEPTIONS:
        assert rationale.strip(), (
            f"APPROVED_EXCEPTIONS entry ({path_sub}, {anchor_sub}) has empty rationale; "
            "exemptions without rationale are forbidden — they're indistinguishable "
            "from typos at review time."
        )


def test_supabase_select_pattern_matches_known_call() -> None:
    """Sanity: the supabase-py SELECT regex actually matches a call shape.

    Defends against silent regex drift — if the regex stops matching, the
    main test passes vacuously even with violations present.
    """
    sample = '.table("revision_history").select("*")'
    assert _SUPABASE_SELECT_RE.search(sample), (
        "supabase-py SELECT regex no longer matches the canonical call shape; "
        "AST scan would silently miss real violations"
    )


def test_raw_sql_pattern_matches_known_query() -> None:
    """Sanity: the raw SQL regex matches a known FROM clause."""
    sample = "SELECT * FROM revision_history WHERE x = 1"
    assert _RAW_SELECT_RE.search(sample), (
        "raw SQL FROM regex no longer matches the canonical pattern; "
        "AST scan would silently miss real violations"
    )


def test_tombstone_filter_pattern_matches_supabase_form() -> None:
    """Sanity: the tombstone filter regex matches the supabase-py is_() form."""
    sample = '.is_("tombstoned_at", "null")'
    assert _TOMBSTONE_FILTER_RE.search(sample)


def test_tombstone_filter_pattern_matches_raw_sql_form() -> None:
    """Sanity: the tombstone filter regex matches raw SQL ``IS NULL``."""
    sample = "WHERE tombstoned_at IS NULL"
    assert _TOMBSTONE_FILTER_RE.search(sample)
