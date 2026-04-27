# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Regression: ``_ENGINE_VERSION`` sources from ``src/__about__.py`` per ADR-0014.

Cycle 3 W4 deliverable per ADR-0021 §"Wave plan" W4. Closes:

- `AUDIT-2026-04-26-007 (P2)`_ — ``_ENGINE_VERSION`` had been hardcoded
  as ``"4.0"`` in ``src/materializer/runtime.py:54`` for multiple
  cycles, drifting from ``pyproject.toml`` every release. The
  consequence in production: 88 derived-artifact rows would silently
  carry ``engine_version="4.0"`` while the actual engine is ``4.1.0``
  — provenance violation per ADR-0014 §"Decision Outcome" UNIQUE
  constraint.
- `AUDIT-2026-04-26-011 (P2)`_ — ``src/__about__.py`` had never
  existed since ADR-0014 was accepted on 2026-04-18; the contract was
  non-implementable as written.

What this test pins:

1. ``src/__about__.py::__version__`` matches ``pyproject.toml
   [project.version]`` — protects against half-bumped commits where a
   contributor edits one but not the other.
2. ``src/materializer/runtime.py::_ENGINE_VERSION`` equals
   ``__about__.__version__`` at module-load time — basic equality.
3. AST inspection of ``runtime.py`` confirms the literal
   ``from src.__about__ import __version__`` import (any alias OK)
   exists — catches a future refactor that re-introduces a hardcoded
   literal coincidentally matching today's pyproject value (``importlib.reload``
   was tried first but broke test isolation by re-defining ``JobHandle``,
   regressing downstream ``isinstance`` checks).
4. ``__about__.__version__`` is a non-empty string — minimal sanity.
5. End-to-end transitive: ``runtime._ENGINE_VERSION`` matches
   ``pyproject.toml [project.version]`` — belt-and-suspenders against
   a chain split where each link individually passes.

Companion to `tests/test_materializer_runtime.py::TestEngineVersionSingleSource`
which pins the *consumer* side of the chain (backfill + lifecycle
router read from ``runtime._ENGINE_VERSION`` at call time, not from a
captured literal). Together those two test files form the structural
sourcing contract:

    pyproject.toml → __about__.__version__ → runtime._ENGINE_VERSION → consumers

A drift at any link in the chain breaks loud.

.. _AUDIT-2026-04-26-007 (P2): ../docs/audit/2026-04-26/02-architecture.md#audit-2026-04-26-007
.. _AUDIT-2026-04-26-011 (P2): ../docs/audit/2026-04-26/02-architecture.md#audit-2026-04-26-011
"""

from __future__ import annotations

import ast
import inspect
import tomllib
from pathlib import Path

# Path to repo root — tests run from there via pytest.
REPO_ROOT = Path(__file__).parent.parent
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"


def _read_pyproject_version() -> str:
    """Read the canonical version from ``pyproject.toml``."""
    with open(PYPROJECT_TOML, "rb") as f:
        pyproject = tomllib.load(f)
    project_version: str = pyproject["project"]["version"]
    return project_version


class TestAboutVersionMatchesPyproject:
    """``src/__about__.py::__version__`` MUST equal
    ``pyproject.toml [project.version]``.

    The duplication is intentional defensive bookkeeping (see
    ``__about__.py`` docstring "Bump procedure" section). This test
    is the enforcement: a half-bumped commit fails CI."""

    def test_about_version_matches_pyproject_toml(self) -> None:
        from src.__about__ import __version__

        pyproject_version = _read_pyproject_version()
        assert __version__ == pyproject_version, (
            f"src/__about__.py::__version__ ({__version__!r}) drifted from "
            f"pyproject.toml [project.version] ({pyproject_version!r}). "
            "Bump both together — see __about__.py docstring 'Bump procedure'."
        )

    def test_about_version_is_nonempty_string(self) -> None:
        from src.__about__ import __version__

        assert isinstance(__version__, str), "__version__ must be a string"
        assert __version__, "__version__ must be non-empty"
        # Sanity: a 'X.Y.Z' shape (loose check — accepts anything dotted).
        parts = __version__.split(".")
        assert len(parts) >= 2, (
            f"__version__={__version__!r} does not look like a SemVer or PEP 440 version."
        )


class TestEngineVersionSourcesFromAbout:
    """``src/materializer/runtime.py::_ENGINE_VERSION`` MUST source from
    ``src/__about__.py::__version__``. Pre-Cycle-3-W4 it was hardcoded
    as ``"4.0"``; the W4 wave migrated to dynamic sourcing per ADR-0014
    §"Decision Outcome" line 44."""

    def test_engine_version_equals_about_version_at_import(self) -> None:
        """Basic equality: import both, assert equality. Catches the
        most common drift (someone re-introduces a literal in
        runtime.py)."""
        from src.__about__ import __version__
        from src.materializer.runtime import _ENGINE_VERSION

        assert _ENGINE_VERSION == __version__, (
            f"_ENGINE_VERSION ({_ENGINE_VERSION!r}) drifted from "
            f"src/__about__.py::__version__ ({__version__!r}). "
            "Pre-W4 the constant was hardcoded as '4.0'; the W4 wave "
            "migrated to source from __about__ — see ADR-0014 "
            "§'Decision Outcome' line 44."
        )

    def test_runtime_imports_version_from_about_via_ast(self) -> None:
        """AST inspection: ``runtime.py`` MUST contain a top-level
        ``from src.__about__ import __version__`` (any alias OK).

        Proves the binding is via import, not a hardcoded literal that
        coincidentally matches today's pyproject value. A future
        refactor that replaces the import with
        ``_ENGINE_VERSION = "4.1.0"`` (or any literal) would coincide
        with today's pyproject value and
        ``test_engine_version_equals_about_version_at_import`` would
        still pass — but THIS test would fail because the import
        statement wouldn't be there.

        Why AST and not ``importlib.reload``: reload re-defines all
        classes in the runtime module (e.g., ``JobHandle``), breaking
        test isolation for downstream importers
        (``test_materializer_runtime.py::TestEnqueueBehaviour``
        regressed via ``isinstance`` against a stale class). AST
        inspection is read-only — survives any test ordering.

        Why AST and not regex on source text: AST is robust against
        comment changes, alias variations (``import as``), formatting,
        and string interpolation tricks. The Cycle 2 close-arc lesson
        about source-text regression-test smell specifically warned
        against ``grep`` patterns; AST-based imports are explicitly
        the suggested rigorous alternative.
        """
        from src.materializer import runtime

        source = inspect.getsource(runtime)
        tree = ast.parse(source)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "src.__about__":
                if any(alias.name == "__version__" for alias in node.names):
                    found = True
                    break
        assert found, (
            "src/materializer/runtime.py does not import __version__ "
            "from src.__about__ — likely a hardcoded literal. Per "
            "ADR-0014 §'Decision Outcome' line 44, _ENGINE_VERSION "
            "MUST source from src/__about__.py::__version__."
        )


class TestEngineVersionMatchesPyproject:
    """Cross-check: end-to-end the chain pyproject → __about__ → runtime
    delivers the same string. Belt-and-suspenders against the case
    where a refactor splits the chain into branches that all
    individually pass but the end-to-end value is wrong."""

    def test_runtime_engine_version_matches_pyproject_toml(self) -> None:
        from src.materializer.runtime import _ENGINE_VERSION

        pyproject_version = _read_pyproject_version()
        assert _ENGINE_VERSION == pyproject_version, (
            f"runtime._ENGINE_VERSION ({_ENGINE_VERSION!r}) does not "
            f"match pyproject.toml [project.version] "
            f"({pyproject_version!r}). End-to-end sourcing chain is "
            "broken — investigate __about__.py and runtime.py."
        )
