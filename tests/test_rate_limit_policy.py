# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Rate-limit policy regression — Cycle 3 #45 / AUDIT-2026-04-26-005.

Pins the rate-limit policy contract per [ADR-0019 Amendment 1](
docs/adr/0019-cycle-2-entry-consolidation-primitive.md). The buckets
live in ``src/api/deps.py``:

- ``RATE_LIMIT_EXPENSIVE = "3/minute"``
- ``RATE_LIMIT_WRITE = "5/minute"``
- ``RATE_LIMIT_MODERATE = "10/minute"``
- ``RATE_LIMIT_ANALYSIS = "20/minute"``
- ``RATE_LIMIT_READ = "30/minute"``
- ``RATE_LIMIT_LIGHT = "60/minute"``

The pre-PR-#45 gap was *enforcement*, not buckets — engines were limited
ad-hoc with literal strings (`"5/minute"`, `"10/minute"`, `"60/minute"`)
instead of the constants, and ~18 write endpoints had NO decorator at
all. PR #45 closed the enforcement gap; the literal-vs-constant cleanup
itself was deferred and closed by N5 (this PR), at which point Rule 2's
``is_expensive_bucket`` was extended to resolve constant names through
``CONSTANT_TO_RATE`` so a future tweak to ``RATE_LIMIT_WRITE`` (e.g.,
"5/minute" → "8/minute") propagates automatically.

## Rules pinned by this file

**Rule 1 — Write coverage.** Every endpoint with HTTP method
``POST/PUT/PATCH/DELETE`` MUST have ``@limiter.limit(...)`` (any value)
UNLESS the endpoint is on the ``APPROVED_EXCEPTIONS`` list with a
documented rationale.

**Rule 2 — Expensive coverage.** Every endpoint whose path OR function
name matches ``EXPENSIVE_PATTERNS`` (Monte Carlo, schedule build,
plugin run, what-if/pareto/leveling, MIP forensic, PDF generation, etc.)
MUST have a rate limit ``≤ 5/minute`` (``RATE_LIMIT_EXPENSIVE`` = 3/min
is preferred; literals ``"3/minute"``, ``"4/minute"``, ``"5/minute"``
also accepted).

**Rule 3 — Exception discipline.** Any addition to ``APPROVED_EXCEPTIONS``
requires a rationale comment in this file. Reviewers should challenge
the rationale on PR.

**Rule 4 — Slowapi Request parameter.** Every endpoint with
``@limiter.limit(...)`` MUST have a parameter typed as ``Request`` (the
starlette/fastapi class). Slowapi extracts the client IP from this
parameter; without one the decorator silently no-ops or raises at
runtime — Rules 1+2 pass while the endpoint is unrate-limited in
production. Added by [#57](
https://github.com/VitorMRodovalho/meridianiq/issues/57) after a DA
exit-council found 3 silent-failure cases.

## What this test does NOT enforce

- Constant-vs-literal preference (advisory only — both forms count as
  rate-limited). A future PR may convert all literals to constants;
  not in scope of #45.
- READ endpoints (``GET``) are NOT required to have a rate-limit.
  Reads on user-owned data are throttled at the per-user-auth surface.
  Adding `RATE_LIMIT_READ` to GETs is a future improvement.
- Healthchecks (``/health``, ``/api/v1/health``) — these are GETs and
  trivially excluded by the GET-not-checked rule.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from src.api.deps import (
    RATE_LIMIT_ANALYSIS,
    RATE_LIMIT_EXPENSIVE,
    RATE_LIMIT_LIGHT,
    RATE_LIMIT_MODERATE,
    RATE_LIMIT_READ,
    RATE_LIMIT_WRITE,
)

ROUTERS_DIR = Path(__file__).parent.parent / "src" / "api" / "routers"

# Constant-name → rate-string lookup.  Imported from ``src.api.deps`` so a
# future rate-value tweak (e.g., ``RATE_LIMIT_WRITE`` "5/minute" → "8/minute")
# is automatically reflected in ``Endpoint.is_expensive_bucket`` evaluation
# without a test edit.  The router AST scan extracts the *name* from the
# decorator (``@limiter.limit(RATE_LIMIT_WRITE)``), and Rule 2 needs the
# underlying rate string to compare against the ≤5/minute threshold.
CONSTANT_TO_RATE: dict[str, str] = {
    "RATE_LIMIT_ANALYSIS": RATE_LIMIT_ANALYSIS,
    "RATE_LIMIT_EXPENSIVE": RATE_LIMIT_EXPENSIVE,
    "RATE_LIMIT_LIGHT": RATE_LIMIT_LIGHT,
    "RATE_LIMIT_MODERATE": RATE_LIMIT_MODERATE,
    "RATE_LIMIT_READ": RATE_LIMIT_READ,
    "RATE_LIMIT_WRITE": RATE_LIMIT_WRITE,
}

# Patterns that mark an endpoint as EXPENSIVE-class (must have rate ≤ 5/minute).
# Lowercased substring match against `<path> <function_name>`.
#
# Narrowed (post-DA-review consideration): excludes broad "forensic" because
# the maintainer chose RATE_LIMIT_MODERATE (10/min) for MIP analyses — they
# are heavy but not Monte-Carlo-class. Excludes broad "simulate" because that
# would require renaming function-name patterns; the explicit path
# "/risk/simulate" + "/what-if" cover the actual EXPENSIVE simulators.
EXPENSIVE_PATTERNS: tuple[str, ...] = (
    "monte_carlo",
    "/risk/simulate",  # Monte Carlo QSRA
    "generate_pdf",
    "generate_report",  # WeasyPrint PDF generation
    "/optimize",  # evolution_optimizer (genetic)
    "/pareto",  # pareto search
    "/resource-leveling",  # resource leveling solver
    "/schedule/build",  # CPM build from scratch
    "/plugins/",  # untrusted plugin run (even sandboxed)
    "/what-if",  # what-if simulation
)

# Endpoints intentionally without rate-limit decorators.
#
# Each entry MUST have a one-line rationale comment. Reviewers should
# challenge the rationale on PR — additions to this list are rare.
#
# Format: (router_module_name, function_name): rationale
APPROVED_EXCEPTIONS: dict[tuple[str, str], str] = {
    # ─────────────────────────────────────────────────────────────────
    # User self-action endpoints — `require_auth`-gated (any logged-in
    # user). Auth subsystem rate-limits per-JWT; explicit @limiter on
    # top would be defensive duplicate protection. The narrow surface
    # (one user touching their own data) is acceptable without rate-
    # limit. Was incorrectly labeled "admin-scope auth gated" pre-DA-
    # review; corrected per AUDIT-2026-04-26-005 follow-up.
    # ─────────────────────────────────────────────────────────────────
    ("admin", "revoke_api_key_endpoint"): (
        "require_auth gated; user revokes own key (per-JWT auth-throttled)"
    ),
    ("admin", "delete_user_data"): (
        "require_auth gated; LGPD/GDPR right-to-erasure (per-JWT auth-throttled)"
    ),
    # NOTE: `reconcile_ips` and `validate_recovery` are NOT in this list.
    # DA-review caught: both use `optional_auth` (anonymous-callable!) +
    # are compute-heavy (IPSReconciler, RecoveryValidator). They MUST
    # have `@limiter.limit(RATE_LIMIT_EXPENSIVE)` — applied in
    # `src/api/routers/admin.py` per the DA-review fix-up commit.
    # ─────────────────────────────────────────────────────────────────
    # NOTE: the 6 `request: <Pydantic>` body-collision endpoints
    # (analysis.contract_check, forensics.create_timeline,
    # schedule_ops.build_schedule_endpoint, whatif.run_what_if /
    # run_pareto_analysis / run_resource_leveling) were closed by #57:
    # renamed to `body: <Pydantic>` + added `request: Request` first
    # parameter + decorated with the appropriate bucket
    # (RATE_LIMIT_MODERATE for the two non-EXPENSIVE-pattern endpoints,
    # RATE_LIMIT_EXPENSIVE for the four EXPENSIVE-pattern ones).
    # ─────────────────────────────────────────────────────────────────
}


@dataclass(frozen=True)
class Endpoint:
    """One router endpoint with its decorator metadata."""

    router: str
    """Router module name (e.g., ``"risk"``, ``"forensics"``)."""

    function: str
    """Decorated function name."""

    method: str
    """HTTP verb, uppercased: ``GET / POST / PUT / PATCH / DELETE / WEBSOCKET``."""

    path: str
    """First-arg path string (e.g., ``"/api/v1/risk/simulate/{project_id}"``)."""

    decorators: tuple[str, ...]
    """All decorator source-text strings on the function."""

    param_annotations: tuple[str, ...]
    """Parameter type annotations as source text, parameter order preserved.

    Empty string for parameters without an annotation. Used by Rule 4 to
    detect whether a slowapi-decorated function has a ``Request``-typed
    parameter (slowapi needs one to extract the client IP).
    """

    @property
    def is_write(self) -> bool:
        return self.method in {"POST", "PUT", "PATCH", "DELETE"}

    @property
    def has_limiter(self) -> bool:
        return any("limiter.limit" in d for d in self.decorators)

    @property
    def has_request_param(self) -> bool:
        """True if any parameter is typed as a starlette/fastapi ``Request``.

        Slowapi's ``@limiter.limit`` decorator requires a ``Request`` instance
        to extract the client IP (or whichever key_func the limiter is bound
        to). Without one, the decorator either silently no-ops or raises at
        runtime — both failure modes are invisible to the AST-only Rule 1
        check.

        Accepts the bare ``Request`` annotation as well as the dotted
        ``fastapi.Request`` / ``starlette.requests.Request`` forms.
        """
        for ann in self.param_annotations:
            if not ann:
                continue
            tail = ann.split(".")[-1]
            if tail == "Request":
                return True
        return False

    @property
    def is_expensive_match(self) -> bool:
        haystack = f"{self.path} {self.function}".lower()
        return any(p in haystack for p in EXPENSIVE_PATTERNS)

    @property
    def limiter_value(self) -> str | None:
        """Return the inner argument of ``@limiter.limit(...)`` if present.

        Examples:
            ``@limiter.limit(RATE_LIMIT_EXPENSIVE)`` → ``"RATE_LIMIT_EXPENSIVE"``
            ``@limiter.limit("3/minute")`` → ``'"3/minute"'``
        """
        for d in self.decorators:
            m = re.search(r"limiter\.limit\(\s*(.+?)\s*\)", d)
            if m:
                return m.group(1).strip()
        return None

    @property
    def is_expensive_bucket(self) -> bool:
        """True if the rate-limit resolves to a string ≤ 5/minute.

        Accepts both the constant-name form (``RATE_LIMIT_EXPENSIVE`` /
        ``RATE_LIMIT_WRITE`` resolve to "3/minute" / "5/minute" via
        ``CONSTANT_TO_RATE``) and the literal-string form (``"3/minute"``
        through ``"5/minute"``).  The literal-string branch survives so an
        ad-hoc decorator authored before N5's sweep — and the documented
        ``whatif.optimize_schedule_endpoint`` exception held at literal
        ``"5/minute"`` per ADR-0019 Amendment 1 line 389 — doesn't
        false-fail the rule.
        """
        v = self.limiter_value
        if v is None:
            return False
        # Normalise dotted-name access (e.g., ``deps.RATE_LIMIT_WRITE``) so
        # the lookup hits regardless of import style.  Bare names pass
        # through unchanged; literal-string forms (which contain ``/``)
        # rsplit harmlessly.
        key = v.rsplit(".", 1)[-1]
        # Resolve constant name to its rate string when applicable so a
        # rate tweak in deps.py (e.g., RATE_LIMIT_WRITE "5/minute" → "8/minute")
        # propagates without a test edit.  Unknown identifiers fall through
        # to the literal regex (covers both stale and ad-hoc cases).
        rate_str = CONSTANT_TO_RATE.get(key, v)
        # Strip enclosing quotes from the literal-string form (ast.unparse
        # may emit '"5/minute"' or "'5/minute'") and require an exact match
        # against ``<digits>/minute``.  ``fullmatch`` rejects anything with
        # extra suffixes (e.g., a hypothetical ``"3/minute_per_user"``
        # custom format) that ``search`` would silently green-light.
        stripped = rate_str.strip("\"'")
        m = re.fullmatch(r"(\d+)/minute", stripped)
        if m:
            return int(m.group(1)) <= 5
        return False


def _extract_endpoints(router_path: Path) -> Iterable[Endpoint]:
    """Walk a router file's AST and yield every decorated endpoint."""
    src = router_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        deco_texts = tuple(ast.unparse(d) for d in node.decorator_list)
        method: str | None = None
        path: str | None = None
        for d_text in deco_texts:
            for verb in ("get", "post", "put", "patch", "delete", "websocket"):
                if d_text.startswith(f"router.{verb}("):
                    method = verb.upper()
                    break
            if method:
                # Extract path string (first positional arg).
                m = re.search(r'router\.\w+\(\s*["\']([^"\']+)["\']', d_text)
                if m:
                    path = m.group(1)
                break
        if method is None:
            continue
        # Capture parameter annotations (positional + keyword-only) so Rule 4
        # can detect Request-typed parameters. Empty string for unannotated
        # parameters (we currently don't have any in routers, but defensive).
        params: list[str] = []
        for arg in (*node.args.args, *node.args.kwonlyargs):
            params.append(ast.unparse(arg.annotation) if arg.annotation else "")
        yield Endpoint(
            router=router_path.stem,
            function=node.name,
            method=method,
            path=path or "<unknown>",
            decorators=deco_texts,
            param_annotations=tuple(params),
        )


def _all_endpoints() -> list[Endpoint]:
    """Collect every router endpoint in ``src/api/routers/``."""
    endpoints: list[Endpoint] = []
    for router_path in sorted(ROUTERS_DIR.glob("*.py")):
        if router_path.name == "__init__.py":
            continue
        endpoints.extend(_extract_endpoints(router_path))
    return endpoints


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


class TestRule1WriteCoverage:
    """Every POST/PUT/PATCH/DELETE endpoint MUST have ``@limiter.limit(...)``
    UNLESS in ``APPROVED_EXCEPTIONS``."""

    def test_every_write_endpoint_is_rate_limited_or_excepted(self) -> None:
        violations: list[str] = []
        for ep in _all_endpoints():
            if not ep.is_write:
                continue
            if (ep.router, ep.function) in APPROVED_EXCEPTIONS:
                continue
            if not ep.has_limiter:
                violations.append(
                    f"{ep.router}.{ep.function}() {ep.method} {ep.path} — "
                    "missing @limiter.limit(...)"
                )
        assert not violations, (
            "Rate-limit policy violation (Rule 1: write coverage). "
            "Each violation below is a write endpoint without "
            "@limiter.limit(...) and not in APPROVED_EXCEPTIONS:\n  - "
            + "\n  - ".join(violations)
            + "\n\nFix: either decorate with @limiter.limit(RATE_LIMIT_MODERATE) "
            "(or other bucket) OR add to APPROVED_EXCEPTIONS in this test "
            "file with a one-line rationale."
        )


class TestRule2ExpensiveCoverage:
    """Every endpoint matching EXPENSIVE_PATTERNS MUST have a rate-limit
    ≤ 5/minute (RATE_LIMIT_EXPENSIVE or literal '3'-'5'/minute)."""

    def test_every_expensive_endpoint_uses_expensive_bucket(self) -> None:
        violations: list[str] = []
        for ep in _all_endpoints():
            if not ep.is_expensive_match:
                continue
            # GET endpoints excluded from this rule (read-class endpoints
            # never reach the expensive bucket; the expensive cost lives in
            # the underlying analyses, not the response generation).
            if ep.method == "GET":
                continue
            # APPROVED_EXCEPTIONS bypass both Rule 1 and Rule 2.
            # Deferred-collision cases rely on Rule 1's exception path
            # to keep the test passing while the rename is in flight.
            if (ep.router, ep.function) in APPROVED_EXCEPTIONS:
                continue
            if not ep.has_limiter:
                violations.append(
                    f"{ep.router}.{ep.function}() {ep.method} {ep.path} — "
                    "EXPENSIVE pattern match WITHOUT @limiter.limit"
                )
                continue
            if not ep.is_expensive_bucket:
                violations.append(
                    f"{ep.router}.{ep.function}() {ep.method} {ep.path} — "
                    f"EXPENSIVE pattern match but rate is "
                    f"{ep.limiter_value!r} (must be RATE_LIMIT_EXPENSIVE "
                    "or string ≤ 5/minute)"
                )
        assert not violations, (
            "Rate-limit policy violation (Rule 2: expensive coverage). "
            "Each violation below is an EXPENSIVE-class endpoint not "
            "rate-limited at the expensive bucket:\n  - "
            + "\n  - ".join(violations)
            + "\n\nFix: decorate with @limiter.limit(RATE_LIMIT_EXPENSIVE). "
            "If the endpoint is genuinely not expensive (false-positive on "
            "the pattern matcher), refine EXPENSIVE_PATTERNS in this file."
        )


class TestRule3ExceptionDiscipline:
    """Every entry in APPROVED_EXCEPTIONS MUST have a non-empty rationale.
    Reviewers should challenge rationales on PR."""

    def test_all_exceptions_have_rationale(self) -> None:
        for (router, fn), rationale in APPROVED_EXCEPTIONS.items():
            assert rationale and rationale.strip(), (
                f"APPROVED_EXCEPTIONS[({router!r}, {fn!r})] has empty "
                "rationale. Add a one-line justification."
            )

    def test_exception_endpoints_actually_exist(self) -> None:
        """An exception for a router/function that doesn't exist is
        dead weight — would silently allow other unintended write
        endpoints to slip through if a refactor renamed."""
        all_ep = {(ep.router, ep.function) for ep in _all_endpoints()}
        for key in APPROVED_EXCEPTIONS:
            assert key in all_ep, (
                f"APPROVED_EXCEPTIONS contains {key} but no such "
                "(router, function) pair exists in src/api/routers/. "
                "Either remove the dead entry or fix the typo."
            )


class TestRule4SlowapiRequestParam:
    """Every endpoint with ``@limiter.limit`` MUST have a parameter typed
    as ``Request`` (slowapi extracts the client IP from it).

    This rule was added by [#57](
    https://github.com/VitorMRodovalho/meridianiq/issues/57) after a DA
    exit-council found 3 endpoints (``comparison.compare_schedules``,
    ``tia.tia_analyze``, ``schedule_ops.generate_schedule_endpoint``)
    with ``@limiter.limit`` decorators but no ``Request``-typed parameter.
    Rules 1+2+3 are AST-decorator-presence checks — they cannot detect this
    runtime failure class. Rule 4 closes the structural gap.
    """

    def test_every_limited_endpoint_has_request_param(self) -> None:
        violations: list[str] = []
        for ep in _all_endpoints():
            if not ep.has_limiter:
                continue
            if not ep.has_request_param:
                violations.append(
                    f"{ep.router}.{ep.function}() {ep.method} {ep.path} — "
                    "@limiter.limit without a Request-typed parameter"
                )
        assert not violations, (
            "Rate-limit policy violation (Rule 4: slowapi Request param). "
            "Each violation below has @limiter.limit but no parameter typed "
            "as starlette/fastapi Request. Slowapi cannot extract the client "
            "IP — the decorator silently no-ops or raises at runtime, so "
            "Rules 1+2 pass while the endpoint is unrate-limited in production:\n  - "
            + "\n  - ".join(violations)
            + "\n\nFix: add `request: Request` (or `_http_request: Request` "
            "if a Pydantic body parameter is named `request`) to the function "
            "signature, and ensure `from fastapi import Request` is imported."
        )


class TestPolicyMatrixSnapshot:
    """Pin the current state of the rate-limit policy matrix.

    This snapshot tracks how many endpoints fall into each category.
    A drift here is informational — the test fails LOUD on a snapshot
    bump so PR reviewers can confirm the change is intentional (e.g.,
    a new EXPENSIVE endpoint added a write-with-limit, or a refactor
    removed an endpoint).
    """

    def test_endpoint_counts_pinned(self) -> None:
        endpoints = _all_endpoints()
        write_with_limit = 0
        write_total = 0
        for ep in endpoints:
            if ep.is_write:
                write_total += 1
                if ep.has_limiter:
                    write_with_limit += 1
        # Pin current state — bump deliberately when adding endpoints.
        # If a future refactor changes these numbers without an obvious
        # cause, the test points at where to look.
        # Floor (not exact-equality) — adding a new endpoint passes if a write
        # is properly Rule-1-decorated; new GETs never break this assertion.
        # The 112 number is a low-watermark from 2026-04-27.
        assert len(endpoints) >= 112, (
            f"Total endpoint count {len(endpoints)} fell below floor (112). "
            "Did a router file get deleted?"
        )
        assert write_total >= 30, f"Write endpoint count {write_total} below floor (30)"
        # After #45 fix-up: every write is either limited or excepted.
        excepted_writes = sum(
            1 for ep in endpoints if ep.is_write and (ep.router, ep.function) in APPROVED_EXCEPTIONS
        )
        assert write_with_limit + excepted_writes == write_total, (
            f"write_with_limit ({write_with_limit}) + excepted "
            f"({excepted_writes}) = {write_with_limit + excepted_writes} "
            f"!= write_total ({write_total}). Some write endpoint slipped "
            "through both Rule 1 and the exception list."
        )
