# 0017. Deduplicate the `api_keys` migration (012 vs 017)

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-22
* Triggered by: 2026-04-22 structural audit — [AUDIT-001 (P0)](../audit/01-critical-findings.md#audit-001--p0--migrations-012_api_keyssql-e-017_api_keyssql-definem-schemas-divergentes-da-mesma-tabela)

## Context and Problem Statement

Two migrations in `supabase/migrations/` define the `api_keys` table with divergent
schemas:

| Aspect | `012_api_keys.sql` | `017_api_keys.sql` |
|---|---|---|
| PK | `id UUID` | `id BIGINT GENERATED ALWAYS AS IDENTITY` |
| Lookup identifier | `key_prefix TEXT` | `key_id TEXT NOT NULL UNIQUE` |
| Invalidation | `is_active BOOLEAN` | `revoked_at TIMESTAMPTZ` |
| Expiration | `expires_at TIMESTAMPTZ` | — |
| Policies | `"Users see own keys"` (quoted) | `api_keys_select`, `api_keys_insert`, `api_keys_delete` |

Runtime code in `src/api/auth.py` — `generate_api_key`, `validate_api_key`,
`list_api_keys`, `revoke_api_key` — references **only** the 017 columns
(`key_id`, `key_hash`, `user_id`, `name`, `created_at`). The 012 columns
(`key_prefix`, `is_active`, `expires_at`) are never used.

Both migrations use `CREATE TABLE IF NOT EXISTS`. On any fresh Supabase instance
that applies migrations in lexical order, 012 wins — creating a table whose
columns do not match the runtime code. 017 then no-ops the `CREATE`, adds
policies that happen to work (they only reference `user_id`), and leaves the
application in a broken state until a manual `ALTER TABLE` adds `key_id`.

This is a correctness hazard, not just a style issue.

## Decision Drivers

- **Fresh installs must work without manual SQL.** Any contributor cloning the
  repo and pointing it at a new Supabase project should land with a working
  schema.
- **Existing production environments must not be disrupted.** If a production
  database currently holds 012's schema plus any manually added `key_id`
  column, dropping the table would destroy live API keys.
- **Migration numbering is append-only.** Rewriting an accepted migration
  breaks the `supabase db migration` audit trail on any instance that has
  already applied it.

## Considered Options

1. **Delete `012_api_keys.sql` outright.**
   - Simplest diff.
   - Breaks replay against instances where 012 was recorded in
     `supabase_migrations.schema_migrations`; Supabase will error on missing
     file.
   - Rejected.

2. **Rewrite `012_api_keys.sql` to match 017's schema.**
   - Would require rewriting accepted, applied history. Violates ADR-0000
     "ADRs are immutable once accepted"; migrations deserve the same
     protection.
   - Rejected.

3. **Reduce `012_api_keys.sql` to a no-op header (comment only) + add migration
   `026_api_keys_schema_align.sql` that reconciles any 012-style live table to
   the 017 shape.**
   - 012 file stays present (history preserved) but does nothing on fresh
     installs.
   - 026 is idempotent: adds `key_id` if absent, backfills it deterministically,
     drops orphan columns with a safe guard. Works against fresh installs
     (where 017's schema is already canonical) AND against legacy instances
     that materialized 012's schema.
   - New fresh installs: 012 runs (no-op), 017 creates the 017 schema, 026
     runs (no-op because schema already matches).
   - Legacy installs where 012 was applied first: 012 replays (no-op),
     017 replays (CREATE skipped because table exists), 026 runs and aligns
     the live schema.
   - **Chosen.**

## Decision Outcome

Reduce `012_api_keys.sql` to a header comment explaining the supersession and
pointing at this ADR. Add `supabase/migrations/026_api_keys_schema_align.sql`
that:

1. Drops the legacy `"Users see own keys"`, `"Users insert own keys"`,
   `"Users update own keys"` policies **if** they exist (they were the 012
   variants; 017's `api_keys_select` / `api_keys_insert` / `api_keys_delete`
   are the canonical set going forward).
2. Adds `key_id TEXT` as nullable, backfills with `'legacy_' || id::text` for
   any existing rows, adds `UNIQUE (key_id)` and the `NOT NULL` constraint.
3. Adds `revoked_at TIMESTAMPTZ` as nullable; converts `is_active = FALSE`
   rows to `revoked_at = now()`; drops `is_active` and `key_prefix` and
   `expires_at` columns **if** they exist.

Each step guards on `information_schema.columns` so the migration is safe on
both fresh and legacy schemas.

Add regression test `tests/test_api_keys_schema.py` that:

- Asserts `CREATE TABLE api_keys` from a fresh migration sweep lands with
  the 017 column set.
- Executes a `INSERT … RETURNING key_id` round-trip using the exact dict
  that `src/api/auth.py::generate_api_key` sends.

## Consequences

**Positive**

- Fresh clones work without hand-edit of SQL.
- Legacy production instances reconciled on the next migration sweep.
- Runtime code in `src/api/auth.py` is the single source of truth for the
  schema contract.
- Append-only history preserved (012 file retained).

**Negative / accepted costs**

- Two extra migration files (012 shell + 026 align) instead of one clean
  definition. Trade-off for migration-history integrity.
- Legacy 012-style tables carry a `legacy_N` string in `key_id` for old rows
  until rotated; acceptable because 012 was never successfully exercised by
  production code (any key generated against 012's schema could not be
  validated by the 017-compatible `src/api/auth.py`).

## Related

- [AUDIT-001 (P0)](../audit/01-critical-findings.md#audit-001--p0--migrations-012_api_keyssql-e-017_api_keyssql-definem-schemas-divergentes-da-mesma-tabela)
- Issue [#16](https://github.com/VitorMRodovalho/meridianiq/issues/16)
- Runtime code: `src/api/auth.py` §"API Key Management"
