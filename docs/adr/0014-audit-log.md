# ADR-0014 audit log — re-audits of the canonical `input_hash`

Companion record to [ADR-0014](0014-derived-artifact-provenance-hash.md). ADRs are immutable once accepted (see the [index](README.md)), so the history of re-audits lives here rather than inside ADR-0014.

ADR-0014 makes `compute_input_hash` a forensic contract: a stored derived artifact is found again only if the same input hashes to the same bytes. The hash is computed over pydantic serialization, so a change in how pydantic serializes, or in the runtime under it, can move every digest and orphan the stored rows. That is why `pydantic` carries a minor-level cap (`tests/test_dependency_caps.py`), and why each floor or cap move is audited before it lands.

## Procedure

1. In a clean environment with the project's `dev` extra, install the target pydantic version and the pydantic-core it pins.
2. Run `python -m pytest tests/test_canonical_hash.py -v`. It covers six classes: `TestDeterminism`, `TestProjectScoping`, `TestContentSensitivity`, `TestChainFilters`, `TestCanonicalJsonRules` and `TestByteExactPin`.
3. Every test must pass, and the two `TestByteExactPin` digests (the minimal and the rich fixture) must be unchanged. The digests are the contract; the other classes check the properties the contract relies on.
4. Only then move the bound in `pyproject.toml`, update the cap string in `tests/test_dependency_caps.py` (#245), and add a row below.
5. If either digest changes, do not merge. Stored `input_hash` values would stop matching. ADR-0014 forbids algorithm drift without a superseding ADR. The pin's docstring asks for that ADR plus a full-table backfill worker before the change merges. (ADR-0014 names the successor "ADR-0015"; that number has since been used for the async materializer, so the successor takes the next free number.)

## Audits

| Date | pydantic | Result | Change |
|---|---|---|---|
| 2026-04-26 | floor 2.13 | `TestByteExactPin`: both fixtures held | `ed74420` |
| 2026-05-17 | floor 2.13.4, cap `<2.14` | 28/28 across the six classes. No `RootModel` in `src/`, so the 2.13.4 `RootModel` change does not apply | #137 |
| 2026-10-30 | floor 2.14.2 (pydantic-core 2.50.2), cap widened to `<2.15` | 28/28, both `TestByteExactPin` digests unchanged | #327 |

## Runtime changes checked against the same tests

The digests also depend on the Python runtime under pydantic, for example through `json` and float formatting.

| Date | Change | Result | Change |
|---|---|---|---|
| 2026-10-31 | CI and the API image move to Python 3.15 | full suite, including the 28, passes on 3.15 | #342 |
| 2026-10-31 | a CI job installs the dependency floors on Python 3.12, the `requires-python` floor | full suite, including the 28, passes on 3.12 | #346 |
