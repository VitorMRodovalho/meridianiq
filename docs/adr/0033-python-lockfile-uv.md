# 0033. Lock the Python dependencies with uv; CI and the API image install the same set

* Status: proposed
* Deciders: @VitorMRodovalho
* Date: 2026-10-31
* Cites: issue #131 (the gap), #348 (what reached production untested), #349 (the image smoke job), #346 (the floor job), #245 (the cap contract), [ADR-0014](0014-derived-artifact-provenance-hash.md) (a forensic hash that depends on serialization)

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

- **Test what ships.** CI must install the versions the image installs.
- **Reproducible image.** The same commit gives the same packages.
- **Updates keep flowing.** Newer releases still arrive weekly, as pull requests that run CI.
- **Keep the existing guards.** The floor job (#346) keeps testing the lower bounds, and the cap contract (#245) keeps failing a widened cap.
- **Small change to the image.** It stays a single stage on `python:3.15-slim`, with the same system libraries.

## Considered Options

1. Status quo, no lock.
2. **`uv.lock`, installed with `uv sync --locked` in CI and in the image; Dependabot's `uv` ecosystem updates the lock.**
3. `uv.lock` exported with `uv export` to a hashed requirements file, installed with `pip --require-hashes`, so the image stays pip-only.
4. pip-tools: one `pip-compile` requirements file per install profile.

## Decision Outcome

Option 2.

- **One file, read by everyone.** CI and the image install from the same `uv.lock`, so the job tests the versions that ship.
- **The lock cannot drift silently.** `--locked` makes both CI and the image build fail when `uv.lock` does not match `pyproject.toml`.
- **Updates keep flowing.** Dependabot's `uv` ecosystem opens pull requests that update the lock, and CI plus the image smoke run on each one.

**Why not option 3.** It leaves two files to keep in step. Dependabot's `uv` ecosystem updates `uv.lock` but not an exported requirements file, so every Dependabot pull request would fail a sync check or need a bot step. Its main advantage, hash checking, option 2 already has: uv verifies the hashes recorded in `uv.lock` when it downloads (measured below).

**Why not option 4.** It needs one file per combination of extras, with no single universal resolution. CI already uses uv (#346).

### Measured (2026-10-31, uv 0.13.6)

**The lock**
- `uv lock` resolves 107 packages, universal for `requires-python >=3.12`. The file is 630 KB, lock `revision = 5`.

**CI**
- `uv sync --locked --extra dev --extra mcp --extra ai` on Python 3.15.2 gives the same suite result as the pip install: 2722 passed, 40 skipped, ruff clean.

**The image**
- `uv sync --locked --no-editable --extra api --extra reports --extra export` installs into `/opt/venv`.
- It reaches healthy, and `scripts/image_smoke.py` (#349) passes 5 of 5: PDF, Excel, CBS upload, AIA G703.
- Size: 647 MB, up from 615 MB. The difference is the uv binary.
- The first attempt put the environment in `/app/.venv`, and `chown -R /app` copied it into a second layer, for 882 MB. Moving it to root-owned `/opt/venv` fixed that, and the app user cannot write to its own dependencies.

**Same versions**
- Of the 52 packages both CI and the image install, 0 differ.

**`--locked`, both arms**
- With `pyproject.toml` changed and the lock not updated, `uv sync --locked` exits 1.
- With the lock matching, it exits 0.

**Hashes, both arms**
- With the wheel hash of one package changed in a scratch copy of the lock, `uv sync` from an empty cache fails with "Hash mismatch for `idna==3.20`".
- With the lock unchanged, it succeeds.

**Dependabot**
- GitHub's supported-ecosystems table lists `uv`, for version and security updates, at uv v0.11.
- uv 0.11.33 accepts this 0.13.6 lock (`uv lock --check` exits 0) and rejects a stale one (exits 1).
- **Not exercised with Dependabot itself**; its first pull request will show it.

## Consequences

**How updates arrive**
- Newer releases no longer reach CI or the image on their own. They arrive as Dependabot `uv` pull requests, weekly, grouped as before.
- An advisory against a locked version arrives as a security pull request.

**What changes for contributors**
- A change to a dependency range must run `uv lock` in the same commit, or CI and the image build fail.
- `pip install -e ".[dev]"` still works locally; it ignores the lock. `uv sync --locked --extra dev` reproduces CI.

**What stays the same**
- The floor job (#346) still resolves `lowest-direct` without the lock, so the lower bounds stay tested. The cap contract is unchanged.

**What is left out**
- The image carries the uv binary, about 32 MB. A multi-stage build could drop it, together with `gcc` and the `-dev` headers; that is a separate change.
- The Doc sync check job still installs with pip. It is path-filtered, regenerates documentation, and is not what ships.

**Rollback**
- Restore the two pip install lines, delete `uv.lock`, and switch the Dependabot entry back to `pip`.
