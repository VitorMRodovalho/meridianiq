# 0033. Lock the Python dependencies with uv; CI and the API image install the same set

* Status: proposed
* Deciders: @VitorMRodovalho
* Date: 2026-10-31
* Council review: `devils-advocate`, 22 findings adjudicated against the repo (outcome in "Review" below)
* Cites: issue #131 (the gap), #348 (what reached production untested), #349 / #354 (the image smoke job), #346 (the floor job), #245 (the cap contract), #352 (version holds), [ADR-0014](0014-derived-artifact-provenance-hash.md) (a forensic hash that depends on serialization)

## Context and Problem Statement

There was no lockfile. Each consumer resolved the ranges in `pyproject.toml` on its own, to the newest release each range allowed:

| Consumer | Install | When |
|---|---|---|
| CI, Backend job | `pip install -e ".[dev,mcp,ai]"` | on every push |
| API image | `pip install ".[api,reports,export]"` | at deploy, minutes later, on the remote builder |

So:
- **A release published between the two runs ships without having been tested.**
- The same commit, rebuilt later, can produce a different image.
- Only the deploy log records what production runs.

On 2026-10-31 the versions happened to match (for example pydantic 2.14.2), but nothing enforced it (#131, comment 6537583919).

## Decision Drivers

- **Test what ships.** CI installs the versions the image installs.
- **Reproducible image.** The same commit gives the same packages.
- **Updates keep flowing,** including transitive ones, as pull requests that run CI.
- **Keep the existing guards.** The floor job (#346) keeps testing the lower bounds, and the cap contract (#245) keeps failing a widened cap.
- **Small change to the image.** It stays a single stage on `python:3.15-slim`, with the same system libraries.

## Considered Options

1. Status quo, no lock.
2. **`uv.lock`, installed with `uv sync --locked` in CI and in the image; Dependabot's `uv` ecosystem updates the lock.**
3. `uv.lock` exported with `uv export` to a hashed requirements file, installed with `pip --require-hashes`, so the image stays pip-only.
4. pip-tools: one `pip-compile` requirements file per install profile.

## Decision Outcome

Option 2.

**What is installed, and from where**
- `uv.lock` holds one universal resolution. CI installs `dev`, `mcp` and `ai` from it; the image installs `api`, `reports` and `export`.
- `--locked` makes both fail when the lock does not match `pyproject.toml`. That includes a version-only bump: the lock records the project's own version, so `/release`, the `__about__` bump procedure and the deploy checklist now run `uv lock`.
- Both use uv 0.13.6: the Dockerfile copies it pinned by digest, and CI pins `setup-uv` to the same version.
- The image environment is root-owned `/opt/venv`, and `UV_NO_DEV=1` keeps any future `dev` dependency group out of it.

**How updates arrive**
- Dependabot's `uv` ecosystem opens pull requests that update the lock.
- `allow: dependency-type: all` covers indirect dependencies too. With a lock, a transitive dependency moves only when the lock is regenerated.
- `versioning-strategy: increase-if-necessary` keeps an in-range update to `uv.lock` only, so the byte-exact cap contract stays green. A release outside a range still edits `pyproject.toml`, and a widened cap still fails that test on purpose.

**What CI checks on each pull request**
- The Backend job installs from the lock.
- Once #354 is merged, the image smoke job also builds the image and drives it. That is what covers the packages only the image installs; the Backend job does not install them (see Review 3).

**Why not option 3.** It leaves two files to keep in step. Dependabot updates `uv.lock`, not an exported requirements file, so every Dependabot pull request would fail a sync check. Its hash checking, option 2 already has (measured below).

**Why not option 4.** It needs one file per combination of extras, with no single universal resolution. CI already uses uv (#346).

### Measured (2026-10-31, uv 0.13.6)

**The lock**
- 107 packages, universal for `requires-python >=3.12`; 630 KB, lock `revision = 5`.
- It declares one resolution fork per Python minor, 3.12 to 3.15 and later. Today no package has more than one locked version.
- 106 sources are the PyPI registry and 1 is the project itself (editable). All 1899 artifact URLs are on files.pythonhosted.org.
- `tests/test_lockfile_sources.py` keeps all three counts true. A lock with one URL moved to a mirror fails it.

**CI**
- `uv sync --locked --extra dev --extra mcp --extra ai` on Python 3.15 gives the same result as the pip install: 2722 passed, 40 skipped, ruff clean. The CI run of this branch logged "Installed 82 packages" and the same counts.

**The image**
- 634 MB, against 615 MB with pip; the difference is the uv binary.
- It reaches healthy, and the image smoke from #354 passes all 5 checks: upload, health report PDF, Excel export, CBS upload, AIA G703.
- An environment in `/app/.venv` reached 882 MB, because `chown -R /app` copied it into a second layer. Hence `/opt/venv`.

**The interpreter**
- In the image, `/usr/local/bin/python -c "import src.materializer.backfill"` fails with `No module named 'src'`, while `/opt/venv/bin/python` succeeds from any working directory.
- The deploy job's re-materialization over `flyctl ssh console` and the checklist's manual command therefore call `/opt/venv/bin/python`. Whether Fly's SSH session inherits the image `PATH` no longer matters.

**`--locked`, three arms**
- A changed dependency range without relocking: exit 1.
- A version bump (4.3.0 to 4.4.0) without relocking: exit 1.
- The lock in step: exit 0.

**Hashes**
- A wheel's hash changed in a scratch copy of the lock fails `uv sync` from an empty cache: "Hash mismatch for `idna==3.20`".
- Changing only that package's sdist hash does not fail, because the sdist is never downloaded when a wheel fits.

**Dependabot**
- GitHub lists the `uv` ecosystem, at uv v0.11, for version and security updates. Its docs list `indirect`/`all` and `versioning-strategy` as supported for `uv`, but do not list which strategy values.
- uv 0.11.33 accepts this lock (`uv lock --check` exits 0) and rejects a stale one.
- Dependabot security updates are enabled on the repository.

**Not exercised until the first Dependabot run** (Monday 06:00 America/Sao_Paulo):
- that `increase-if-necessary` is accepted for `uv`;
- that the dependency graph reads `uv.lock`, which security updates for locked transitive packages need. After the merge, check the dependency-graph SBOM for a locked transitive package.

## Consequences

**How updates arrive**
- Newer releases no longer reach CI or the image on their own. They arrive as weekly Dependabot pull requests that update the lock, grouped as before, plus security pull requests for advisories.
- If those pull requests stop arriving or keep failing, the lock freezes. Watch the first runs (#340 and #352).

**What changes for contributors**
- Any change to `pyproject.toml` that the lock records (ranges, extras, the version) needs `uv lock` in the same commit.
- `pip install -e ".[dev]"` still works locally, but it resolves the newest releases, which CI no longer tests. `uv sync --locked --extra dev --extra mcp --extra ai` installs what CI installs. README, CONTRIBUTING and the user guides still show the pip command; updating them is a follow-up.

**What stays the same**
- The floor job (#346) still resolves `lowest-direct` without the lock. The cap contract is unchanged.

**Operator notes**
- In a production shell, `pip list` now shows the base interpreter. Use `uv pip list --python /opt/venv/bin/python`.

**Rollback**
- Restore the two pip install lines and the plain `python` in the re-materialization step, delete `uv.lock`, and switch the Dependabot entry back to `pip`.

## Review (devils-advocate, adjudicated)

Fixed in this change:
1. **A version bump makes the lock stale** (measured: exit 1). `/release`, the `__about__` procedure and the deploy checklist now run `uv lock`. `/release` also gained the `__about__.py` bump it was missing, and lost an `app.py` edit that no longer applies.
2. **`flyctl ssh console -C "python …"`** would have run the base interpreter, which cannot import the app (measured). Now `/opt/venv/bin/python`.
3. **"The image smoke runs on each Dependabot PR"** holds only once #354 is merged, so this change is ordered after it.
   - About 15 packages only the image installs are not installed by the Backend job: the WeasyPrint stack, and `uvloop`, `httptools`, `watchfiles` and `pyyaml` from `uvicorn[standard]`.
   - The smoke renders a PDF through the running server, so it exercises the WeasyPrint stack and the server loop (`uvloop`, `httptools`, which uvicorn uses when present).
   - `watchfiles` and `pyyaml` are used by uvicorn only for `--reload` and YAML log configuration, which production does not use. They are installed but not exercised.
   - Without WeasyPrint the report endpoint answers 200 with HTML instead of failing. That is filed separately; the smoke catches it.
4. **Transitive updates.** `allow: all` added.
5. **The cap contract against floor bumps.** `increase-if-necessary` added. Not exercised until the first run.
8. **CI used the newest uv.** Pinned to 0.13.6, like the image.
10. / 21. **The lock's artifact URLs were unchecked.** Guard test added.
11. **`uv sync` installs a default `dev` group.** `UV_NO_DEV=1` added.
12. The CLAUDE.md line about reproducing CI named only `dev`; it now names CI's three extras.
13. The floor job's comment said the Backend job resolves the newest releases; corrected.
16. README.md is copied after the dependency layer, so a README edit no longer reinstalls the dependencies.
17. "0 of 52 differ" holds by construction, since both run Python 3.15 on one lock. It shows both installs followed the lock, not that they agree independently.
18. The smoke's five checks are named, and #354 carries the script.
20. `tests/test_python_runtime_guard.py` also reads `UV_PYTHON`. Set to 3.16, it fails.
22. A `.dockerignore` keeps `.env`, `.venv` and everything the image does not copy out of the build context.

Rejected:
7. **"The universal lock holds production to versions that still support 3.12."** uv's default fork strategy, `requires-python`, picks the latest compatible version for each supported Python version (uv's resolution docs). The lock's markers show the per-minor forks.

Open, not fixed here:
6. **Build backends are not locked.**
   - pyyaml 6.0.3 has no cp315 wheel, so the image builds it from its sdist. The sdist's hash is in the lock, but the build backend it pulls is resolved fresh and is not hash-checked. The same holds for hatchling, which builds the project.
   - So "the same commit gives the same packages" holds for everything installed from wheels, not for those builds.
   - Follow-up: `[tool.uv] build-constraint-dependencies` with hashes.
9. **Fly's remote builder first builds this Dockerfile at the deploy.** #354 builds the image on the CI runner for every pull request. Watch the first deploy, and roll back as above if needed.
14. gitleaks ran on this branch with the lock in place and passed.
15. See "Operator notes" above.
19. The uv digest in the Dockerfile and the CI `version` have no automatic updater. They are listed with the other holds in #352.
