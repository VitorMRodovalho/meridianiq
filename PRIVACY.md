# Data Handling — Non-binding Factual Disclosure

> **This is not a privacy policy.** This document is a factual technical
> disclosure of how the MeridianIQ open-source project stores, processes, and
> discards data at the time of its writing (2026-04-18, alongside migration
> 023). It is provided for transparency and to help operators of a MeridianIQ
> deployment reason about their own compliance obligations. It is **not**
> legal advice, does **not** constitute terms of service, and does **not**
> bind the project maintainer to any specific handling of your data.
>
> **Operators who self-host MeridianIQ are responsible for their own privacy
> policy, data-processing agreements, and compliance posture (LGPD, GDPR,
> HIPAA, or otherwise). For binding questions consult licensed counsel in
> your jurisdiction.**

This document is intentionally scoped to what the code does. It will be kept
in sync with the schema via the release process: every migration that changes
a user-facing data surface must update this file or explicitly note that no
update is needed.

**This file is not served to end-users of any deployment.** It describes the
behaviour of the open-source code, not a commitment to any end user.
Operators who run MeridianIQ for third parties must publish their own
user-facing privacy policy separately — nothing in this file substitutes for
that.

---

## 1. What MeridianIQ stores

Deployments that use the Supabase backend (`ENVIRONMENT=production`) persist
three classes of data:

### 1.1 Primary input — XER / MSP schedule files

- **Location:** Supabase Storage bucket `xer-files`.
- **Content:** the binary file the user uploaded. For Oracle Primavera P6,
  this is typically a tab-separated text dump of the project database
  (activities, WBS, calendars, relationships, cost/resource assignments,
  baselines). For Microsoft Project, an XML export. The file is retained
  as-is; MeridianIQ does not redact or modify its contents.
- **Sensitivity:** XER files commonly contain **project names, customer
  names, resource names, cost rates, and activity descriptions**. These
  fields can include personally identifiable information (PII), commercial
  pricing, and contractual milestones. Operators should treat the bucket
  contents as **confidential** and configure bucket-level ACLs accordingly.

### 1.2 Structured derivatives — PostgreSQL tables

The parser extracts the XER into ~20 relational tables (`projects`,
`activities`, `predecessors`, `calendars`, `resources`,
`resource_assignments`, `wbs_elements`, `activity_codes`,
`task_activity_codes`, `financial_periods`, `task_financials`, plus UDFs
and activity codes). These mirror the source file field-for-field in a
queryable form.

### 1.3 Materialized analysis results — `schedule_derived_artifacts`

Starting with migration 023 (Cycle 1 v4.0, Wave 1 — see ADR-0009 and
ADR-0014), analysis engines produce durable output rows in
`schedule_derived_artifacts` rather than recomputing on every request.

Each row contains:

- The analysis `payload` as JSON (e.g., a DCMA 14-Point result, a float
  trends series, a CPM critical-path listing) — derived from the source
  schedule, **not** a verbatim copy of it.
- **Provenance**: `engine_version`, `ruleset_version`, `input_hash`
  (sha256 of the project-scoped canonical JSON of the parsed schedule —
  see ADR-0014 for the exact algorithm), `effective_at` (the data_date
  the analysis speaks to), `computed_at` (wall-clock materialization
  time), and `computed_by` (the `auth.users(id)` of the user who
  triggered the materialization, or `NULL` for system-triggered
  backfills).
- `is_stale` / `stale_reason` — staleness flags set when the underlying
  input changes or a newer engine/ruleset supersedes the row.

The `payload` is derivative and reversible only with the original XER in
hand; it is not a substitute for the source file.

### 1.4 Supporting tables (not user content)

- `audit_log` — one row per sensitive action, capturing `user_id`,
  `action`, `entity_type`, `entity_id`, request `ip_address`,
  `user_agent`, and action-specific `details` JSON. Added to support
  forensic traceability per the SCL Protocol 2nd ed §4 expectations of
  construction-claims-grade recordkeeping.
- `organizations` / `organization_members` — multi-tenant scaffolding.
- `programs` / `schedule_uploads` — grouping and revision history.
- `benchmarks`, `risk_register`, `erp_cost_tables`, etc. — feature-
  specific derivatives.

---

## 2. Where the data lives

- **Primary database and Storage:** Supabase PostgreSQL project
  `tuswqzeytiobqfkxgkbe`, region **`us-west-2`** (AWS Oregon) at the time
  of writing. Operators who deploy their own instance control their own
  region selection. Operators who serve Brazilian data subjects must
  independently evaluate whether this region satisfies their LGPD Art. 33
  international-transfer basis (legal basis + transfer mechanism);
  operators serving EU data subjects must independently evaluate GDPR
  Chapter V transfer mechanisms (SCCs, adequacy decisions, etc.).
  MeridianIQ provides no transfer mechanism on any operator's behalf.
- **Backend compute:** Fly.io region of the operator's choosing. The
  reference deployment runs on `gru` (São Paulo). Stateless; no
  persistent data on Fly.io.
- **Frontend:** Cloudflare Pages CDN. Static assets only; no data at
  rest.
- **Third-party inference (opt-in):** When the `NLP Query` feature is
  invoked, the analysis **summary** (never the raw schedule) is sent to
  Anthropic's Claude API. See `src/analytics/nlp_query.py`. If this is a
  compliance concern for a deployment, the feature can be disabled at
  the environment-variable level.

---

## 3. Retention

MeridianIQ does not implement automatic deletion. Default behaviour:

- Uploaded XER/MSP files and their derivatives persist **until the
  uploading user or an organization admin triggers a delete**.
- `audit_log` rows are retained indefinitely by design — they exist to
  provide a forensic trail after the underlying entity is deleted.
  Operators who need time-bound audit retention must implement their own
  lifecycle rule on that table.
- `schedule_derived_artifacts` rows cascade with their parent project
  (see §4); no independent retention policy.

---

## 4. Deletion and right-to-erasure

The `projects` row is the anchor for all schedule-related data. Deleting
it removes the entire graph of dependent rows via `ON DELETE CASCADE`:

- All 13 persist-chain child tables (`activities`, `predecessors`,
  `calendars`, etc.) cascade per migration 018 and the ADR-0012
  compensating-delete contract.
- `schedule_derived_artifacts` cascades per migration 023 and ADR-0014,
  enforced by the `test_post_persist_tables_declare_on_delete_cascade`
  CI guard in `tests/test_schema_fk_cascade.py`.
- The uploaded XER binary in the `xer-files` Storage bucket is removed
  by `SupabaseStore._persist_schedule_data`'s compensating cleanup (see
  ADR-0012 amendment #1). A best-effort attempt is also made on user-
  initiated delete (see `src/database/store.py`).

`audit_log` rows **do not** cascade — they persist after the entity is
deleted, referencing it by `entity_id` string. This is intentional for
forensic integrity. Operators who need the audit trail to disappear
alongside the entity must remove the rows explicitly.

### 4.1 User-initiated erasure

A MeridianIQ user can delete their own projects through the API; this
triggers the cascade above. The project-level delete removes the
schedule graph and (via `ON DELETE SET NULL` on
`schedule_derived_artifacts.computed_by` added in migration 023) clears
the user-linked actor identity from derivative rows.

### 4.2 Operator-initiated erasure

An operator with Supabase `service_role` credentials can delete any row
or bucket object, bypassing RLS. This is the current path for
administrative erasure requests (account-wide deletion, LGPD Art. 18 IV,
GDPR Art. 17). Operators should log these actions separately from the
MeridianIQ `audit_log` for their own compliance purposes.

### 4.3 Audit trail lifecycle

The `audit_log` table is designed to outlive the entities it references.
This is defensible under a legitimate-interest framework — LGPD Art. 7
IX / Art. 10 (legítimo interesse) and GDPR Art. 6(1)(f) — when the
interest is forensic recordkeeping per SCL Protocol 2nd ed §4
(construction-claims-grade traceability). Operators whose jurisdiction
requires a time-bound audit retention must implement a lifecycle rule
on this table themselves; MeridianIQ ships none by default. The balancing
test between legitimate interest and subject rights is the operator's
responsibility and should be documented by the operator independently.

---

## 5. Access controls

- **Row Level Security (RLS)** is enabled on every schedule-related
  table. Policies check `projects.user_id = auth.uid()`. No
  `WITH CHECK (TRUE)` escapes exist; the `schedule_derived_artifacts`
  RLS quadruple (SELECT / INSERT / UPDATE / DELETE) mirrors the
  migration-018 pattern, extended by migration 023 with an UPDATE policy
  to eliminate a silent-no-op class under the `authenticated` role (see
  ADR-0014).
- **Authentication** is delegated to Supabase Auth (OAuth: Google,
  LinkedIn, Microsoft). JWTs are ES256-signed; verification uses JWKS
  (see `src/api/auth.py`).
- **Backend-to-DB access** uses the Supabase `service_role` key, which
  bypasses RLS. The key lives in the Fly.io secret store and is never
  exposed to the frontend.
- **`schedule_derived_artifacts.computed_by`** stores the Supabase UUID
  of the materializing user. Under both LGPD and GDPR a UUID that
  resolves to a natural person inside the same database qualifies as
  personal data (GDPR Recital 26 on pseudonymisation). The column uses
  `ON DELETE SET NULL` so user erasure propagates cleanly; the paired
  `audit_log.user_id` retains the original UUID until a separate
  retention rule clears it.

---

## 6. Audit trail

Every call that materializes a derived artifact writes a row to
`audit_log` with `action='materialize'`, capturing `user_id`, `entity_id`
(the project), `ip_address`, `user_agent`, and the artifact's provenance
in `details`. This composes with the `computed_by` column on the
artifact row itself for redundant-by-design chain-of-custody per SCL
Protocol 2nd ed §4.

Uploads, deletions, and organization-membership changes are also
audited. See `src/api/organizations.py::_audit` and related call sites.

---

## 7. Third parties and sub-processors — reference deployment only

The table below describes the infrastructure used by **the project
maintainer's reference deployment**. It is NOT prescriptive — an
operator who forks and self-hosts chooses their own providers and
regions, and MUST rewrite this section for their own deployment before
presenting it to any data subject.

| Role | Provider (reference) | Region (reference) |
|---|---|---|
| Auth, DB, Storage | Supabase | us-west-2 |
| Backend compute | Fly.io | gru (São Paulo, configurable) |
| Frontend CDN | Cloudflare Pages | global edge |
| Optional NLP | Anthropic | US (Claude API) |

Each of these providers has their own privacy policy; operators who
adopt MeridianIQ should review them against their jurisdiction's
requirements before deploying for a sensitive use case. Operators who
deploy in a region different from the reference inherit NONE of the
above — the schema and access-control behaviour is the same; the
jurisdiction is not.

---

## 8. Security issues

If you believe you have found a security-sensitive defect, please do
**not** open a public GitHub issue. Email the project maintainer
directly (see the repository README for contact). Coordinated
disclosure preferred.

---

## 9. Scope of this disclosure

This document describes the **code as of commit date 2026-04-18**, in
particular migration 023 (`schedule_derived_artifacts`) and the
forensic-provenance contract from ADR-0014. Subsequent changes that
affect data handling will update this file before merging.

This document does **not**:

- Constitute a contract or a promise of any specific handling.
- Bind any operator to the described behaviour.
- Replace the operator's own privacy policy, ToS, or DPA.
- Address jurisdiction-specific requirements (LGPD Art. 18 subject
  rights, GDPR Art. 17 right to erasure, HIPAA, SOC 2, ISO 27001, etc.).

**For binding legal questions, consult licensed counsel in your
jurisdiction.**

---

*Last reviewed: 2026-04-18 — MeridianIQ v4.0 Cycle 1 Wave 1, alongside
migration 023 (see ADR-0009, ADR-0014).*
