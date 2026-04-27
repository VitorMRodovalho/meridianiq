# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Rate-limit policy regression — Cycle 3 #45 / AUDIT-2026-04-26-005.

Pins the rate-limit policy contract per [ADR-0019 Amendment 1](
docs/adr/0019-cycle-2-entry-consolidation-primitive.md). The buckets
already exist in ``src/api/deps.py:138-140``:

- ``RATE_LIMIT_EXPENSIVE = "3/minute"``
- ``RATE_LIMIT_MODERATE = "10/minute"``
- ``RATE_LIMIT_READ = "30/minute"``

The pre-PR-#45 gap was *enforcement*, not buckets — engines were limited
ad-hoc with literal strings (`"5/minute"`, `"10/minute"`, `"60/minute"`)
instead of the constants, and ~18 write endpoints had NO decorator at
all. This test enforces the policy moving forward.

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

ROUTERS_DIR = Path(__file__).parent.parent / "src" / "api" / "routers"

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
    # Admin endpoints — admin-scope auth-gated; auth IS the throttle.
    # The `require_admin` dependency rejects non-admin requests at the
    # router-deps layer; rate-limiting on top would be redundant.
    ("admin", "revoke_api_key_endpoint"): "admin-scope auth gated",
    ("admin", "delete_user_data"): "admin-scope auth gated; LGPD/GDPR right-to-erasure",
    ("admin", "reconcile_ips"): "admin-scope auth gated; manual reconciliation operation",
    ("admin", "validate_recovery"): "admin-scope auth gated; recovery validation tool",
    # ─────────────────────────────────────────────────────────────────
    # Deferred — request parameter collision with Pydantic body model.
    # ─────────────────────────────────────────────────────────────────
    # These endpoints take a Pydantic body parameter named `request: SomeRequest`,
    # which collides with the FastAPI `request: Request` slowapi requires.
    # Adding the decorator requires renaming `request: <Pydantic>` →
    # `body: <Pydantic>` AND adding a separate `request: Request` parameter.
    # The rename is mechanically safe (FastAPI auto-detects body via type
    # annotation, parameter name is irrelevant for routing) but touches every
    # call-site and benefits from focused review. Tracked as #45 follow-up.
    (
        "analysis",
        "contract_check",
    ): "deferred — request: ContractCheckRequest body collision; #45 follow-up",
    (
        "forensics",
        "create_timeline",
    ): "deferred — request: CreateTimelineRequest body collision; #45 follow-up",
    (
        "schedule_ops",
        "build_schedule_endpoint",
    ): "deferred — request: dict body collision; #45 follow-up",
    ("whatif", "run_what_if"): "deferred — request: WhatIfRequest body collision; #45 follow-up",
    (
        "whatif",
        "run_pareto_analysis",
    ): "deferred — request: ParetoRequest body collision; #45 follow-up",
    (
        "whatif",
        "run_resource_leveling",
    ): "deferred — request: LevelingRequest body collision; #45 follow-up",
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

    @property
    def is_write(self) -> bool:
        return self.method in {"POST", "PUT", "PATCH", "DELETE"}

    @property
    def has_limiter(self) -> bool:
        return any("limiter.limit" in d for d in self.decorators)

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
        """True if the rate-limit is ``RATE_LIMIT_EXPENSIVE`` or a string ≤ 5/minute."""
        v = self.limiter_value
        if v is None:
            return False
        if v == "RATE_LIMIT_EXPENSIVE":
            return True
        # Literal string form: '"N/minute"' OR "'N/minute'" (ast.unparse may emit either).
        m = re.search(r"""['"](\d+)/minute['"]""", v)
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
        yield Endpoint(
            router=router_path.stem,
            function=node.name,
            method=method,
            path=path or "<unknown>",
            decorators=deco_texts,
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
        assert len(endpoints) == 112, f"Total endpoint count drifted: {len(endpoints)} (was 112)"
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
