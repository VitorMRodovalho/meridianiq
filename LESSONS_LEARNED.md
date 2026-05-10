# MeridianIQ — Lessons Learned

This document collects **process + technical lessons** learned across MeridianIQ release cycles. Format follows the cycle structure: each entry summarizes a specific failure mode (or near-miss) and the discipline that closes it.

The intent is **future-self utility**: when planning a similar wave or PR, scan the relevant cycle entry for the failure modes already encountered.

---

## Cycle 5 — Z-shape consolidation (closed at `v4.3.0`, 2026-05-09)

Authored 2026-05-09 evening at cycle close. Per ADR-0024 success criterion 8.

### Process lessons

#### L5.1 — Entry-council MANDATORY on substantive scope, regardless of priority label

- **Setup**: PR #104 (W3 PR-A, pre-Cycle-5 W3-A) was P3-priority (a polish PR per the cycle planning). The reviewer council was skipped on the assumption "P3 priority = P3 correctness-risk = no council needed".
- **What happened**: 4 P0 findings surfaced post-impl (2 in DA exit-council, 2 in user QA). Inversion of `direction = sign(cusum_value)` to `sign(delta_days)`, missing `methodology=""` fallback on error path, etc.
- **Discipline that closes it**: `feedback_entry_council_discipline.md` — backend/frontend-reviewer entry-council MANDATORY on substantive scope (schema-additive, semantic-mapping, wrapper additions). **Size is NOT a valid skip criterion. Priority is NOT a valid skip criterion.** This lesson was already codified in memory before Cycle 5; Cycle 5 reinforced it with 5/5 W3 PRs running entry-council.

#### L5.2 — DA exit-council finds what entry-council misses

- **Pattern across W3**: 5/5 W3 PRs went through both entry-council (pre-impl) AND DA exit-council (post-impl).
- **DA findings count**: PR #115 (3 P1 + 1 P2), PR #116 (3 P1 + 4 P2/P3), PR #118 (2 P1 + 4 P2/P3). All 8 P1s addressed inline; the P2/P3s tracked as follow-up issues.
- **Lesson**: Entry-council validates feasibility + UX; DA exit-council validates correctness post-implementation. They are **complementary, not redundant**. Skipping either hurts the cycle.

#### L5.3 — Honest framing on missed targets is the discipline, not target avoidance

- **Setup**: Cycle 5 W4 hygiene memo target was "0 mypy `--strict` errors". Realistic baseline pre-stubs was 306 errors; post-stubs is 350 (stubs reveal previously-masked errors).
- **What happened**: Hit the "0 errors" target was unachievable in W4 scope. Two paths considered: (a) descope W4 (don't add stubs), (b) ship stubs + honest framing in CHANGELOG + file follow-up.
- **Choice**: Path (b). CHANGELOG documents "stubs in place" milestone instead of "0 errors achieved", with explicit framing on why the count went UP. Filed [#121](https://github.com/VitorMRodovalho/meridianiq/issues/121) for systematic cleanup.
- **Lesson**: This pattern repeats from Cycle 1 W4 + Cycle 4 W4 path-A activations. **The discipline is naming the target reset honestly, not avoiding the work that requires it.** Every cycle that lands a partial-target comes with public framing in CHANGELOG; future contributors get the real picture.

#### L5.4 — Single-PR vs split: blast-radius cost vs review cohesion

- **Setup**: PR #118 (W3-E, #84) was the largest PR in the wave: 875 LoC across 12 files (migration, store, endpoints, schemas, tests, frontend wire, i18n).
- **Choice offered to user**: Single-PR vs split into W3-E1 (backend) + W3-E2 (frontend). User chose single-PR.
- **Outcome**: Single-PR succeeded; review surface large but cohesive. DA exit-council still found 2 P1 (silent dev/prod count divergence + skip race), addressable inline.
- **Lesson**: Single-PR is the right call when the change is **internally coupled** — backend table + endpoint + frontend wire all need to land together for the feature to work. Split is the right call when the layers are **independently shippable** (e.g., a refactor that doesn't change behavior). #84 was the former.

#### L5.5 — Stats-catalog regen is a pre-PR mental checklist item, not a CI auto-recovery

- **Setup**: PR #118 added 2 endpoints + migration 029. First push to PR triggered CI failure on "Verify catalogs match source" (endpoint count drift 127 → 129; migration count 28 → 29).
- **What happened**: Took an extra commit (and CI cycle) to fix.
- **Discipline that closes it**: When a PR adds endpoints, run `python scripts/generate_api_reference.py` locally before pushing. Same for migrations + the README/CLAUDE.md/architecture.md catalog references.
- **Lesson**: The CI gate is the safety net, not the primary check. Adding a "regenerate catalogs" reminder to the PR-creation mental checklist saves an extra round-trip.

### Technical lessons

#### L5.T1 — PostgREST DELETE without `Prefer: return=representation` returns empty body

- **Setup**: PR #118 `clear_revision_skips` SupabaseStore helper returned `len(res.data or [])` from a `.delete().eq().eq().execute()` chain.
- **Failure mode**: PostgREST DELETE without explicit `returning` parameter returns NO body. `res.data` is `[]` even when N rows were deleted. **`cleared_count` would always be 0 in production while InMemoryStore tests pass.** Frontend's `cleared_count === 0` toast fires incorrectly + telemetry permanently 0.
- **DA exit-council**: caught this during PR #118 review. Same dev/prod divergence shape as BUG-007 / PR #104 silent-no-op precedent / tombstone audit_log_id race.
- **Fix**: Two-round-trip pattern (SELECT then DELETE, return SELECT count). Extra round-trip on a manual-button reconsider call (rare, operator-paced) is acceptable and dodges the supabase-py version-contract question.
- **Lesson**: ALWAYS verify SDK-level return-shape contracts when porting from InMemoryStore to SupabaseStore. The InMemoryStore is a TEST DOUBLE, not a CONTRACT MIRROR.

#### L5.T2 — Svelte 5 runes work in `@testing-library/svelte` v5 + jsdom

- **Setup**: PR #114 (W3-B) needed a Vitest harness for RevisionConfirmCard.
- **Spike result**: `@testing-library/svelte@5.3.1` + Svelte 5.55.5 + jsdom 29 + Vitest 4 — `$state` / `$derived` / `$effect` / `$props` all work without Playwright dependency.
- **Lesson**: `vitest-browser-svelte` (browser + Playwright) was the alternative path; the spike validated jsdom is sufficient for component tests today. Saved a Playwright dependency + browser CI infrastructure overhead. **30-minute spikes pay for themselves.**

#### L5.T3 — `Intl.DateTimeFormat` defaults to viewer-local TZ; force UTC for domain-naive dates

- **Setup**: PR #115 (W3-C) `formatDate` helper for revision-confirmation card data_date.
- **Failure mode**: P6 `data_date` is timezone-naive by domain convention. `Intl.DateTimeFormat` defaults to the viewer's local TZ — a UTC midnight ISO `2026-04-15T00:00:00Z` viewed in UTC-3 renders as "Apr 14".
- **Discipline that closes it**: Force `timeZone: 'UTC'` in options. Make the override **non-overridable at TypeScript level** via `Omit<Intl.DateTimeFormatOptions, 'timeZone'>` so callers compile-fail rather than fail silently. DA exit-council on PR #115 caught a fallback day-shift bug for offset-bearing ISOs (the `iso.slice(0, 10)` shortcut also breaks here); switched fallback to `parsed.toISOString().slice(0, 10)`.
- **Lesson**: When formatting dates from domain-specific schemas (P6 data_date, contract dates, baseline_lock_at, etc.), be explicit about TZ semantics in the helper signature. Viewer-local default is the wrong policy for domain-naive dates.

#### L5.T4 — Structured `error_code` > fragile text-match for 4xx differentiation

- **Setup**: PR #116 (W3-D) replaced text-pattern detection of cap-vs-other 4xx errors (introduced in PR #83) with structured `error_code` field on the response body.
- **Failure mode the structured form prevents**: a future i18n change that translates "revision cap reached" → "limite de revisões atingido" would break the `/revision cap/i` regex match silently, and the localized cap message would never surface.
- **Caveat**: PR #116 itself introduced fragile text-match on the cap-vs-unique disambiguation at `revisions.py:215-217` (`"cap" in message.lower()`). DA exit-council caught it. Filed [#117](https://github.com/VitorMRodovalho/meridianiq/issues/117) for typed-exception refactor.
- **Lesson**: When designing API error contracts, **use machine-readable codes**, not human-readable text. When implementing one error contract, audit your OWN code for the same anti-pattern you're fixing.

### Cycle-close discipline reinforced this cycle

- **6/6 PRs ran DA exit-council** per ADR-0018 Amendment 1
- **5/5 W3 PRs ran entry-council** per `feedback_entry_council_discipline.md`
- **4 follow-up issues filed** during cycle (#117 / #119 / #120 / #121) — each tracked specifically vs left as TODO comments in code
- **Honest CHANGELOG framing** on W4 partial close
- **Memory file refresh** at cycle close (`project_state.md` + `project_resume_next_session.md`)

---

## Future cycles

Each cycle close should append a new section above this one. Do NOT delete prior cycles' lessons — they accumulate as repository memory.
