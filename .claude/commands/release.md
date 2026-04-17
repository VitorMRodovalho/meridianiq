Cut a new MeridianIQ release: $ARGUMENTS

Expected argument: semver version without the `v` prefix (e.g., `3.8.0`, `3.8.0-rc1`, `4.0.0`). Abort with a clear error if no argument is provided or the format is invalid.

## Preflight (abort on any failure)

1. Working tree clean: `git status`.
2. Branch is `main` and up-to-date with origin.
3. Latest CI run on `main` is `success`: `gh run list --branch main --limit 1 --json conclusion --jq '.[0].conclusion'`.
4. Tag `v$ARGUMENTS` does not already exist: `git tag -l v$ARGUMENTS` must be empty.
5. Current version (in `pyproject.toml`) is lower than the new version (semver forward).

## Sync docs first

6. Run `/sync-docs` to regenerate `docs/api-reference.md`, `docs/methodologies.md`, `docs/mcp-tools.md`, and refresh `docs/architecture.md` stats. Commit the sync separately (different commit type — `docs:` vs `chore(release):`) before proceeding.

## Version bump

7. Edit the following files, replacing the current version (which is typically `X.Y.Z-dev`) with `$ARGUMENTS`:
   - `CHANGELOG.md` — rename the top heading from `## [X.Y.Z-dev] — …` to `## [$ARGUMENTS] — YYYY-MM-DD — …` (today's date).
   - `pyproject.toml` — `version = "$ARGUMENTS"`.
   - `web/package.json` — `"version": "$ARGUMENTS"`.
   - `src/api/app.py` — both `release="meridianiq-api@$ARGUMENTS"` (Sentry init) and `version="$ARGUMENTS"` (FastAPI constructor).
   - `README.md` — increment the "Released versions" count and append a new row to the Roadmap table if this is a minor/major bump.
   - `CLAUDE.md` — refresh the `Version:` line with stats pulled from the doc generators (engines, endpoints, routers, tests, pages, PDF report types, MCP tools).

## Verify

8. `python3 -m pytest tests/ -q` — abort on failure.
9. `cd web && npm run check` — abort on failure.

## Commit, tag, push, release

10. `git add CHANGELOG.md pyproject.toml web/package.json src/api/app.py README.md CLAUDE.md`.
11. Commit with subject `chore(release): v$ARGUMENTS — <codename>` (codename from CHANGELOG heading). Use a HEREDOC for the body with wave-level highlights. **Never** add `Co-Authored-By` trailers.
12. Create annotated tag: `git tag -a v$ARGUMENTS -m "<release message>"` (message mirrors the release notes summary).
13. Push: `git push origin main && git push origin v$ARGUMENTS`.
14. Extract the `## [$ARGUMENTS]` section of `CHANGELOG.md` into `/tmp/release-notes-$ARGUMENTS.md`.
15. Create the GitHub release: `gh release create v$ARGUMENTS --title "v$ARGUMENTS — <codename>" --notes-file /tmp/release-notes-$ARGUMENTS.md`.

## CI monitor + memory

16. Use a `Monitor` tool with an until-loop to watch CI on the release commit. Report `success | failure | cancelled` and the run ID.
17. Update `project_state.md` in memory: new version, commit hash, release URL, metrics snapshot.

## Rollback rules

- If any step after #11 fails, **do not** amend or force-push.
- A pushed tag is immutable — ship `X.Y.Z+1` with the fix unless the user explicitly approves `git push origin :v$ARGUMENTS` (destructive).
- Never skip hooks (`--no-verify`) or sign-off bypass.
