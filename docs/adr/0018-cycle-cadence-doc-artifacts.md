# 0018. Cycle cadence doc artifacts

* Status: accepted — amended 2026-04-27 (**Amendment 1**: PR-level cadence — devils-advocate-as-second-reviewer protocol; see end of file)
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
- [AUDIT 2026-04-26](../audit/2026-04-26/README.md) — re-run per §5 of this ADR
- ADR-0009 §"Cycle 1 v4.0" (reference for the cycle concept)
- `.github/workflows/doc-sync-check.yml`

---

## Amendment 1 (2026-04-27) — PR-level cadence: devils-advocate-as-second-reviewer protocol

* Status: accepted
* Date: 2026-04-27
* Trigger: [ADR-0021 §"Open process gap"](0021-cycle-3-entry-floor-plus-field-shallow.md#open-process-gap) self-flagged the absence of in-repo codification; [AUDIT-2026-04-26-003 (P2)](../audit/2026-04-26/02-architecture.md#audit-2026-04-26-003) confirmed; tracked under [#42](https://github.com/VitorMRodovalho/meridianiq/issues/42).

### Context

ADR-0018 originally covered **cycle-close** cadence (the five doc artifacts in §"Decision"). The 2026-04-27 close-arc session of Cycle 2 organically established a complementary **PR-level** cadence — a "devils-advocate-as-second-reviewer" protocol used on every PR with non-trivial code or ADR-level content. The pattern proved robust across 12+ PRs (#33, #35, #36, #37, #38, #39, #47, #48, #49, #50, #51, #52) but lived only in maintainer memory + `docs/LESSONS_LEARNED.md` prose. AUDIT-2026-04-26-003 flagged this as a P2 process gap; ADR-0021 §"Open process gap" self-disclosed the absence; #42 tracks closure.

This amendment formalizes the PR-level cadence as a continuation of the cycle-cadence theme — same ADR, same source-of-truth for process discipline.

### The protocol

For PRs that touch ADR-level decisions OR substantive code changes:

1. **Open the PR.** Pre-code council (e.g., backend-reviewer + frontend-ux-reviewer in parallel) is recommended for waves and ADRs but is not strictly part of this PR-level cadence; the protocol below is the *exit* council.
2. **Dispatch DA review.** Run `Agent(subagent_type="devils-advocate", ...)` with a PR-specific prompt that names load-bearing claims to verify, framing risks to red-team, citations to spot-check, and severity questions to interrogate. A vague "review this PR" prompt produces shallow output — see §"Negative / accepted costs" below.
3. **Address blocking findings** in a fix-up commit on the same branch. Non-blocking findings either get addressed or get explicit defer-rationale entries in the structured comment of step 4.
4. **Post a structured comment** on the PR. Recommended sections (the standing template observed across PRs #38–#52):
   - **Blocking findings — FIXED in `<sha>`** (table: # / finding / fix)
   - **Non-blocking findings — FIXED** (table)
   - **Non-blocking findings — DEFERRED** (table with defer-rationale)
   - **What DA cleared** (verification passed bullets)
   - **Reframed claim** if any closure language was overstated in the PR body
   - **Updated counts** (tests added/removed, severity matrix shifts)
5. **Self-merge** via `gh pr merge <N> --rebase --delete-branch` — preserves the audit trail. The commit history shows the fix-up; the PR comment shows the review; the rebase choice keeps the fix-up commit distinct from the original work for forensic readability.

### Skip exceptions

The protocol is overhead. Skip when the surface is mechanical and risk-free:

- **Dependabot PRs** — CI is the review.
- **Catalog regen-only PRs** — mechanical script output.
- **1-line typo fixes** — risk = nil.
- **Doc-only LESSONS_LEARNED appends** — factual, no prescriptive content. PR #37 precedent.
- **ROADMAP / status-marking refreshes after a merged event** — derivative state. PRs #47, #49, #51 precedent.

When in doubt, run the protocol — false positives cost 5–10 min, false negatives cost 1–3 hours of post-merge cleanup.

### Rationale (empirical)

Across 12+ sample PRs (#33–#52) under the protocol:

- **DA review caught 2 blocking + 4 substantive non-blocking findings per PR on average.**
- Densest single PR: PR #38 (5 blocking + 5 non-blocking) on a Cycle 3 entry doc-only PR — denser than typical because ADR-level doc surface is large and citation-drift accumulates fast.
- Recurring categories:
  - **ADR-citation drift** — same class hit PR #36, PR #38, AND PR #50 (the audit that documents the class). The protocol catches its own recurrence.
  - **Severity miscategorization** — PR #50 reescalated AUDIT-2026-04-26-007 from P3 → P2 mid-review.
  - **Missed-finding addition** — PR #50 added AUDIT-2026-04-26-011 mid-review when DA discovered `src/__about__.py` had never existed.
  - **Honesty-debt slippage on closure claims** — PR #50's "structurally closes" framing reframed to "code-side closes; operator re-mat is required for end-to-end".

Time cost: ~2 min to dispatch + ~5–10 min to address findings. Time savings: a single caught blocking finding usually saves 1–3 hours of post-merge cleanup. The pattern is a strict positive on every empirical sample.

### Negative / accepted costs

- **Unenforced.** Same social-enforcement model as the cycle-cadence §"Decision". A maintainer can skip the protocol on any PR; the cost is higher review-surface variance. Future work could add a `.github/PULL_REQUEST_TEMPLATE.md` checkbox or a CI step that warns if a substantive PR has no DA-review comment, but neither is mandated here.
- **Prompt-engineering load.** The protocol's value depends on the DA agent being well-prompted. PR-specific framing (load-bearing claims, files to verify, severity questions) is what makes the protocol catch substantive findings. A boilerplate prompt produces boilerplate review.
- **Self-pressure-test bias.** This amendment was authored under the protocol it codifies. The empirical claims (12 PRs, 2+4 average, recurring drift class catches) are self-supporting evidence. The structural gap (no in-repo codification before this amendment) was real regardless of who confirmed it; the empirical data is real regardless of who collected it. PR #50 §"Disclosure" recorded a similar conflict-of-interest honestly. Future amendments to the protocol should note this and seek external validation when feasible.

### Cross-references

- [LESSONS_LEARNED.md Cycle 2 close-arc](../LESSONS_LEARNED.md) — empirical data + 5 close-arc lessons authored under the protocol
- [ADR-0021 §"Open process gap"](0021-cycle-3-entry-floor-plus-field-shallow.md#open-process-gap) — the gap-flag this amendment closes
- [AUDIT-2026-04-26-003 (P2)](../audit/2026-04-26/02-architecture.md#audit-2026-04-26-003) — formal audit finding
- Issue [#42](https://github.com/VitorMRodovalho/meridianiq/issues/42) — tracking

### Scope of what this Amendment does NOT do

- **Does not codify the 4-agent council protocol** (PV + strategist round 1 parallel; DA + IV round 2 paired) used for cycle-entry decisions. ADR-0021 §"Open process gap" flags both the PR-level protocol AND the cycle-entry council. The cycle-entry council operates on different rhythm (per-cycle, ~2/year) vs PR-level (per-PR, frequent), and its codification touches investor-view + strategist + product-validator surfaces beyond this amendment's scope. Reserved for a future Amendment 2 to ADR-0018 OR a separate ADR.
- **Does not enforce the protocol via CI.** Social enforcement only. PR-template checkbox + review-comment heuristic CI step are explicit future work.
- **Does not create a `docs/adr/cycles/cycle-N/` directory** with audit-grade council outputs (the alternative ADR-0021 §"Open process gap" suggested). The PR-level protocol leaves its trail in the PR comment + commit history; cycle-entry councils would need this if/when Amendment 2 lands.
