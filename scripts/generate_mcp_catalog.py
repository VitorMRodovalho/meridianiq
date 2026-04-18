"""Generate docs/mcp-tools.md from the MCP server's @mcp.tool() decorators.

Introspects ``src.mcp_server`` and writes a Markdown catalog of every
registered tool: name, signature, one-line summary, full description,
and parameter breakdown parsed from the Google-style docstring.

Usage::

    python3 scripts/generate_mcp_catalog.py

Regenerate whenever tools are added, renamed, or removed.
"""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _find_mcp_tools(module: Any) -> list[tuple[str, Any]]:
    """Find functions registered as MCP tools.

    FastMCP wraps decorated functions; we read the module directly and
    identify ``@mcp.tool()`` decorated items by scanning source lines.
    """
    src_path = Path(module.__file__)
    source = src_path.read_text(encoding="utf-8")

    # Match `@mcp.tool()` followed by (optionally blank lines and) `def NAME` or `async def NAME`
    pattern = re.compile(r"@mcp\.tool\(\)\s*\n(?:async\s+)?def\s+(\w+)\s*\(")
    names = pattern.findall(source)

    tools: list[tuple[str, Any]] = []
    for name in names:
        fn = getattr(module, name, None)
        if fn is None:
            continue
        tools.append((name, fn))
    return tools


_ARG_HEADER = re.compile(r"^\s*(Args|Arguments|Parameters)\s*:\s*$", re.MULTILINE)
_RETURN_HEADER = re.compile(r"^\s*(Returns|Return)\s*:\s*$", re.MULTILINE)
_RAISES_HEADER = re.compile(r"^\s*(Raises|Raise)\s*:\s*$", re.MULTILINE)


def _parse_docstring(doc: str | None) -> dict[str, str]:
    """Parse Google-style docstring into summary / description / args / returns."""
    if not doc:
        return {"summary": "", "description": "", "args": "", "returns": ""}

    cleaned = inspect.cleandoc(doc)
    lines = cleaned.splitlines()
    summary = lines[0].strip() if lines else ""

    # Split off summary, then parse sections
    body = "\n".join(lines[1:]).strip()

    # Find section boundaries
    args_m = _ARG_HEADER.search(body)
    returns_m = _RETURN_HEADER.search(body)
    raises_m = _RAISES_HEADER.search(body)

    section_starts = sorted(
        [m.start() for m in (args_m, returns_m, raises_m) if m],
    )
    description_end = section_starts[0] if section_starts else len(body)
    description = body[:description_end].strip()

    def _slice(header_match: re.Match[str] | None) -> str:
        if not header_match:
            return ""
        start = header_match.end()
        later_starts = [s for s in section_starts if s > header_match.start()]
        end = later_starts[0] if later_starts else len(body)
        return inspect.cleandoc(body[start:end]).strip()

    return {
        "summary": summary,
        "description": description,
        "args": _slice(args_m),
        "returns": _slice(returns_m),
    }


def _format_signature(fn: Any) -> str:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn.__name__ + "(...)"
    params = []
    for name, param in sig.parameters.items():
        anno = ""
        if param.annotation is not inspect.Parameter.empty:
            anno_obj = param.annotation
            anno_name = getattr(anno_obj, "__name__", str(anno_obj))
            anno = f": {anno_name}"
        default = ""
        if param.default is not inspect.Parameter.empty:
            default = f" = {param.default!r}"
        params.append(f"{name}{anno}{default}")
    ret = ""
    if sig.return_annotation is not inspect.Signature.empty:
        ret_obj = sig.return_annotation
        ret_name = getattr(ret_obj, "__name__", str(ret_obj))
        ret = f" -> {ret_name}"
    return f"{fn.__name__}({', '.join(params)}){ret}"


def main() -> None:
    from src import mcp_server  # noqa: WPS433 — deliberate lazy import after sys.path tweak

    tools = _find_mcp_tools(mcp_server)

    lines: list[str] = []
    lines.append("# MCP Tools Catalog")
    lines.append("")
    lines.append(
        f"MeridianIQ exposes **{len(tools)} tools** via the Model Context Protocol "
        f"so AI assistants (Claude Code, Claude Desktop) can query and analyze "
        f"uploaded P6 XER schedules."
    )
    lines.append("")
    lines.append("## Installation")
    lines.append("")
    lines.append("Install the MCP extras and run the server:")
    lines.append("")
    lines.append("```bash")
    lines.append('pip install -e ".[mcp]"')
    lines.append("python -m src.mcp_server")
    lines.append("```")
    lines.append("")
    lines.append("### Claude Code / Claude Desktop configuration")
    lines.append("")
    lines.append("Add to your MCP servers config (e.g. `~/.config/claude-code/config.json`):")
    lines.append("")
    lines.append("```json")
    lines.append("{")
    lines.append('  "mcpServers": {')
    lines.append('    "meridianiq": {')
    lines.append('      "command": "python",')
    lines.append('      "args": ["-m", "src.mcp_server"],')
    lines.append('      "cwd": "/absolute/path/to/meridianiq"')
    lines.append("    }")
    lines.append("  }")
    lines.append("}")
    lines.append("```")
    lines.append("")
    lines.append("## Tool index")
    lines.append("")
    lines.append("| Tool | One-line summary |")
    lines.append("|---|---|")
    for name, fn in tools:
        parsed = _parse_docstring(fn.__doc__)
        summary = parsed["summary"].replace("|", "\\|") or "—"
        anchor = name.lower().replace("_", "-")
        lines.append(f"| [`{name}`](#{anchor}) | {summary} |")
    lines.append("")

    lines.append("## Tools")
    lines.append("")

    for name, fn in tools:
        parsed = _parse_docstring(fn.__doc__)
        sig = _format_signature(fn)

        lines.append(f"### `{name}`")
        lines.append("")
        if parsed["summary"]:
            lines.append(f"**{parsed['summary']}**")
            lines.append("")
        lines.append("```python")
        lines.append(sig)
        lines.append("```")
        lines.append("")
        if parsed["description"]:
            lines.append(parsed["description"])
            lines.append("")
        if parsed["args"]:
            lines.append("**Arguments:**")
            lines.append("")
            lines.append("```")
            lines.append(parsed["args"])
            lines.append("```")
            lines.append("")
        if parsed["returns"]:
            lines.append("**Returns:**")
            lines.append("")
            lines.append(parsed["returns"])
            lines.append("")
        lines.append("---")
        lines.append("")

    # Regeneration footer
    lines.append("Regenerate this catalog with: `python3 scripts/generate_mcp_catalog.py`")

    output = REPO_ROOT / "docs" / "mcp-tools.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(tools)} MCP tools → {output}")


if __name__ == "__main__":
    main()
