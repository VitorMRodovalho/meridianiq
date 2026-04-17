Run the MeridianIQ "planned vs delivered" QA/QC checkpoint.

This implements the `feedback_qa_discipline.md` rule: validate after each feature, catch bugs before starting the next.

Optional argument: feature name (for reporting clarity). If not provided, infer from the most recent commit subject.

## Part 1 — Standard verify (fail fast)

1. `python3 -m pytest tests/ -q` — all tests pass.
2. `ruff check src/ tests/` — clean.
3. `ruff format --check src/ tests/` — clean.
4. `cd web && npm run check` — zero errors (warnings are acceptable; snapshot the count).
5. `cd web && npm run build` — builds successfully.

Report pass/fail per step. Stop on first failure and diagnose.

## Part 2 — Stats-consistency (single-source-of-truth validation)

Run the 3 doc generators and capture output counts. Then verify all the following locations agree:

| Count | Authoritative source | Must also agree with |
|---|---|---|
| Analysis engines | `generate_methodology_catalog.py` output | `CLAUDE.md` Version line, `docs/architecture.md` overview + diagram, `README.md` feature list |
| API endpoints / routers | `generate_api_reference.py` output | `CLAUDE.md`, `docs/architecture.md` overview + diagram |
| MCP tools | `generate_mcp_catalog.py` output | `CLAUDE.md`, `docs/architecture.md` |
| Test count | `pytest --collect-only` | `CLAUDE.md`, `CHANGELOG.md` latest entry |
| SvelteKit pages | `ls web/src/routes/**/+page.svelte \| wc -l` | `CLAUDE.md`, `docs/architecture.md` |

If any location disagrees with the authoritative source, report the drift (file:line + expected vs actual). Offer to run `/sync-docs` to fix.

## Part 3 — Planned vs delivered (diff review)

6. Read the most recent commit message(s) since the last tag: `git log $(git describe --tags --abbrev=0)..HEAD --oneline` plus full messages.
7. For each commit subject claim (e.g., "adds X endpoint", "fixes Y bug"), grep the diff to verify the change is actually present.
8. Flag any commit that claims something not visible in the diff — this is the "planned but not delivered" bug class.
9. Conversely, check if the diff contains changes not mentioned in any commit message (drive-by edits that should have been separate commits).

## Part 4 — Confidentiality / sanitisation sweep

10. Run ripgrep for likely sensitive tokens in the full diff:
    - Client/company names (maintain a list in `.claude/sensitive-terms.txt` if it exists).
    - Credential patterns: `AKIA[A-Z0-9]{16}`, `-----BEGIN [A-Z ]+PRIVATE KEY-----`, `supabase.*[eE]y[A-Za-z0-9_.-]{40,}`, `ghp_[A-Za-z0-9]{36}`.
    - Absolute filesystem paths pointing to the user's Downloads/ or home directory that might leak through.
11. If any match, abort with a red flag and ask the user whether to redact.

## Report format

Finish with a concise one-screen report:
- ✅ / ❌ per part
- Stats drift table (empty if clean)
- Planned vs delivered summary (empty if clean)
- Sensitive-term hits (empty if clean)
- Recommended next action (proceed / fix X / abort)
