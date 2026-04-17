# Scripts

Self-maintaining documentation generators. Each script introspects live source code and writes a Markdown file under `docs/`. Run them whenever the underlying code changes — typically as part of a pre-merge checklist (the PR template has a checkbox).

| Script | Output | Introspects |
|---|---|---|
| `generate_api_reference.py` | `docs/api-reference.md` | `src/api/app.py` → all `APIRoute` instances with tag, summary, response model, auth dependencies |
| `generate_methodology_catalog.py` | `docs/methodologies.md` | `src/analytics/*.py` + `src/export/*.py` module docstrings → title, summary, References block, detected standards |
| `generate_mcp_catalog.py` | `docs/mcp-tools.md` | `src/mcp_server.py` `@mcp.tool()` decorated functions → signature, Google-style docstring (Args / Returns) |

## Usage

```bash
python3 scripts/generate_api_reference.py
python3 scripts/generate_methodology_catalog.py
python3 scripts/generate_mcp_catalog.py
```

Each prints a one-line summary of what it wrote. Commit the regenerated Markdown alongside the source-code change that triggered the regeneration.

## Why generators instead of hand-written docs?

Hand-written catalogs for 98 endpoints / 40 engines / 22 tools drift within one release cycle. The generators:

- **Stay honest** — the Markdown is always sourced from the live code
- **Fail loud** — if a router is missing a docstring, the catalog has a blank cell that's visible in review
- **Document the contract** — the fields extracted (summary, standards, auth tier) are the ones we want authors to maintain

If you add a new endpoint / engine / MCP tool, updating its docstring is enough — the catalog entry appears on the next regeneration.

## What they don't do

- They don't fetch anything over the network
- They don't write anything outside `docs/`
- They don't touch tests or source code
- They don't run if the module fails to import — fix the import first

## Adding a new generator

Follow the same shape: a `main()` that reads from `src/`, builds a list of lines, writes via `Path.write_text`. Keep the Markdown output deterministic (sort by name or declared order, not by dictionary iteration) so diffs stay readable.
