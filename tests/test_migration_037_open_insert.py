# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""No surviving policy lets a client write any row it likes.

Migration 011 created two INSERT policies with ``WITH CHECK (TRUE)`` (on
``alerts`` and ``health_scores``), and they were live in production on
2026-10-09. Migration 037 drops them. The ratchet replays every migration
and fails on any surviving INSERT/UPDATE/ALL policy whose check is ``true``;
the control replays the files before 037 and must find the two.
"""

from __future__ import annotations

import re

from tests.test_migration_034_org_rls import MIGRATIONS, Policy, _files, _replay

MEASURED_OPEN = {
    ("alerts", "Users insert own alerts"),
    ("health_scores", "Users insert own health_scores"),
}


def _open_writes(state: dict[tuple[str, str], Policy]) -> set[tuple[str, str]]:
    return {
        key
        for key, pol in state.items()
        if pol.cmd in {"insert", "update", "all"}
        and re.search(r"\bwith\s+check\s*\(\s*true\s*\)", pol.body)
    }


def test_no_write_policy_checks_true_after_037() -> None:
    assert _open_writes(_replay(sorted(MIGRATIONS.glob("*.sql")))) == set()


def test_negative_control_finds_the_measured_policies_before_037() -> None:
    assert _open_writes(_replay(_files("037_"))) == MEASURED_OPEN
