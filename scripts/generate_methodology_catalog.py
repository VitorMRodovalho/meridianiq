"""Generate docs/methodologies.md from src/analytics/*.py module docstrings.

Each analysis engine in ``src/analytics/`` is a standalone module whose
top-level docstring documents the methodology, its purpose, and the
published standards it implements (AACE RP, DCMA 14-point, ANSI/EIA,
SCL Protocol, PMI, etc.). This script reads every module docstring,
extracts the summary / description / references block, and emits a
single Markdown catalog.

Usage::

    python3 scripts/generate_methodology_catalog.py

Regenerate whenever engines are added, renamed, or relocated.
"""

from __future__ import annotations

import ast
import inspect
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ANALYTICS_DIR = REPO_ROOT / "src" / "analytics"
EXPORT_DIR = REPO_ROOT / "src" / "export"


@dataclass
class EngineDoc:
    module_name: str
    title: str
    summary: str
    body: str
    references: list[str]


_REF_HEADER = re.compile(r"^\s*(References?|Refs?)\s*:\s*$", re.MULTILINE)
_METHODOLOGY_HEADER = re.compile(r"^\s*Methodology\s*:?\s*$", re.MULTILINE)


def _read_module_docstring(path: Path) -> str | None:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return None
    return ast.get_docstring(tree)


def _split_sections(doc: str) -> tuple[str, str, list[str]]:
    """Split docstring into (title, body_without_refs, reference_lines)."""
    cleaned = inspect.cleandoc(doc)
    lines = cleaned.splitlines()
    title = lines[0].strip() if lines else ""
    rest = "\n".join(lines[1:]).strip()

    refs_match = _REF_HEADER.search(rest)
    if refs_match:
        body = rest[: refs_match.start()].strip()
        refs_block = rest[refs_match.end() :].strip()
        references = [
            line.lstrip("-•* ").strip()
            for line in refs_block.splitlines()
            if line.strip() and not line.strip().startswith(("Note:", "Notes:"))
        ]
    else:
        body = rest
        references = []

    return title, body, references


def _extract_summary(body: str) -> tuple[str, str]:
    """Split body into (summary_paragraph, remaining_body)."""
    parts = body.split("\n\n", 1)
    summary = parts[0].strip().replace("\n", " ")
    remaining = parts[1].strip() if len(parts) > 1 else ""
    return summary, remaining


def _module_display_name(module_name: str) -> str:
    """Turn snake_case into Title Case."""
    return module_name.replace("_", " ").title()


STANDARD_HINTS = [
    ("aace rp 29r-03", "AACE RP 29R-03 — Forensic Schedule Analysis"),
    ("aace rp 52r-06", "AACE RP 52R-06 — Time Impact Analysis"),
    ("aace rp 57r-09", "AACE RP 57R-09 — Integrated Cost/Schedule Risk Analysis"),
    ("aace rp 49r-06", "AACE RP 49R-06 — Identifying Critical Activities"),
    ("aace rp 10s-90", "AACE RP 10S-90 — Cost Engineering Terminology"),
    ("aace rp 46r-11", "AACE RP 46R-11 — Scheduling Professional Skills"),
    ("aace rp 41r-08", "AACE RP 41R-08 — Risk Analysis and Contingency"),
    ("aace rp 65r-11", "AACE RP 65R-11 — Monte Carlo Risk Analysis"),
    ("ansi/eia-748", "ANSI/EIA-748 — Earned Value Management Systems"),
    ("eia-748", "ANSI/EIA-748 — Earned Value Management Systems"),
    ("dcma", "DCMA 14-Point Schedule Assessment"),
    ("scl protocol", "SCL Delay and Disruption Protocol"),
    ("gao schedule", "GAO Schedule Assessment Guide"),
    ("pmbok", "PMI PMBOK Guide"),
    ("pmi practice standard for scheduling", "PMI Practice Standard for Scheduling"),
]


def _detect_standards(title: str, body: str, refs: list[str]) -> list[str]:
    """Detect standards referenced in the docstring even if not listed explicitly."""
    text = " ".join([title, body, " ".join(refs)]).lower()
    found: list[str] = []
    for needle, label in STANDARD_HINTS:
        if needle in text and label not in found:
            found.append(label)
    return found


def _collect(dir_path: Path) -> list[EngineDoc]:
    docs: list[EngineDoc] = []
    for py in sorted(dir_path.glob("*.py")):
        if py.name == "__init__.py":
            continue
        module_name = py.stem
        doc = _read_module_docstring(py)
        if not doc:
            continue
        title, body, references = _split_sections(doc)
        summary, remaining = _extract_summary(body)
        docs.append(
            EngineDoc(
                module_name=module_name,
                title=title,
                summary=summary,
                body=remaining,
                references=references,
            )
        )
    return docs


def _render_engine(engine: EngineDoc) -> list[str]:
    display = _module_display_name(engine.module_name)
    lines = [f"### `{engine.module_name}` — {display}"]
    if engine.title:
        lines.append("")
        lines.append(f"**{engine.title}**")
    if engine.summary:
        lines.append("")
        lines.append(engine.summary)
    if engine.body:
        lines.append("")
        lines.append(engine.body)
    standards = _detect_standards(
        engine.title, engine.body + " " + engine.summary, engine.references
    )
    if standards:
        lines.append("")
        lines.append("**Standards implemented:**")
        lines.append("")
        for s in standards:
            lines.append(f"- {s}")
    if engine.references:
        lines.append("")
        lines.append("**Explicit references from docstring:**")
        lines.append("")
        for ref in engine.references:
            lines.append(f"- {ref}")
    lines.append("")
    lines.append("---")
    lines.append("")
    return lines


def main() -> None:
    engines = _collect(ANALYTICS_DIR)
    exports = _collect(EXPORT_DIR) if EXPORT_DIR.exists() else []

    lines: list[str] = []
    lines.append("# Methodology Catalog")
    lines.append("")
    lines.append(
        f"MeridianIQ's analysis stack is **{len(engines)} engines** plus "
        f"**{len(exports)} export module** in `src/export/`. Every engine is a "
        f"standalone module whose docstring cites the published standard it "
        f"implements — this catalog is auto-generated from those docstrings."
    )
    lines.append("")
    lines.append(
        'When a scheduler or forensic analyst asks *"what standard does this '
        'calculation follow?"*, the answer is in the engine docstring and in '
        "this catalog."
    )
    lines.append("")

    lines.append("## Index")
    lines.append("")
    lines.append("| Engine | Title |")
    lines.append("|---|---|")
    for e in engines:
        anchor = e.module_name.replace("_", "-")
        title = e.title.replace("|", "\\|") or "—"
        lines.append(
            f"| [`{e.module_name}`](#{anchor}--{_module_display_name(e.module_name).lower().replace(' ', '-')}) | {title} |"
        )
    lines.append("")

    lines.append("## Engines")
    lines.append("")
    for engine in engines:
        lines.extend(_render_engine(engine))

    if exports:
        lines.append("## Export Modules")
        lines.append("")
        for engine in exports:
            lines.extend(_render_engine(engine))

    lines.append("")
    lines.append("Regenerate with: `python3 scripts/generate_methodology_catalog.py`")

    output = REPO_ROOT / "docs" / "methodologies.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(engines)} engines + {len(exports)} export modules → {output}")


if __name__ == "__main__":
    main()
