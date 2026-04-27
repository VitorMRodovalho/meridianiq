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
3. AST inspection of ``runtime.py`` confirms BOTH the
   ``from src.__about__ import __version__`` import AND the absence of
   any ``_ENGINE_VERSION = <string-literal>`` assignment. Either alone
   has a hole; both together pin the binding. (``importlib.reload`` was
   tried first but broke test isolation by re-defining ``JobHandle``,
   regressing downstream ``isinstance`` checks.)
4. ``__about__.__version__`` is a non-empty string — minimal sanity.
5. End-to-end transitive: ``runtime._ENGINE_VERSION`` matches
   ``pyproject.toml [project.version]`` — belt-and-suspenders against
   a chain split where each link individually passes.

Companions in the sourcing contract:

- `tests/test_materializer_runtime.py::TestEngineVersionSingleSource`
  pins the *consumer* side of the chain (backfill + lifecycle router
  read from ``runtime._ENGINE_VERSION`` at call time, not from a
  captured literal).
- `tests/test_materializer_runtime.py::TestArtifactContent::test_saved_artifacts_carry_input_hash_and_versions`
  pins the *write* side (``Materializer.materialize()`` actually
  emits ``engine_version=_ENGINE_VERSION`` on saved rows).

Together those test files form the structural sourcing contract:

    pyproject.toml → __about__.__version__ → runtime._ENGINE_VERSION → consumers
                                                                    → save_derived_artifact

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
    """Read the canonical version from ``pyproject.toml``.

    Defensive guard against PEP 621 dynamic versioning: if the project
    ever moves to ``dynamic = ["version"]`` (e.g.,
    ``[tool.setuptools.dynamic] version = {attr = "src.__about__.__version__"}``),
    ``[project.version]`` won't exist and the caller needs an explicit
    handler. This raises a typed error so the test failure points at
    the migration rather than masking it as a generic ``KeyError``."""
    with open(PYPROJECT_TOML, "rb") as f:
        pyproject = tomllib.load(f)
    project = pyproject.get("project", {})
    if "version" not in project:
        raise RuntimeError(
            "pyproject.toml has no static [project.version] — likely PEP 621 "
            "dynamic versioning. Update _read_pyproject_version to fall back "
            "to importlib.metadata.version('meridianiq') OR read the dynamic "
            "config block."
        )
    project_version: str = project["version"]
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

    def test_runtime_does_not_hardcode_engine_version_literal(self) -> None:
        """AST inspection: ``runtime.py`` MUST (a) contain a top-level
        ``from src.__about__ import __version__`` and (b) NOT contain
        any ``_ENGINE_VERSION = <string-literal>`` assignment.

        The two checks together pin the binding. Either alone has a
        gap:

        - Import-only check: a future refactor could write
          ``from src.__about__ import __version__`` AND
          ``_ENGINE_VERSION = "4.1.0"`` (literal, coincidentally matching
          today's pyproject). The import test passes; the binding is wrong.
        - Literal-only check: a future refactor could omit the import
          and bind ``_ENGINE_VERSION`` from somewhere else (e.g.,
          ``importlib.metadata`` directly). The literal check passes;
          the canonical source contract is bypassed.

        Both checks together force the explicit
        ``from src.__about__ import __version__ as _ENGINE_VERSION``
        pattern (or the equivalent two-step ``import`` then ``=``
        binding to the imported name).

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
        against ``grep`` patterns; AST-based parsing is the suggested
        rigorous alternative.
        """
        from src.materializer import runtime

        source = inspect.getsource(runtime)
        tree = ast.parse(source)

        # Check (a): import from src.__about__ must exist.
        import_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "src.__about__":
                if any(alias.name == "__version__" for alias in node.names):
                    import_found = True
                    break
        assert import_found, (
            "src/materializer/runtime.py does not import __version__ "
            "from src.__about__ — likely a hardcoded literal. Per "
            "ADR-0014 §'Decision Outcome' line 44, _ENGINE_VERSION "
            "MUST source from src/__about__.py::__version__."
        )

        # Check (b): no top-level _ENGINE_VERSION = "<literal-string>" assignment.
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_ENGINE_VERSION":
                        if isinstance(node.value, ast.Constant) and isinstance(
                            node.value.value, str
                        ):
                            raise AssertionError(
                                f"Found hardcoded literal "
                                f"_ENGINE_VERSION = {node.value.value!r} at "
                                f"runtime.py:{node.lineno}. The constant MUST "
                                f"come from `from src.__about__ import "
                                f"__version__ as _ENGINE_VERSION` (or via a "
                                f"binding to the imported `__version__` name) "
                                f"per ADR-0014 §'Decision Outcome' line 44."
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
