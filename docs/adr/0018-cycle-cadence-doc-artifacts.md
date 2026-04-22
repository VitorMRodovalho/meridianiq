# 0018. Cycle cadence doc artifacts

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-22
* Triggered by: 2026-04-22 structural audit — [AUDIT-006/007/011 doc-drift](../audit/06-planned-vs-implemented.md#doc-drift--catálogo) and `docs/GAP_ASSESSMENT_v3.3.md` stalecontent

## Context and Problem Statement

The 2026-04-22 audit found that several foundational docs drifted out of sync
with runtime between v3.3 and v4.0.1:

- `README.md §Key Numbers` listed 40 engines / 98 endpoints / 52 pages / 870
  tests against a real 47 / 121 / 54 / 1350.
- `CLAUDE.md` carried the "no web/Dockerfile yet" note long after BUG-011
  closed.
- `SECURITY.md §Supported Versions` and `BUGS.md` header both still advertised
  `v3.6.x` / `v3.6.0-dev` against production `v4.0.1`.
- `docs/GAP_ASSESSMENT_v3.3.md` sat at the `docs/` root and appeared current to
  any new reader.
- No top-level `ROADMAP.md` — the only source of forward plan was ADR-0009
  (a cycle-specific, internal document).
- `docs/LESSONS_LEARNED.md` dated 2026-04-02, two cycles stale.

The root cause is that the project has a **release cadence** (CHANGELOG entry
per tag) but no **cycle cadence** for the meta-docs that exist between
commits and releases. Things silently decay.

## Decision Drivers

- A contributor joining mid-project should see current state, not 2-cycle-old
  claims.
- Re-running the audit should be cheap, mechanical, and expected — not a
  one-off.
- Each cycle close is a natural checkpoint for the meta-docs; more frequent
  would be thrash, less frequent is what produced this drift.

## Decision

At the close of every cycle (today the unit is a "cycle" as defined by
ADR-0009 and its successor ADR pattern), the Chairman commit must include or
be immediately followed by a commit updating these five artifacts:

1. **`docs/ROADMAP.md`** — forward-looking 1-page doc listing the next cycle's
   committed scope + the next-next cycle's tentative scope + deferred items
   with links to the ADR or issue that parked them. Supersedes the fragmented
   view currently held in ADR-0009 / `docs/SCHEDULE_VIEWER_ROADMAP.md`. First
   version authored as part of Cycle 2 kickoff.
2. **`BUGS.md` backlog pruning** — move resolved items to
   `docs/archive/BUGS_HISTORY.md` if older than two cycles, update the header
   to the current version, keep the active bugs + feature backlog + technical
   debt sections slim.
3. **`docs/LESSONS_LEARNED.md`** — append one entry per cycle with:
   cycle identifier, what shipped, what the gate found, what we would do
   differently. Append-only; never edit past entries.
4. **Catalog regeneration** — run the three `scripts/generate_*.py` plus
   `scripts/check_stats_consistency.py` and commit any drift. Already wired
   into `doc-sync-check.yml`; this ADR formalizes that it is **cycle-close
   mandatory**, not opportunistic.
5. **Audit re-run** — a new `docs/audit/YYYY-MM-DD/` directory following the
   6-layer structure of the 2026-04-22 baseline. Findings become GitHub issues
   with the `audit-YYYY-MM-DD` label.

## Consequences

**Positive**

- Drift becomes impossible to accumulate across cycles without being caught
  at close.
- New contributors have a predictable contract: one place for roadmap, one
  place for lessons, one audit per cycle.
- Historical artifacts (old audits, archived bug history) accumulate in
  `docs/archive/` and `docs/audit/<date>/`, giving a readable long-term
  record.

**Negative / accepted costs**

- ~1-2 hours of doc work per cycle close. Mitigated because the audit re-run
  is largely mechanical (the 2026-04-22 methodology section of
  `docs/audit/README.md` is the checklist) and the catalog scripts are
  already automated.
- If a cycle closes without the 5 artifacts updated, a follow-up commit is
  required; enforced socially for now rather than by a pre-commit hook
  (future work if observed to fail).

## Scope of what this ADR does NOT require

- No new tools or scripts beyond the already-existing
  `scripts/generate_*.py` and `scripts/check_stats_consistency.py`.
- No formal "cycle close" ceremony or meeting — this is a solo / small-team
  project.
- No retroactive archival of docs from cycles already closed; start with
  Cycle 2.

## Related

- [AUDIT 2026-04-22](../audit/README.md)
- ADR-0009 §"Cycle 1 v4.0" (reference for the cycle concept)
- `.github/workflows/doc-sync-check.yml`
