Regenerate doc catalogs and refresh architecture.md for the current codebase state.

## Run generators (in order — they are independent, can parallelise if preferred)

1. `python3 scripts/generate_api_reference.py` → writes `docs/api-reference.md`. Note the printed `N endpoints across M routers`.
2. `python3 scripts/generate_methodology_catalog.py` → writes `docs/methodologies.md`. Note the printed `N engines + M export modules`.
3. `python3 scripts/generate_mcp_catalog.py` → writes `docs/mcp-tools.md`. Note the printed `N MCP tools`.

Each generator is the single source of truth for its respective count.

## Refresh architecture.md stats from generator output

4. Update `docs/architecture.md`:
   - Line 1 HTML comment: `<!-- Last updated: YYYY-MM-DD (vX.Y.Z) -->` with today's date and current pyproject version.
   - Overview paragraph: "N analysis engines + M export modules, P API endpoints across Q routers, R SvelteKit pages, 11 hand-crafted SVG chart components, 20 Supabase migrations, 22 MCP tools, 14 PDF report types, T tests".
   - Mermaid diagram subgraphs:
     - `UI` node: "R pages · Svelte 5 runes …".
     - `API` node: "P endpoints · Q routers …".
     - `ENGINES` node: "N analysis engines + M export module …".
   - Catalog-pointer lines near the bottom (API Reference + Methodologies rows).

   Counts:
   - Pages: `ls web/src/routes/**/+page.svelte | wc -l`.
   - Tests: `python3 -m pytest tests/ --collect-only -q 2>&1 | tail -5` → extract "N tests collected".

## Consistency pass — CLAUDE.md

5. If any of the counts changed vs what `CLAUDE.md` says in the `Version:` line, update it. This is the second source of truth for counts (after the generators); do not let it drift.

## Commit if dirty

6. `git status`. If only catalog files / architecture.md / CLAUDE.md changed, commit as `docs: regenerate catalogs for vX.Y.Z-dev` or `docs: regenerate catalogs for vX.Y.Z` (match the current pyproject version). Body: short diff summary of counts that changed (`N → N'`).
7. Do NOT push automatically — leave the push to the caller (often called from `/release`, which pushes after the release commit).

## No-op case

If generators produce no diff and CLAUDE.md is already coherent, report "Docs in sync — no commit needed" and exit.
