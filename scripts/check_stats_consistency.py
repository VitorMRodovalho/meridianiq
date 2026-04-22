#!/usr/bin/env python3
"""Validate that top-level docs' count claims match the canonical catalogs.

Run after the three generator scripts so the catalogs are up to date:

    python3 scripts/generate_api_reference.py
    python3 scripts/generate_methodology_catalog.py
    python3 scripts/generate_mcp_catalog.py
    python3 scripts/check_stats_consistency.py

The validator treats the generated catalog headers as the single source of
truth:

- ``docs/api-reference.md`` — "**N endpoints** across **M routers**"
- ``docs/methodologies.md`` — "**N engines** plus **M export module**"
- ``docs/mcp-tools.md``     — "**N tools**"

It also counts SvelteKit pages directly:

- ``web/src/routes/**/+page.svelte``

It then scans the ``## Architecture`` section of ``CLAUDE.md`` and fails on
any number claim that disagrees with the canonical source.  Historical
anchors (e.g. the ``Version: vX.Y.Z`` line that freezes a release snapshot)
are skipped by default.

Exit codes:

    0 — all counts match
    1 — at least one mismatch (message on stderr)

No third-party dependencies — stdlib only.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_MD = ROOT / "docs" / "api-reference.md"
METH_MD = ROOT / "docs" / "methodologies.md"
MCP_MD = ROOT / "docs" / "mcp-tools.md"
CLAUDE_MD = ROOT / "CLAUDE.md"
README_MD = ROOT / "README.md"
ROUTES_DIR = ROOT / "web" / "src" / "routes"


@dataclass
class Stats:
    endpoints: int
    routers: int
    engines: int
    export_modules: int
    mcp_tools: int
    pages: int

    def describe(self) -> str:
        return (
            f"{self.engines} engines + {self.export_modules} export module, "
            f"{self.endpoints} endpoints across {self.routers} routers, "
            f"{self.mcp_tools} MCP tools, {self.pages} pages"
        )


def _read(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def _must_match(pattern: str, text: str, *, label: str) -> tuple[int, ...]:
    m = re.search(pattern, text)
    if not m:
        raise SystemExit(
            f"could not locate canonical count for {label!r} — "
            f"pattern {pattern!r} did not match. "
            f"Did you regenerate the catalog?"
        )
    return tuple(int(g) for g in m.groups())


def canonical_stats() -> Stats:
    """Extract the single source of truth from the generated catalogs."""
    api_text = _read(API_MD)
    meth_text = _read(METH_MD)
    mcp_text = _read(MCP_MD)

    endpoints, routers = _must_match(
        r"\*\*(\d+)\s+endpoints?\*\*\s+across\s+\*\*(\d+)\s+routers?\*\*",
        api_text,
        label="api-reference endpoints/routers",
    )
    engines, export_modules = _must_match(
        r"\*\*(\d+)\s+engines?\*\*\s+plus\s+\*\*(\d+)\s+export\s+module",
        meth_text,
        label="methodologies engines/export",
    )
    (mcp_tools,) = _must_match(
        r"\*\*(\d+)\s+tools?\*\*",
        mcp_text,
        label="mcp-tools count",
    )

    pages = sum(1 for _ in ROUTES_DIR.rglob("+page.svelte"))

    return Stats(
        endpoints=endpoints,
        routers=routers,
        engines=engines,
        export_modules=export_modules,
        mcp_tools=mcp_tools,
        pages=pages,
    )


def extract_architecture_block(claude_md: str) -> str:
    """Pull just the ``## Architecture`` section of CLAUDE.md.

    Historical anchors (Version:, v3.7.0, release notes) live outside this
    section and are intentionally not validated — they are frozen snapshots.
    """
    match = re.search(r"## Architecture\b(.*?)(?:\n## |\Z)", claude_md, re.DOTALL)
    if not match:
        raise SystemExit("CLAUDE.md: `## Architecture` section not found")
    return match.group(1)


def find_mismatches(stats: Stats, architecture_block: str) -> list[str]:
    """Return a list of human-readable mismatch messages. Empty = consistent."""
    mismatches: list[str] = []

    def _check(pattern: str, expected: int, label: str) -> None:
        m = re.search(pattern, architecture_block)
        if m is None:
            return  # claim not present — nothing to validate
        actual = int(m.group(1))
        if actual != expected:
            mismatches.append(
                f"CLAUDE.md Architecture: {label} claims {actual}, canonical is {expected}"
            )

    _check(r"\*\*(\d+)\s+analysis\s+engines\*\*", stats.engines, "engines")
    _check(r"FastAPI\s+with\s+(\d+)\s+endpoints?", stats.endpoints, "endpoints")
    _check(r"across\s+(\d+)\s+routers?", stats.routers, "routers")
    _check(r"SvelteKit\s*\+\s*Tailwind\s*v4,\s*(\d+)\s+pages?", stats.pages, "pages")

    return mismatches


def extract_readme_key_numbers(readme: str) -> str:
    """Pull just the ``## Key Numbers`` section from README.md.

    The surrounding sections (Capabilities, Architecture, Live Demo
    badges) carry version strings and historical anchors that are
    intentionally not validated here.
    """
    match = re.search(r"## Key Numbers\b(.*?)(?:\n## |\Z)", readme, re.DOTALL)
    if not match:
        raise SystemExit("README.md: `## Key Numbers` section not found")
    return match.group(1)


def find_readme_mismatches(stats: Stats, key_numbers_block: str) -> list[str]:
    """Return mismatch messages for the README §Key Numbers table."""
    mismatches: list[str] = []

    def _check(pattern: str, expected: int, label: str) -> None:
        m = re.search(pattern, key_numbers_block)
        if m is None:
            return
        actual = int(m.group(1))
        if actual != expected:
            mismatches.append(
                f"README.md Key Numbers: {label} claims {actual}, canonical is {expected}"
            )

    # Examples of rows the table uses:
    #   | Analysis engines | 47 + 1 export module |
    #   | API endpoints | 121 across 23 routers |
    #   | Frontend pages | 54 (Schedule Viewer, …) |
    _check(
        r"Analysis\s+engines\s*\|\s*(\d+)\s*\+\s*\d+\s*export",
        stats.engines,
        "engines",
    )
    _check(r"API\s+endpoints\s*\|\s*(\d+)\b", stats.endpoints, "endpoints")
    _check(r"across\s+(\d+)\s+routers?", stats.routers, "routers")
    _check(r"Frontend\s+pages\s*\|\s*(\d+)\b", stats.pages, "pages")

    return mismatches


def main() -> int:
    stats = canonical_stats()

    claude_text = _read(CLAUDE_MD)
    architecture = extract_architecture_block(claude_text)
    claude_mismatches = find_mismatches(stats, architecture)

    readme_mismatches: list[str] = []
    if README_MD.exists():
        readme_text = _read(README_MD)
        readme_mismatches = find_readme_mismatches(
            stats, extract_readme_key_numbers(readme_text)
        )

    all_mismatches = claude_mismatches + readme_mismatches
    if all_mismatches:
        print("Stats drift detected:\n")
        for msg in all_mismatches:
            print(f"  - {msg}")
        print(
            f"\nCanonical state (from generated catalogs): {stats.describe()}",
            file=sys.stderr,
        )
        print(
            "\nFix the offending file(s) to match, or regenerate the catalogs if "
            "the code changed.",
            file=sys.stderr,
        )
        return 1

    print(f"Stats consistent across CLAUDE.md and README.md: {stats.describe()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
