# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Single-source-of-truth for the package version.

Per `ADR-0014 §"Decision Outcome"`_ row 44 (the `engine_version`
provenance contract):

    | engine_version | TEXT NOT NULL | Source: src/__about__.py::__version__. |

Closes the multi-cycle drift documented in:

- `AUDIT-2026-04-26-011 (P2)`_ — file ``src/__about__.py`` had never
  existed since ADR-0014 was accepted on 2026-04-18; the contract was
  non-implementable as-written.
- `AUDIT-2026-04-26-007 (P2)`_ — ``_ENGINE_VERSION`` was hardcoded as
  ``"4.0"`` in ``src/materializer/runtime.py:54``, drifting from
  pyproject.toml's package version every release.

Sourcing chain:

1. ``pyproject.toml [project] version = "X.Y.Z"`` is the canonical
   editable source (build-time / packaging convention).
2. ``src/__about__.py::__version__`` mirrors that string as a literal
   (runtime / forensic-provenance convention).
3. ``src/materializer/runtime.py::_ENGINE_VERSION`` re-imports it.
4. ``src/materializer/backfill.py`` and
   ``src/api/routers/lifecycle.py`` consume from
   ``src.materializer.runtime`` (already wired pre-W4 — see
   ``LESSONS_LEARNED.md`` Cycle 2 close-arc on the engine_version dedup).

**Why a literal and not** ``importlib.metadata.version("meridianiq")``:

The materializer writes ``engine_version`` to forensic-provenance rows
in ``schedule_derived_artifacts`` (``UNIQUE NULLS NOT DISTINCT``
constraint per ADR-0014 §"Decision Outcome"). The provenance value
MUST be deterministic across CI and production, regardless of whether
the package is installed via ``pip install -e .``, a wheel, or run
from source-tree. ``importlib.metadata`` returns whatever the
distribution metadata says, which can drift from ``pyproject.toml``
when the editable install pre-dates a version bump (incident-level
evidence is anecdotal; the structural argument is: forensic provenance
needs a deterministic canonical source independent of install state).

``src/api/app.py`` uses ``importlib.metadata`` for its own release-tag
lookup (Sentry telemetry, ``/health`` endpoint) — that's correct for
*observability* (we want to know what was actually deployed). For
*forensic provenance* we need the canonical source.

**Bump procedure (release engineering)**:

1. Bump ``pyproject.toml [project.version]`` to the new ``X.Y.Z``.
2. Bump ``__version__`` below to the same string in the same commit.
3. Re-materialize derived artifacts per `ADR-0014`_ provenance contract.

Step 2 is intentional defensive duplication. The regression test in
``tests/test_engine_version_source.py`` asserts that ``__version__``
here equals ``pyproject.toml [project.version]`` so a half-bumped
commit fails CI loud.

Step 3 is the operator hand-off that closes the multi-cycle drift
surfaced by W4. **It is NOT optional** — `src/database/store.py
get_latest_derived_artifact` does an exact ``engine_version`` equality
match, so pre-existing artifact rows written under the OLD version
become **invisible to the read path** (not "stale-but-readable") the
moment a bump merges. Consumer endpoints will see ``None`` and trigger
re-mat on first read of every affected project. This is intentional
per ADR-0014 (version mismatch → forced re-mat), but it means a deploy
of a version-bump WITHOUT a coordinated re-mat plan produces a brief
window of blank dashboards. The bump procedure should always be
deploy-coordinated with a bulk re-mat or a tombstone migration on the
old rows.

.. _ADR-0014 §"Decision Outcome": ../docs/adr/0014-derived-artifact-provenance-hash.md#decision-outcome
.. _AUDIT-2026-04-26-011 (P2): ../docs/audit/2026-04-26/02-architecture.md#audit-2026-04-26-011
.. _AUDIT-2026-04-26-007 (P2): ../docs/audit/2026-04-26/02-architecture.md#audit-2026-04-26-007
.. _ADR-0014: ../docs/adr/0014-derived-artifact-provenance-hash.md
"""

from __future__ import annotations

__version__: str = "4.3.0"
# Re-exported by ``src/materializer/runtime.py::_ENGINE_VERSION``. MUST
# equal ``pyproject.toml [project.version]`` — pinned by
# ``tests/test_engine_version_source.py::TestAboutVersionMatchesPyproject``.
# Bound at module import time.
#
# Verifying dynamic sourcing (engine consumers picking up __version__):
# see ``tests/test_engine_version_source.py`` AST-based pattern.
# ``importlib.reload`` was tried first and rejected — reloading the
# materializer runtime re-defines ``JobHandle`` which breaks
# ``isinstance`` checks downstream
# (``test_materializer_runtime.py::TestEnqueueBehaviour``).
