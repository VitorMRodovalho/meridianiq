# 0000. Record architecture decisions

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-17

## Context and Problem Statement

MeridianIQ has grown from a v0.1 prototype to v3.7.0 with 41 analysis engines, 107 API endpoints, 53 frontend pages, and ~20 supporting technology choices (database, hosting, auth, CSS framework, charting approach, PDF engine, JWT algorithm, MCP transport, and more). The rationale for each of those choices lives in commit messages, the CHANGELOG, and the maintainer's memory — none of which are a good long-term record.

When a future contributor (or a future version of the maintainer) asks *"why FastAPI instead of Django?"* or *"why Fly.io instead of AWS?"*, they need a quick, authoritative answer — not a spelunking expedition through three years of commits.

## Decision Drivers

- **Continuity of reasoning** — the *why* behind a choice decays faster than the choice itself.
- **Onboarding cost** — new contributors should be able to understand the shape of the system without reverse-engineering it.
- **Reversibility analysis** — when a tech choice no longer fits, we need to know what alternatives were considered and why they were rejected, so we can reopen the question with context.
- **Low maintenance overhead** — any process that requires more than 15 minutes per decision will be skipped.

## Considered Options

1. **Do nothing** — keep reasoning in commits and CHANGELOG.
2. **Long-form architecture doc** — one big `ARCHITECTURE.md` explaining every choice.
3. **Architectural Decision Records (ADRs) in MADR format** — one short markdown per decision, numbered, under `docs/adr/`.
4. **Wiki-based knowledge base** — decisions in GitHub Wiki or Notion.

## Decision Outcome

**Chosen: Option 3 — ADRs in MADR format under `docs/adr/`.**

### Rationale

- **Versioned with the code.** The decision and the code it justifies live in the same repository, so a PR that reverses a decision naturally updates the ADR alongside.
- **Diffable.** ADR changes show up in code review. A wiki does not.
- **Low ceremony.** A short MADR is ~150 words. Writing one takes 15–30 minutes; reading one takes 2 minutes. The cost is correct for the value.
- **Superseding instead of editing** — the history of how we *changed our mind* is as valuable as the current state.
- **Well-established format.** MADR has tooling, examples, and community familiarity. No invention required.

### Rejected alternatives

- **Do nothing** — the status quo. It's the reason this ADR exists. Commits and CHANGELOG capture *what* changed, not *why* we chose one of N options.
- **One big architecture doc** — tempting but too heavy. It atrophies because the cost of editing a large document to record a small decision is prohibitive, and because the doc's structure rarely anticipates future decisions. ADRs are composable; a monolithic doc is not.
- **Wiki** — fragments the knowledge layer. A decision that lives in a wiki is invisible when you're reading the code, and it doesn't travel with forks.

## Consequences

**Positive**:
- Every non-trivial architecture choice is captured.
- Future decisions can reference prior ADRs (e.g., "we're overriding ADR-0003 because…").
- New contributors have a curated reading list.
- `GOVERNANCE.md` can simply say "record architecture decisions as ADRs" without repeating the why.

**Negative**:
- Small overhead per decision.
- Discipline required — without it, ADRs become a backfill exercise instead of a real-time record.

**Neutral**:
- ADRs 0001–0005 are retroactive (written for decisions made between v0.1 and v3.7). Future ADRs are authored as part of the PR that introduces the change.
