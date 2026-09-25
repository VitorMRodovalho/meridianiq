# 0030. Tenant access rule: one access context, owner-only, 404 when hidden

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-09-25
* Cites: [ADR-0013](0013-websocket-progress-hardening.md) (job-channel close codes, unchanged), `src/api/access.py`

## Context and Problem Statement

The backend reads Supabase with the service-role key, so Postgres RLS does not scope API reads. Tenant scoping therefore lives in application code, and until now it was opt-in: a store read checked ownership only when the caller passed a `user_id`. With external accounts now signing up, "opt-in" is not an acceptable default.

## Decision

1. **One rule, one place.** Every route that selects tenant data by id resolves the id through `AccessContext` (`src/api/access.py`). The rule:
   * the owner of a project may reach it;
   * the `system` principal (materializer, backfill) may reach any existing project;
   * a project with no recorded owner is reachable only by the anonymous development principal, which exists only outside production and only with the in-memory store;
   * nothing else is granted.
2. **Hidden is not found.** A project the caller may not reach answers exactly like one that does not exist: `404` with the same body. `403` is reserved for resources that are visible but whose action is forbidden (org roles; the job-channel codes of ADR-0013).
3. **Ids in request bodies are authorized before any read or cache lookup.** One hidden id makes the whole request a 404. An optional id that is given but hidden is a 404 and is never silently ignored.
4. **Sharing is not honoured yet.** `project_shares`, `program_shares` and org membership grant nothing until their write side is hardened. Honouring reads first would turn an unchecked share write into one-call exfiltration.
5. **Result stores are owned.** Stored analysis results (risk, EVM, TIA, timelines, reports) record their owner and use unguessable ids.
6. **API keys act as their owner.** A key never reaches more than its owner could.

### Scope and actors, stated so they are not assumed

* **By-id access is where the rule lives today.** Store *list* methods still apply their older filter: on the in-memory store, an ownerless project appears in a user's list. They converge on this rule when the list routes migrate. Until then, "one rule" holds for reads by id, not yet for lists.
* **SuperAdmin grants nothing through this path.** Administrative reads, when they exist, use a separate and audited path.
* **The `system` principal** is obtained only through `AccessContext.system(store, reason=...)`, which logs the reason. The MCP server does not use it: it gets its own identity when it migrates.
* **Demo and sandbox flows** do not read ownerless projects in production. Measured on 2026-09-25: production holds no ownerless projects, programs or uploads.

## Consequences

* Routes migrate to the access context in slices. Until a route migrates, it keeps its previous behaviour.
* Tests exercise both directions for every migrated route: the owner reaches the resource (positive control), another tenant gets the not-found answer, and the answers for "hidden" and "missing" are identical.
* Background work must state that it acts as `system`. It cannot inherit an anonymous identity by omission.
