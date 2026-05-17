<!-- Authored 2026-05-17 evening (Cycle 6 W0) — operator runbook for H-shape per ADR-0025 -->

# Cycle 6 — Operator Runbooks

This document collects the **operator-paced** items relevant to Cycle 6 H-shape execution per [ADR-0025](../adr/0025-cycle-6-entry-h-shape.md). All items here require maintainer (operator) action; Claude can prepare templates and audit-trail but cannot execute outreach or persona retirement decisions.

| # | Title | Trigger | Estimated time | Difficulty | Section |
|---|---|---|---|---|---|
| W0-OPS-01 | Operator decisions at ratification (A/A/B/B/A) — historical record | One-time at Cycle 6 W0 (DONE 2026-05-17) | n/a — completed | n/a | [§W0-OPS-01](#w0-ops-01--operator-decisions-at-ratification--done-2026-05-17) |
| W2-OPS-01 | Pathway A — 5 customer-development conversations | Cycle 6 W0-W2 (~2 weeks to 2026-05-31) | 30-60 min/conversation + 10 min logging | High (cold/warm outreach) | [§W2-OPS-01](#w2-ops-01--pathway-a-execution-5-cd-conversations) |
| W2-OPS-02 | Pathway B — 1 persona formally retired with ADR | Cycle 6 W0-W2 (alternative to Pathway A) | 1-2 hours (outreach attempt + null wait + ADR drafting) | Medium (clean structural exit) | [§W2-OPS-02](#w2-ops-02--pathway-b-execution-1-persona-formally-retired) |
| W2-OPS-03 | W2 GATE close synthesis | Cycle 6 W2 close (~2026-05-31) | 30 min | Low (audit trail) | [§W2-OPS-03](#w2-ops-03--w2-gate-close-synthesis) |
| W2-OPS-04 | Cycle 6.5 amendment ADR (IF W2 GATE fails OR cosmetic-met) | Cycle 6 W2+1 (conditional) | 1-2 hours | Medium | [§W2-OPS-04](#w2-ops-04--cycle-65-amendment-adr-template) |

**Standing protocol:** Each operator action ends with a "Registry" step. Update tracking issue [#134](https://github.com/VitorMRodovalho/meridianiq/issues/134) as evidence accumulates. Cycle 7 entry council reads issue #134 + this runbook to judge GATE outcome on Pathway A/B HONEST criteria.

---

## W0-OPS-01 — Operator decisions at ratification — ✅ DONE 2026-05-17

Per [ADR-0025 §"Operator decisions required at ratification"](../adr/0025-cycle-6-entry-h-shape.md). Captured at [PR #135 comment](https://github.com/VitorMRodovalho/meridianiq/pull/135#issuecomment-4469468635).

| # | Decision | Choice | Operative consequence |
|---|----------|--------|----------------------|
| 1 | W2 GATE criteria | **A — keep as-written** | 5 CDs OR 1 persona-retirement-ADR per Pathway A/B HONEST. W2 close ~2026-05-31. |
| 2 | Personas eligible for Pathway B | **A — all 7 eligible** | Owner / Program Director / Cost Engineer / Subcontractor / Field Engineer / Consultant-Claims SME / PMO Director |
| 3 | Prompt caching ADR scope | **B — defer to Cycle 7** | Removed from Cycle 6 W4 scope. $0 SOM = $0 ROI; coherent with DROPPED "AI cost moat" framing. |
| 4 | ADR-0024 + ADR-0025 lineage sign-off | **B — sign with caveat** | Sign off lineage; Cycle 7 entry council protocol amendment question pre-registered: "Should Round 1 agents be required to challenge planning memo candidate pool BEFORE proposing scope?" |
| 5 | Pathway A/B HONEST distinction | **A — accept as-written** | Criteria in ADR-0025 §"Honest GATE vs cosmetic GATE distinction" govern Cycle 7 council judgment. Cosmetic-met → Cycle 7 inherits Cycle 6.5 obligations. |

---

## W2-OPS-01 — Pathway A execution (5 CD conversations)

**Trigger:** Cycle 6 W0-W2. W2 close ~2026-05-31.

**Goal:** 5 customer-development conversations logged honestly (per Pathway A HONEST criteria from [ADR-0025](../adr/0025-cycle-6-entry-h-shape.md)).

### Pre-flight checklist

- [ ] Confirmed W2 close target date (default: 2026-05-31; amendable per ADR-0025 op decision 1)
- [ ] Selected 5-8 outreach targets (over-recruit to account for null/non-response)
- [ ] Confirmed targets are external parties without prior MeridianIQ relationship OR have documented prior interest signal
- [ ] Drafted conversation script (see §"Conversation script template" below)
- [ ] Created tracking row in [#134](https://github.com/VitorMRodovalho/meridianiq/issues/134) per conversation as it happens

### Outreach attempt script template

> **Use case 1 — AACE/PMI working-group inquiry (warm outreach via existing membership):**
>
> Subject: MeridianIQ — open-source P6 schedule intelligence platform — feedback request
>
> Hi [name], I'm a fellow [AACE TCM / PMI-CP] member working on an open-source schedule intelligence platform called MeridianIQ. It implements [N] analysis engines including DCMA 14-Point, AACE RP 14R-90 critical path, EVMS forensics, and lifecycle phase inference — all citing published standards.
>
> Two questions if you have 15-20 min:
> 1. What's the schedule-quality pain you currently feel that incumbent tools (P6 / Acumen Fuse / Phoenix) don't address?
> 2. Would a [specific MeridianIQ capability that maps to their named role] be useful in your work, or is the problem elsewhere?
>
> Happy to do this async by email or 20-min call. No sales context — I'm pre-revenue and gathering signal before deciding what to ship next.

> **Use case 2 — paid-product prospect conversation:**
>
> (Same opening, but explicit "I'm exploring whether to commercial-license a Pro tier" framing if appropriate.)

> **Use case 3 — design-partner inquiry (warmer, more committed):**
>
> (Same opening + "Would you be willing to be a design partner — meaning I prioritize your specific use case in exchange for ~3 conversations over the next 60 days?")

### Conversation logging template

For each conversation, log in #134 as:

```
### CD #N — [Date]
- Party: [Name / org / role]
- Persona pertinence: [Owner / GC / Subcontractor / Consultant-Claims / PMO Director / Cost Engineer / Risk Manager / Program Director / Field Engineer]
- Prior MeridianIQ relationship: [None / Documented prior interest (cite)]
- Topic: [substantively engaging MeridianIQ's specific value prop — NOT generic scheduling-tools conversation]
- Substantive engagement quote-grade: [Specific quote or observation showing they understood MeridianIQ's specific value prop, not generic tool discussion]
- Outcome: [Specific feature request / persona-validating observation / explicit interest signal / explicit disinterest signal / named next action]
- Could this have happened without MeridianIQ existing? [Yes/No] (if Yes → mark cosmetic-met flag)
- Next action: [Date + ask if applicable]
```

### Honest vs cosmetic flag (CRITICAL)

If 5 CDs logged but ≥3 marked "cosmetic-met" (conversation could have happened without MeridianIQ existing), **Cycle 7 council will judge the GATE met cosmetically**. Cycle 6.5 obligations apply regardless of headcount.

The cosmetic-met failure mode is logged honestly in #134 — Cycle 7 council judges based on the operator's own honesty about cosmetic flags. Do NOT shade the cosmetic flag to satisfy headcount. The pre-registration discipline IS that the operator self-reports honestly.

### Failure mode — outreach yields fewer than 5 substantive CDs

Switch to Pathway B (§W2-OPS-02) and use the failed-outreach attempts as evidence for persona retirement Pathway B HONEST criteria #1 ("≥1 actual outreach attempt was made AND received no response OR explicit disinterest").

---

## W2-OPS-02 — Pathway B execution (1 persona formally retired)

**Trigger:** Cycle 6 W0-W2. Alternative to Pathway A.

**Goal:** Retire 1 persona from the 7 active per Pathway B HONEST criteria from [ADR-0025](../adr/0025-cycle-6-entry-h-shape.md). Converts perpetual "deferred" status to closed scope.

### Pre-flight checklist

- [ ] Selected candidate persona for retirement (operator's call from all 7 per op decision 2)
- [ ] Made ≥1 outreach attempt to candidate persona's representative AND documented null response OR explicit disinterest (per Pathway B HONEST criterion #1)
- [ ] Inventoried issues/features that would be closed/deprecated by this persona's retirement (per criterion #2 closed scope)
- [ ] Drafted Cycle 7+ reactivation pre-condition OR explicit "no reactivation path" (per criterion #3)

### Persona-retirement-ADR template (ADR-0026 reserved if retired)

```markdown
# ADR-0026 — Cycle 6 W2 Pathway B retirement of [PERSONA NAME]

* Status: proposed
* Deciders: @VitorMRodovalho
* Date: 2026-MM-DD
* Cites: [ADR-0025](0025-cycle-6-entry-h-shape.md) §"Decision" Pathway B; [ADR-0025 §"Honest GATE vs cosmetic GATE distinction"](0025-cycle-6-entry-h-shape.md)
* Cycle: 6 W2 HARD GATE closure (criterion #3)

## Context

Per ADR-0025, Cycle 6 W2 HARD GATE requires 5 CD conversations logged OR 1 persona formally retired with ADR. Operator selected Pathway B (persona retirement) for [reason — e.g., outreach yielded fewer than 5 substantive CDs / strategic call to retire lowest-optionality persona / etc.].

[PERSONA NAME] has been listed in active persona scope across Cycles 1-5 (5 cycles), with the following deferral framing in each:

| Cycle | Cycle entry framing | Action taken |
|-------|---------------------|--------------|
| 1 | [e.g., "negative — deferred"] | [e.g., "no scope work"] |
| 2 | [framing] | [action] |
| 3 | [framing] | [action] |
| 4 | [framing] | [action] |
| 5 | [framing] | [action] |

## Outreach attempt evidence (Pathway B HONEST criterion #1)

| Date | Channel | Recipient | Outcome |
|------|---------|-----------|---------|
| 2026-MM-DD | [email / LinkedIn / AACE-PMI member channel / cold] | [name + org if disclosable; "redacted role" otherwise] | [null response after N weeks OR explicit disinterest with quote] |

[Add 1+ rows. NOT honest if zero actual attempts were made.]

## Closed scope (Pathway B HONEST criterion #2)

Issues to close as `wontfix` upon ADR ratification:
- #[issue] — [title]
- #[issue] — [title]

Features to deprecate (mark as out-of-scope in README + remove from ROADMAP):
- [feature 1]
- [feature 2]

## Reactivation path (Pathway B HONEST criterion #3)

[Choose ONE:]
- **Cycle N+ reactivation pre-condition**: [PERSONA NAME] reactivates as active scope IF [specific external evidence — e.g., ≥2 paid prospects from this persona category make explicit inquiry, OR AACE/PMI working group publishes guidance specifically about this persona's workflow]
- **No reactivation path**: [PERSONA NAME] is retired permanently. Cycle 7+ candidate pool does not list this persona.

## Decision

Adopt retirement of [PERSONA NAME] from active persona scope per Cycle 6 W2 HARD GATE Pathway B per ADR-0025.

## Consequences

**Positive:**
- Cycle 6 W2 HARD GATE criterion #3 met honestly via Pathway B
- Active persona scope contracts from 7 to 6 — Cycle 7+ candidate pool simplified
- "Deferred forever" perpetual status converted to closed scope (eliminates PV escalation framing pathway for this persona)
- [persona-specific consequence]

**Negative:**
- Irreversible scope contraction (per reactivation path — explicit no-path OR conditional)
- Issues marked `wontfix` may bias future contributors away from related work
- [persona-specific consequence]

**Risks:**
- If reactivation pre-condition emerges later, recovery requires net-new ADR (not just resurrection)
- Other 6 personas may inherit "next on the retirement block" signaling
```

### Failure mode — cosmetic retirement detected

If retirement ADR fails Pathway B HONEST criterion #1 (no actual outreach attempt) OR criterion #2 (no genuine closed scope), **Cycle 7 council will judge the GATE met cosmetically**. Same consequence as Pathway A cosmetic-met: Cycle 6.5 obligations apply.

The most common cosmetic failure mode: retire a persona that was already implicitly dead (e.g., never had any associated open issues, never appeared in cycle scope memos in the first place). The ADR's "Cycles 1-5 framing table" + "Closed scope" rows are the audit-trail check.

---

## W2-OPS-03 — W2 GATE close synthesis

**Trigger:** Cycle 6 W2 close target date (~2026-05-31).

**Goal:** Synthesize W2 GATE outcome + update issue #134 + notify Claude for Cycle 6 next-step branching.

### Steps

1. **Sum up Pathway A + Pathway B + Pathway C (mixed) evidence** logged in #134.
2. **Self-honesty check**:
   - For each CD: re-examine the "could this have happened without MeridianIQ existing?" flag. Be honest.
   - For Pathway B retirement: re-examine the outreach attempt evidence. Was it a substantive attempt or a CYA email?
3. **GATE outcome decision** — one of:
   - **MET HONESTLY** (Pathway A: ≥5 substantive CDs with ≤2 cosmetic flags; Pathway B: 1 retirement ADR satisfying all 3 HONEST criteria; Pathway C: equivalent rigor mix)
   - **MET COSMETICALLY** (headcount satisfied but Pathway A/B HONEST criteria failed) — Cycle 7 inherits Cycle 6.5 obligations
   - **NOT MET** — Cycle 6.5 amendment ADR triggers (§W2-OPS-04)
4. **Update #134** with synthesis + close OR convert to Cycle 6.5 tracking
5. **Notify Claude** in next session: "Cycle 6 W2 GATE outcome = [MET HONESTLY / MET COSMETICALLY / NOT MET]. Proceed to [W3-W5 conditional execution / Cycle 7 entry with Cycle 6.5 obligations / Cycle 6.5 amendment ADR draft]."

### Registry checklist

- [ ] #134 updated with full synthesis + outcome decision
- [ ] PR #135 comment (or new ADR-0025 amendment PR) added if amendment to GATE specifics emerged
- [ ] If Pathway B used: ADR-0026 PR drafted + reviewed + merged
- [ ] Next-session Claude briefing prepared

---

## W2-OPS-04 — Cycle 6.5 amendment ADR template

**Trigger:** W2 HARD GATE NOT met by close OR met cosmetically.

**Goal:** Honest amendment of ADR-0025 to pivot remaining waves to discovery-only.

### Cycle 6.5 amendment ADR template (ADR-0026 reserved if amendment needed)

```markdown
# ADR-0026 — Cycle 6.5 amendment: pivot to discovery-only after W2 GATE [NOT MET / MET COSMETICALLY]

* Status: proposed
* Deciders: @VitorMRodovalho
* Date: 2026-MM-DD (W2+1)
* Cites: [ADR-0025](0025-cycle-6-entry-h-shape.md) §"Cycle 6.5 patch trigger conditions"

## Context

Cycle 6 W2 HARD GATE per ADR-0025 reached close on [date]. Outcome:
- Pathway A: [N CDs logged; M cosmetic-met flagged; rationale]
- Pathway B: [0 or 1 persona retirement ADR drafted; HONEST criteria met or failed]
- Aggregate: [NOT MET / MET COSMETICALLY]

Per ADR-0025 Cycle 6.5 trigger condition (a) [or (e)], remaining wave budget reallocates to discovery-only.

## Decision

Amend ADR-0025 wave plan:
- **W3-W5 (conditional) CANCELED**. Frontend DA cluster (#105/#106/#107/#108/#110/#46), backend P3 (#117/#119/#120), Fly autosuspend, hygiene close, mypy slice, CI floor-verify step — all DEFERRED to Cycle 7+.
- **W3-W5 budget reallocated** to discovery-only execution:
  - W3-W4: Additional outreach attempts (target: log 5+ more substantive CDs OR persona-retirement-ADRs across the remaining 2-3 weeks).
  - W5: Cycle 6 close synthesis — what was learned about each attempted persona; what reactivation pre-conditions remain.

Release tag for Cycle 6:
- **No `v4.4.0` minor release** (Bucket B floor bumps already shipped via W1 hygiene PR; release class drops to patch)
- **`v4.3.1` patch** released at Cycle 6 close documenting:
  - Bucket B floor bumps (security hygiene)
  - W2 GATE outcome (NOT MET / MET COSMETICALLY)
  - Discovery-only pivot rationale
  - Cycle 7 entry council pre-conditions accumulated

## Consequences

**Positive:**
- Honest amendment per ADR-0025 Cycle 6.5 trigger conditions
- Discovery-only sprint = first such cycle in MeridianIQ history; provides operator with focused customer-development experience
- Releases pressure on Cycle 7 entry council to invent yet another consolidation framing
- 4 sycophancy framings stay DROPPED with sycophancy-recurrence trigger still active

**Negative:**
- 4 P3 carryover follow-ups (#105/#106/#107/#108/#110/#46/#117/#119/#120) defer further to Cycle 7+
- Release tag class drops to patch — public signal of constrained cycle
- Pattern of "Cycle N can't ship the full plan" becomes a 2nd consecutive data point (Cycle 5 dropped W5 Z-IV, Cycle 6 drops W3-W5)

**Risks:**
- Discovery-only sprint itself produces 0 substantive CDs (base-rate scenario per IV Cycle 6 finding)
  - If so, Cycle 7 entry council faces explicit "formally pivot OSS thesis OR retire project to maintenance mode" decision per ADR-0025 §"Risks" #2

## Operator decisions required at Cycle 6.5 ratification

1. Confirm discovery-only sprint targets (number of outreach attempts; deadline for Cycle 6 close)
2. Confirm release tag class (`v4.3.1` patch vs hold for Cycle 7)
3. Optional: pre-commit Cycle 7 entry framing if maintainer wants to lock the question now (e.g., "Cycle 7 = explicit pivot/maintenance-mode decision council")
```

---

## Standing references

- [ADR-0025](../adr/0025-cycle-6-entry-h-shape.md) — Cycle 6 entry H-shape
- [LESSONS_LEARNED.md](../../LESSONS_LEARNED.md) — Cycle 6 entry section (6 anti-sycophancy lessons banked)
- Issue [#134](https://github.com/VitorMRodovalho/meridianiq/issues/134) — W2 HARD GATE tracking + Pathway A/B HONEST template
- [PR #129](https://github.com/VitorMRodovalho/meridianiq/pull/129) — Bucket A pre-W0 unconditional (DONE)
- [PR #135](https://github.com/VitorMRodovalho/meridianiq/pull/135) — ADR-0025 ratification (DONE)
- `memory/project_v40_cycle_6.md` — operator-only scope memo (private)
