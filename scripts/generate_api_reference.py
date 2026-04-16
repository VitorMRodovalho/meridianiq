"""Generate docs/api-reference.md from the running FastAPI app.

Introspects ``src.api.app.app`` and writes a Markdown reference grouped
by router.  For each endpoint we emit: HTTP method, path, one-line
summary (first line of docstring), response model name, and auth
requirement.

Usage::

    python3 scripts/generate_api_reference.py

Regenerate whenever endpoints are added, renamed, or removed.  The
output file lives at ``docs/api-reference.md`` and is checked in.
"""

from __future__ import annotations

import inspect
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from fastapi.routing import APIRoute  # noqa: E402

from src.api.app import app  # noqa: E402


def _one_line(docstring: str | None) -> str:
    if not docstring:
        return ""
    return inspect.cleandoc(docstring).splitlines()[0].strip()


def _infer_tag(route: APIRoute) -> str:
    """Infer a router tag from the endpoint module path."""
    endpoint = getattr(route, "endpoint", None)
    if endpoint is None:
        return "misc"
    module = getattr(endpoint, "__module__", "") or ""
    # src.api.routers.<name> → <name>
    parts = module.rsplit(".", 1)
    return parts[-1] if parts else "misc"


def _requires_auth(route: APIRoute) -> str:
    """Best-effort auth check by inspecting dependencies."""
    for dep in route.dependant.dependencies:
        name = getattr(dep.call, "__name__", "")
        if name == "require_auth":
            return "required"
        if name == "optional_auth":
            return "optional"
    return "none"


def _response_model(route: APIRoute) -> str:
    model = route.response_model
    if model is None:
        return "—"
    return getattr(model, "__name__", str(model))


TAG_META = {
    "upload": ("Upload", "File ingestion (XER, MS Project XML)"),
    "projects": ("Projects", "CRUD, detail, activities, validation"),
    "programs": ("Programs", "Multi-revision program rollup"),
    "comparison": ("Comparison", "Two-schedule diff + manipulation detection"),
    "forensics": ("Forensics", "CPA per AACE RP 29R-03, delay waterfall"),
    "tia": ("TIA", "Time Impact Analysis per AACE RP 52R-06"),
    "evm": ("EVM", "Earned Value Management per ANSI/EIA-748"),
    "risk": ("Risk", "Monte Carlo QSRA per AACE RP 57R-09"),
    "analysis": ("Analysis", "CPM, DCMA 14-point, schedule view, calendar, attribution"),
    "intelligence": (
        "Intelligence",
        "Health Score, float trends, root cause, NLP, anomalies, alerts, dashboard",
    ),
    "whatif": ("What-If", "Deterministic + probabilistic scenarios, Pareto"),
    "schedule_ops": ("Schedule Ops", "Generation, build, cashflow, lookahead, risk register"),
    "cost": ("Cost", "CBS upload + persistence, trends, narrative, float entropy"),
    "exports": ("Exports", "Excel workbook, XER round-trip"),
    "benchmarks": ("Benchmarks", "Cross-project percentile comparison"),
    "reports": ("Reports", "PDF generation (10 types) + download"),
    "admin": ("Admin", "API keys, GDPR deletion"),
    "health": ("Health", "Readiness and liveness"),
    "org": ("Organizations", "Teams, members, audit"),
}


def _section_header(tag: str) -> tuple[str, str]:
    meta = TAG_META.get(tag)
    if meta:
        return meta
    return (tag.replace("_", " ").title(), "")


def main() -> None:
    # Group routes by router tag
    by_tag: dict[str, list[APIRoute]] = defaultdict(list)
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        # Skip auto-generated /docs, /openapi.json, etc.
        if route.path in {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}:
            continue
        tag = _infer_tag(route)
        by_tag[tag].append(route)

    # Order tags by TAG_META order, then alphabetical for unknowns
    ordered_tags = [t for t in TAG_META if t in by_tag]
    ordered_tags += sorted(t for t in by_tag if t not in TAG_META)

    total_endpoints = sum(len(v) for v in by_tag.values())

    lines: list[str] = []
    lines.append("# API Reference")
    lines.append("")
    lines.append(
        f"Generated from `src/api/app.py` — **{total_endpoints} endpoints** across "
        f"**{len(by_tag)} routers**. Interactive Swagger UI is served at "
        f"`/docs` when the API is running; this document is a static browseable index."
    )
    lines.append("")
    lines.append(
        "All paths are prefixed with the deployment base URL (e.g. "
        "`https://meridianiq.fly.dev`). Auth column: `none` (public), "
        "`optional` (degrades gracefully), `required` (returns 401 without bearer token)."
    )
    lines.append("")
    lines.append("Regenerate with: `python3 scripts/generate_api_reference.py`")
    lines.append("")

    # Index
    lines.append("## Contents")
    lines.append("")
    for tag in ordered_tags:
        name, _blurb = _section_header(tag)
        anchor = name.lower().replace(" ", "-").replace("/", "")
        lines.append(f"- [{name}](#{anchor}) — {len(by_tag[tag])} endpoints")
    lines.append("")

    # Sections
    for tag in ordered_tags:
        name, blurb = _section_header(tag)
        lines.append(f"## {name}")
        if blurb:
            lines.append("")
            lines.append(f"_{blurb}_")
        lines.append("")
        lines.append("| Method | Path | Summary | Response | Auth |")
        lines.append("|---|---|---|---|---|")

        routes = sorted(by_tag[tag], key=lambda r: (r.path, sorted(r.methods or [])))
        for route in routes:
            methods = sorted(m for m in (route.methods or []) if m != "HEAD")
            method = " / ".join(methods)
            summary = _one_line(route.endpoint.__doc__ if route.endpoint else "")
            # Escape pipe in summary/path to not break the markdown table
            summary = summary.replace("|", "\\|")
            path = route.path.replace("|", "\\|")
            response = _response_model(route)
            auth = _requires_auth(route)
            lines.append(f"| `{method}` | `{path}` | {summary or '—'} | `{response}` | {auth} |")
        lines.append("")

    output = REPO_ROOT / "docs" / "api-reference.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {total_endpoints} endpoints across {len(by_tag)} routers → {output}")


if __name__ == "__main__":
    main()
