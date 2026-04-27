# MeridianIQ Governance

This document describes how MeridianIQ is maintained and how decisions are made. It is deliberately short — the project is solo-maintained today, and this file codifies just enough process to keep the repo healthy as it grows.

## Maintainer

| Role | Person | Contact |
|---|---|---|
| Lead maintainer | Vitor Maia Rodovalho | `vitor.rodovalho@outlook.com` |
| Security contact | Same | See `SECURITY.md` |

A single maintainer holds the commit bit. Additional maintainers are added by the lead maintainer when a regular contributor demonstrates sustained quality over multiple releases.

## Decision-making

- **Day-to-day code decisions** — maintainer judgement, with published standards (AACE, DCMA, SCL, AIA, PMI) as the tie-breaker when methodology is involved.
- **Architectural decisions** — recorded as an ADR under [`docs/adr/`](docs/adr/). Any change that (a) adds/removes a dependency category, (b) changes how users deploy, or (c) reshapes the module boundaries is an ADR.
- **Breaking changes** — require a major version bump and a migration note in `CHANGELOG.md`.

### Process discipline

- **Cycle-close cadence** — five doc artifacts updated at every cycle close per [ADR-0018 §"Decision"](docs/adr/0018-cycle-cadence-doc-artifacts.md): `ROADMAP`, `BUGS` pruning, `LESSONS_LEARNED` append, catalog regen, audit re-run.
- **PR-level cadence** — devils-advocate-as-second-reviewer protocol on PRs touching ADR-level decisions or substantive code per [ADR-0018 Amendment 1](docs/adr/0018-cycle-cadence-doc-artifacts.md#amendment-1-2026-04-27--pr-level-cadence-devils-advocate-as-second-reviewer-protocol). Skip exceptions documented; social enforcement (no CI gate today).

## Release cadence

- **Target**: one minor release per month when active work is landing; faster if a P1 item is ready in isolation.
- **Patch releases** — on demand when a released version has a blocking bug.
- **Major releases** — reserved for breaking API/data-model changes. Never forced by the calendar.
- **Semver rules**:
  - `MAJOR` — breaking API/data-model
  - `MINOR` — new methodology engine, new endpoint, new page, new export format, new PDF report type, new MCP tool
  - `PATCH` — bug fixes, dependency bumps, doc-only changes
- **Release process** — run the `/release <version>` slash command (`.claude/commands/release.md`). It gates on clean tree + green CI + forward semver, syncs doc catalogs, commits, tags (annotated), pushes, creates the GitHub release, and monitors CI.

## Archive policy

**`docs/archive/vX-planning/`** — planning documents move here when superseded by a later planning cycle. Move on the first commit of the next major version. Never delete; the archive tells the story of how the product evolved.

**`archive/v1-power-bi-models/`** — legacy Power BI deliverables from the pre-v0.1 era. Frozen. No new content goes there.

**`src/legacy/`** (future) — code that is deprecated but still compiled. Stays for ≥1 minor release before deletion. Deletion happens in a minor bump with a `Removed` entry in `CHANGELOG.md`.

**When in doubt**: archive, don't delete. A forked project's history is priceless.

## Triage cadence

- **Bugs** (GitHub issues with `bug` label) — triaged within 48 hours. Critical or security-sensitive bugs are fixed in a patch release within one week; others queue for the next minor.
- **Feature requests** (`enhancement` label) — reviewed at the start of each release cycle against `project_backlog.md` priorities.
- **Discussions** — opened publicly; maintainer reads but does not guarantee a response time.
- **Security reports** — see [`SECURITY.md`](SECURITY.md) for the private disclosure flow.

## Confidentiality

- **No client, project, or company names** ever appear in this repository, commits, branch names, PR titles, or release notes. If an incident surfaces such data, redact and force-push-with-care (maintainer only) before the commit is referenced elsewhere.
- **Synthetic test fixtures only.** Real XER / cost / risk data is kept outside the repository.
- **Sensitive research or planning** that does not belong in the public repo lives in the private companion repo (`meridianiq-private`, by invitation).

## Communication

- Public discussions: GitHub issues and Discussions.
- Security: email listed in `SECURITY.md`.
- Private/business: maintainer's email listed above.

## Changing this document

This file evolves. Changes are made through a normal pull request. The commit message should explain the motivation for the governance change, and a line item should be added to `CHANGELOG.md` under `Changed`.
