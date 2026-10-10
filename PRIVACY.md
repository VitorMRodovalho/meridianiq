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
- `user_profiles` — one row per account, created at sign-up from the
  identity provider: email address, full name, company, role, avatar URL.
  Supabase Auth keeps its own record of the account (`auth.users`: email
  address, provider identities, sign-in times).
- `organizations` / `memberships` — multi-tenant scaffolding.
- `forensic_access_log` — who viewed, exported, modified or shared a
  forensic timeline (`user_id`, organization, action, details, time).
- `programs` / `schedule_uploads` — grouping and revision history.
- `benchmarks`, `risk_register`, `erp_cost_tables`, etc. — feature-
  specific derivatives.

### 1.5 AI assistant (migrations 035, 036 and 040)

The AI assistant ("Ask Your Schedule") is off unless the operator enables
it, and then only for accounts the operator approves.

- `ai_entitlements` — which accounts may use it, their limits, who granted
  or revoked access, the account's email address as known at grant time
  (for the operator's display), and an optional free-text note by the
  operator about the account.
- `ai_usage` — one row per call: `user_id`, `project_id`, the model, the
  prices used, token counts and cost. It never stores the question or the
  answer. It has no foreign key, so it outlives the account's other data
  (spend accounting); the rows are pseudonymous.
- `ai_access_requests` — an account's request for access: status, the
  times, who decided, and an optional free-text **note** written by the
  user. The note is cleared when the request is approved or dismissed.
  A pending request is kept until it is decided; a decided request is
  deleted by a daily job once 30 days have passed since the decision
  (§3). The operator's decision itself stays in `audit_log` (§3).
- When a request is made, the operator is emailed that "an account asked
  for access", with no address, id or note (see §7), at most 10 emails per
  hour over all accounts (`AI_REQUEST_ALERTS_PER_HOUR`); requests above
  that are recorded and listed without an email.
- What is sent to the model provider on a call: a compact statistical
  summary of the schedule (counts, rounded metrics, the project's short
  name up to 120 characters) and the user's question as typed, which is
  free text and can hold anything the user writes. No activity names, no
  raw schedule.

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
  reference deployment runs in `iad` (Ashburn, Virginia, United States;
  measured with `fly status` on 2026-10-09). It holds no database and no
  files, but some analysis results (timelines, TIA, EVM, risk) live in
  the API process's memory until the machine restarts or the user erases
  their data, and the API's log lines pass through Fly.io's logging.
- **Frontend:** Cloudflare Pages CDN serves the static frontend. It
  stores no user data, and like any CDN it processes visitors' request
  metadata (such as the IP address) under its own terms.
- **Third-party inference (opt-in):** When the `NLP Query` feature is
  invoked, the analysis **summary** (never the raw schedule) is sent to
  Anthropic's Claude API. See `src/analytics/nlp_query.py`. If this is a
  compliance concern for a deployment, the feature can be disabled at
  the environment-variable level.
- **Error monitoring (opt-in):** When `SENTRY_DSN` is set, unhandled
  errors and a 10% sample of request timings are sent to Sentry. The
  reference deployment uses Sentry's EU data region (Frankfurt,
  Germany). A report holds the stack trace without local variables,
  the request's method and path (paths can contain project or
  organization IDs), the release and environment, and recent log lines.
  The exception's message and any log record at ERROR level are sent as
  written, so they can contain an identifier or a value the code put in
  them. The path of a file in Storage (`{user_id}/{upload_id}/{project
  name}.xer`) is replaced by `{path}` anywhere in a report.
  It holds no query string (neither the request's nor those of the
  API's own calls to its database), request headers, cookies or request
  body, so no credentials and no client IP address (`send_default_pii=False`,
  and `src/api/sentry_scrub.py` removes every header, including
  `Fly-Client-IP`, which the SDK's own filter does not cover). On the AI
  routes the log lines are dropped and IDs in the path are masked. See
  `src/api/app.py`.
- **Product analytics (off in the reference deployment):** the frontend
  loads PostHog only when it is built with `VITE_POSTHOG_KEY`
  (`web/src/lib/analytics.ts`). The reference deployment is built
  without it (measured 2026-10-09: no PostHog script, request or browser
  storage). When it is set, PostHog receives page views, page leaves and
  a client error event, keeps an identifier in the browser's
  `localStorage`, and sends to `VITE_POSTHOG_HOST` (default
  `us.i.posthog.com`, United States).

---

## 3. Retention

MeridianIQ implements one automatic deletion: a daily database job
(pg_cron, migration 040) removes AI access requests that were approved or
dismissed more than 30 days earlier. Runs are skipped while the database
is paused, so a request goes on the first run after its 30 days. The
job's run history (`cron.job_run_details`, kept 7 days) records only the
job, its command text and a status, no personal data. Copies in database
backups expire with the provider's backup retention.

Everything else persists until deleted. Default behaviour:

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
- **The uploaded XER binary in the `xer-files` Storage bucket is removed
  only by the erasure in §4.1.** Rows deleted any other way leave the file
  in the bucket, where only an operator with `service_role` can remove it
  (§4.2); a failed persist keeps it on purpose, as the source for a retry
  (ADR-0015).

`audit_log` rows **do not** cascade — they persist after the entity is
deleted, referencing it by `entity_id` string. This is intentional for
forensic integrity. Operators who need the audit trail to disappear
alongside the entity must remove the rows explicitly.

When the account itself is deleted (§4.2), `audit_log.user_id` and
`forensic_access_log.user_id` become NULL and the rows stay, as do the
organizations the account created and the shares, invitations and
milestones it recorded (their actor column becomes NULL); the account's
programs and reports are deleted with it (migration 038). Only the actor
column is cleared: an audit row about the account (`entity_id`) or its
`details` can still hold the account's id. An organization whose only
owner was the deleted account stays, with no one able to manage it.
Deleting an account whose projects still exist is refused (they point at
its programs), so the erasure in §4.1 comes first. Before migration 038
these references made Postgres refuse to delete any account at all.

### 4.1 User-initiated erasure

There is no endpoint to delete a single project. `DELETE
/api/v1/user/data` deletes the user's rows (uploads, projects and the
cascade above, analyses, comparisons, timelines, TIA, EVM, risk
simulations, contributed benchmarks, programs, API keys and the
profile; see the `delete_user_data` function in migration 014), and
clears the user-linked actor identity from derivative rows (via `ON
DELETE SET NULL` on `schedule_derived_artifacts.computed_by`, migration
023). It first removes the user's uploaded files from Storage: every
object in the user's folder at any depth, including one whose row is
already gone, and it reports how many were removed (`deleted_files`). If
a file is still listed afterwards it stops there, reports `partial` and
leaves the rows, so calling it again resumes.

`DELETE /api/v1/user/data` also erases the AI access request's note,
withdraws a pending request (it becomes dismissed, so the operator no
longer sees it), and clears the address and the operator's note on the
AI entitlement. The request row itself is kept, with its status, times
and who decided (no free text), until the block ends: it is what blocks a
new request for 30 days after a dismissal or a withdrawal, and without it
an account could erase and ask again at will, emailing the operator each
time (legitimate interest in preventing abuse, LGPD Art. 7 IX / GDPR
Art. 6(1)(f)). The daily job then deletes it (§3); deleting the account
removes it at once. You may object to this block (LGPD Art. 18 §2, GDPR
Art. 21) by contacting the operator of the deployment you use, who weighs
the objection against the abuse it prevents and can remove the record by
hand (§4.2). Access itself and the pseudonymous `ai_usage`
rows remain (§1.5). If the AI part of the erasure fails, the response
says `partial` instead of `complete`. Copies in database backups expire
with the provider's backup retention.

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
  table. Policies check `projects.user_id = auth.uid()`. Migration 011
  created two INSERT policies with `WITH CHECK (TRUE)`, on `alerts` and
  `health_scores`; client roles held no INSERT privilege on either table
  (measured 2026-10-09), and migration 037 drops both. The
  `schedule_derived_artifacts`
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
  `audit_log.user_id` retains the original UUID until the account is
  deleted, which sets it to NULL (migration 038), or a separate
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
| Backend compute | Fly.io | iad (Ashburn, Virginia, US; configurable) |
| Frontend CDN | Cloudflare Pages | global edge |
| Optional NLP | Anthropic | US (Claude API) |
| Operator email alerts (new account, AI access request) | Resend | per the operator's Resend account |
| Error monitoring (opt-in, `SENTRY_DSN`) | Sentry | EU (Frankfurt) |
| Product analytics (opt-in, `VITE_POSTHOG_KEY`; not enabled) | PostHog | US by default |

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

*Last reviewed: 2026-10-09, for the backend region, Storage erasure
(files removed by the user's erasure since this date),
error monitoring, RLS, product analytics and the data classes in §1.4.
The rest was last reviewed 2026-04-18 (MeridianIQ v4.0 Cycle 1 Wave 1,
alongside migration 023; see ADR-0009, ADR-0014).*
