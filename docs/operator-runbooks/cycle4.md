<!-- Authored 2026-05-07 (Cycle 4 W2 PR-A) — operator-paced runbooks for W1 + W2-A revision lifecycle incidents -->
# Cycle 4 — Operator Runbooks (W2 revision lifecycle)

This document collects the **operator-paced** items relevant to the
[ADR-0022 §"Wave plan W2"](../adr/0022-cycle-4-entry-beta-honest.md) revision
lifecycle deliverables. Cycle 4 W1 ops items are tracked in
[`cycle3.md`](cycle3.md) (#26 / #28 / #54) where they were originally scoped;
the per-cycle directory split here is **incident-focused**, not
phase-of-cycle-focused.

| # | Title | Trigger | Estimated time | Difficulty | Section |
|---|---|---|---|---|---|
| W2-INC-01 | Revision mis-grouping (operator confirmed wrong parent) | After-the-fact discovery via support ticket / data review | 5-15 min | Operations + judgement | [§W2-INC-01](#w2-inc-01--revision-mis-grouping-incident) |
| W2-INC-02 | Bulk tombstone (multiple revisions in same program) | Schema migration / data-migration error producing many wrong rows | 15-30 min | Ops + manual SQL | [§W2-INC-02](#w2-inc-02--bulk-tombstone-multiple-revisions) |
| W2-INC-03 | Un-tombstone within 24h grace window | Operator realized tombstone was wrong call | 10-20 min | Ops + audit_log review | [§W2-INC-03](#w2-inc-03--un-tombstone-within-24h-grace-window) |

**Standing protocol:** each incident response ends with a §"Registry" step. Comment the action on a tracking issue (or open one if the incident is novel) and append a one-line entry to the audit log if the action wasn't auto-paired by the API.

---

## W2-INC-01 — Revision mis-grouping incident

**Trigger:** A user (or you, or a support ticket) reports "I confirmed
this XER as a revision of project X, but it should have been treated as
a brand-new project (or a revision of project Y instead)". Per ADR-0022
HB-C contract the fix is **soft-tombstone with audit trail**, NOT
hard-delete.

**ADR:** [ADR-0022 §"Soft-tombstone deliverables"](../adr/0022-cycle-4-entry-beta-honest.md)

### Pre-flight diagnosis

Identify the offending row(s):

```sql
-- Find recent revision_history rows for a user (replace UUID)
SELECT
    rh.id           AS revision_id,
    rh.project_id,
    p.project_name,
    rh.revision_number,
    rh.data_date,
    rh.content_hash,
    rh.tombstoned_at,
    rh.tombstoned_reason,
    rh.created_at
FROM revision_history rh
JOIN projects p ON p.id = rh.project_id
WHERE p.user_id = '<USER_UUID>'
  AND rh.tombstoned_at IS NULL
ORDER BY rh.created_at DESC
LIMIT 50;
```

Confirm the row to tombstone is the right one. **Cross-check the
`content_hash`** against the user's expected XER bytes — if the hash
matches a different physical schedule than the one labelled, the
tombstone is correct AND a separate root-cause investigation is needed
(detect heuristic v1 false-positive? client-side mis-click?).

### Tombstone procedure (preferred — via API)

```bash
# 1. Get a SuperAdmin JWT (browser DevTools → localStorage)
JWT="..."  # paste locally — DO NOT share

REVISION_ID="<UUID>"
REASON="explanation of why this row is wrong (≤500 chars)"

# 2. Call the API
curl -X POST "https://meridianiq-api.fly.dev/api/v1/revisions/$REVISION_ID/tombstone" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg r "$REASON" '{reason:$r}')"

# 3. Verify the response
# Expected: 200 with {revision_id, tombstoned_at, audit_log_id}
```

The endpoint writes:

1. ``UPDATE revision_history SET tombstoned_at = now(), tombstoned_reason = ?``
2. ``INSERT audit_log {action='revision_tombstoned', entity_type='revision_history',
    entity_id=revision_id, details={reason, original_baseline_lock_at}}``

The pair is best-effort (audit may fail-after-update) — see
``src/database/store.py:tombstone_revision`` docstring for the contract.

### Tombstone procedure (fallback — direct SQL)

When the API path is unavailable (Fly down, JWT expired during incident,
etc.) — apply via SQL Editor at
`https://supabase.com/dashboard/project/tuswqzeytiobqfkxgkbe/sql/new`:

```sql
BEGIN;

-- 1. Capture pre-state for audit details (read tombstoned_at to detect
--    already-tombstoned and reject double-tombstone)
SELECT id, tombstoned_at, baseline_lock_at
  FROM revision_history
 WHERE id = '<REVISION_UUID>';
-- If tombstoned_at IS NOT NULL: STOP. Already tombstoned. Don't double-up.

-- 2. Tombstone
UPDATE revision_history
   SET tombstoned_at = now(),
       tombstoned_reason = '<REASON>'
 WHERE id = '<REVISION_UUID>'
   AND tombstoned_at IS NULL;
-- Expected: 1 row affected.

-- 3. Paired audit_log row
INSERT INTO audit_log (
    user_id, action, entity_type, entity_id, details, ip_address, user_agent
) VALUES (
    '<OPERATOR_USER_UUID>',
    'revision_tombstoned',
    'revision_history',
    '<REVISION_UUID>',
    jsonb_build_object(
        'reason', '<REASON>',
        'original_baseline_lock_at', NULL,  -- fill from step 1's result
        'manual_sql', true
    ),
    NULL,
    'sql-editor-manual'
);

-- 4. Verify
SELECT tombstoned_at, tombstoned_reason
  FROM revision_history
 WHERE id = '<REVISION_UUID>';

COMMIT;
```

### Verification

```sql
-- Confirm tombstone visible in revision_history
SELECT tombstoned_at, tombstoned_reason
  FROM revision_history
 WHERE id = '<REVISION_UUID>';
-- Expected: tombstoned_at NOT NULL, tombstoned_reason matches.

-- Confirm audit_log paired write
SELECT id, action, entity_id, details, created_at
  FROM audit_log
 WHERE entity_id = '<REVISION_UUID>'
   AND action = 'revision_tombstoned'
 ORDER BY created_at DESC LIMIT 1;
-- Expected: 1 row, recent timestamp, details contains reason + original_baseline_lock_at.

-- Confirm RLS-default reads now hide this row
SELECT count(*) FROM revision_history WHERE id = '<REVISION_UUID>';
-- Under authenticated role: 0 (RLS SELECT policy filters tombstoned_at IS NULL).
-- Under postgres role: 1 (service-role bypass).
```

### Rollback

See [§W2-INC-03](#w2-inc-03--un-tombstone-within-24h-grace-window) for the
un-tombstone procedure. Available within 24h grace window.

### Registry

1. Comment on the originating issue (or open one if novel) with the
   revision_id + audit_log_id.
2. If multiple incidents in a week, file a meta-issue and consider
   tightening the detect heuristic confidence threshold (currently 0.9
   on exact name match; v1 may be over-suggesting).

---

## W2-INC-02 — Bulk tombstone (multiple revisions)

**Trigger:** Data migration error or detect heuristic regression
produced many wrong revision_history rows.

**Pre-condition:** Identify ALL the bad rows in a single SELECT before
mutating. Bulk operations multiply blast radius.

### Procedure

```sql
BEGIN;

-- 1. Capture the affected rows (BEFORE state for audit)
CREATE TEMP TABLE _bulk_tombstone_targets AS
SELECT id, project_id, baseline_lock_at
  FROM revision_history
 WHERE <PREDICATE>  -- e.g., created_at BETWEEN '2026-05-07 12:00' AND '2026-05-07 14:00'
   AND tombstoned_at IS NULL;

-- Sanity-check the count
SELECT count(*) FROM _bulk_tombstone_targets;
-- Expected: matches your intent. If not, ROLLBACK and refine PREDICATE.

-- 2. Tombstone all of them
UPDATE revision_history
   SET tombstoned_at = clock_timestamp(),  -- per-row distinct timestamps
       tombstoned_reason = '<BATCH_REASON>'
 WHERE id IN (SELECT id FROM _bulk_tombstone_targets);

-- ⚠ NOTE: clock_timestamp() vs now()
-- now() returns the cached transaction start time — all UPDATEd rows
-- would share the same timestamp. clock_timestamp() returns wall-clock
-- per row, preserving the UNIQUE NULLS NOT DISTINCT contract from
-- migration 028 IF you ever need to insert TWO same-revision-number
-- rows after this batch (very unusual but per migration prose).

-- 3. Paired audit_log entries (one per tombstone)
INSERT INTO audit_log (
    user_id, action, entity_type, entity_id, details, user_agent
)
SELECT
    '<OPERATOR_USER_UUID>',
    'revision_tombstoned',
    'revision_history',
    t.id,
    jsonb_build_object(
        'reason', '<BATCH_REASON>',
        'original_baseline_lock_at', t.baseline_lock_at,
        'bulk', true,
        'batch_size', (SELECT count(*) FROM _bulk_tombstone_targets)
    ),
    'sql-editor-bulk'
FROM _bulk_tombstone_targets t;

-- 4. Verify counts match
SELECT
    (SELECT count(*) FROM revision_history WHERE tombstoned_at IS NOT NULL
        AND tombstoned_reason = '<BATCH_REASON>') AS tombstoned,
    (SELECT count(*) FROM audit_log WHERE action = 'revision_tombstoned'
        AND details->>'reason' = '<BATCH_REASON>') AS audited;
-- Expected: equal counts. If not, ROLLBACK and investigate.

DROP TABLE _bulk_tombstone_targets;
COMMIT;
```

### Registry

File a P1 issue with the BATCH_REASON, root cause, count of affected
rows, and reference to the audit_log entries.

---

## W2-INC-03 — Un-tombstone within 24h grace window

**Trigger:** Operator (or user via support ticket) realized the tombstone
in [§W2-INC-01](#w2-inc-01--revision-mis-grouping-incident) was wrong.

**Pre-condition:** Within 24h of the original tombstone. Beyond 24h,
un-tombstoning may break downstream invariants if any UI / report
already presented "this revision is gone" to a user.

### Procedure

```sql
BEGIN;

-- 1. Verify the row IS still tombstoned (idempotent — double un-tombstone is no-op)
SELECT id, tombstoned_at, tombstoned_reason, baseline_lock_at
  FROM revision_history
 WHERE id = '<REVISION_UUID>'
   AND tombstoned_at IS NOT NULL;
-- Expected: 1 row. If 0, the row is already active (no-op).

-- 2. Verify the tombstone is within the 24h grace window
SELECT
    EXTRACT(EPOCH FROM (now() - tombstoned_at)) / 3600 AS hours_since_tombstone
  FROM revision_history
 WHERE id = '<REVISION_UUID>';
-- Expected: < 24. If > 24, STOP and consider whether un-tombstoning is
-- the right call vs creating a new revision_history row at the next
-- revision_number (a "redo" rather than an "undo").

-- 3. Un-tombstone — append-only trigger PERMITS this (it allows mutation
--    of tombstoned_at + tombstoned_reason in either direction)
UPDATE revision_history
   SET tombstoned_at = NULL,
       tombstoned_reason = NULL
 WHERE id = '<REVISION_UUID>';

-- 4. Paired audit_log entry — DIFFERENT action (forensic trail must
--    show the un-tombstone as its own event, not a magical un-do of
--    the original tombstone)
INSERT INTO audit_log (
    user_id, action, entity_type, entity_id, details, user_agent
) VALUES (
    '<OPERATOR_USER_UUID>',
    'revision_untombstoned',
    'revision_history',
    '<REVISION_UUID>',
    jsonb_build_object(
        'reason', '<UNTOMBSTONE_REASON>',
        'within_grace_window', true,
        'manual_sql', true
    ),
    NULL,
    'sql-editor-manual'
);

-- 5. Verify
SELECT tombstoned_at, tombstoned_reason FROM revision_history
 WHERE id = '<REVISION_UUID>';
-- Expected: both NULL.

COMMIT;
```

### Registry

Comment on the original W2-INC-01 incident issue with the un-tombstone
audit_log id + reason. If un-tombstones happen ≥3× in a month, that's a
signal to revisit the detect heuristic threshold or the confirmation UX
copy.

---

## Standing observability

After any of the W2-INC procedures, probe runtime:

```bash
curl -H "Authorization: Bearer $JWT" \
  https://meridianiq-api.fly.dev/api/v1/superadmin/runtime
```

Look at `active_ws_channels` and `rate_limit_buckets` — sudden jumps
during incident response are signals to dig deeper. See [§project_oom_baseline_2026_05.md](../../) (Claude memory) for the baseline curve.

## Cross-references

- [ADR-0022](../adr/0022-cycle-4-entry-beta-honest.md) §"Soft-tombstone deliverables" + Amendment 1
- [Migration 028](../../supabase/migrations/028_revision_history.sql) §"Append-only mutation guard"
- `tests/test_revision_history_tombstone_filter.py` — AST regression for SELECT-path tombstone filter
- `cycle3.md` — Cycle 3 operator items (#26 / #28 / #54) — separate incidents
