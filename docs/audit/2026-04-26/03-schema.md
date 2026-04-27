<!-- Audit run: 2026-04-26 · Layer 2b (Schema) -->
# Camada 2b — Schema (Migrations + RLS)

Cobertura RLS, FK/CASCADE, e o legado `api_keys` resolvido por ADR-0017.

## Inventário (em 2026-04-26)

26 arquivos `.sql` em `supabase/migrations/`:

```
001_initial_schema.sql           011_rls_fixes.sql                021_audit_trail_user_agent.sql
002_auth_rls.sql                 012_api_keys.sql ← no-op         022_programs_unique_upsert.sql
003_intelligence.sql             013_benchmarks.sql               023_schedule_derived_artifacts.sql
004_storage_refactor.sql         014_security_rpcs.sql            024_projects_status_state.sql
005_programs_table.sql           015_v3_persistence.sql           025_lifecycle_phase.sql
006_cleanup_orphan_uploads.sql   016_risk_register.sql            026_api_keys_schema_align.sql
007_organizations.sql            017_api_keys.sql ← canonical
008_value_milestones.sql         018_schedule_persistence.sql
009_forensic_workspace.sql       019_erp_cost_tables.sql
010_sandbox.sql                  020_projects_program_columns.sql
```

**Diff vs baseline (2026-04-22):** **+5 migrations adicionais** desde
v4.0.1 → v4.0.2 → v4.1.0:

- `022_programs_unique_upsert.sql` (Cycle 1 W0) — UNIQUE constraint em programs
- `023_schedule_derived_artifacts.sql` (Cycle 1 W1) — ADR-0014 / -0015 base
- `024_projects_status_state.sql` (Cycle 1 W2) — ADR-0015 state machine
- `025_lifecycle_phase.sql` (Cycle 1 W3) — ADR-0016
- `026_api_keys_schema_align.sql` (Cycle 2 W0 / audit B4) — ADR-0017

## Status do `api_keys` (carry-over de AUDIT-001 da baseline)

**Em código:** RESOLVIDO. `012_api_keys.sql` foi convertido em no-op com header explícito:

```
-- Migration 012: SUPERSEDED BY 017 + 026 (see ADR-0017).
```

A tabela autoritativa é definida em `017_api_keys.sql` (id BIGINT, key_id TEXT
UNIQUE, key_hash TEXT UNIQUE, user_id UUID, name TEXT, created_at, revoked_at,
last_used_at), com RLS + 3 policies (`api_keys_select`, `api_keys_insert`,
`api_keys_update`).

`026_api_keys_schema_align.sql` é idempotente: identifica via `pg_attribute` se
a instância tem schema legado de 012; se sim, faz backfill `key_id`, traduz
`is_active=FALSE → revoked_at=now()`, drop colunas legadas. Em instância nova,
no-op.

**Em produção:** AINDA PENDENTE — issue [#26](https://github.com/VitorMRodovalho/meridianiq/issues/26)
OPEN há 5 dias. Carry-over para [`HANDOFF.md §H-01-carryover`](HANDOFF.md#h-01-carryover).

## Cobertura RLS por migration nova

Verificado por grep `ENABLE ROW LEVEL SECURITY` + `CREATE POLICY`:

| Migration | RLS enable | Policies | Avaliação |
|---|---|---|---|
| 022_programs_unique_upsert | 0 | 0 | ✅ ALTER em programs (RLS herdada de 005). Migration adiciona UNIQUE constraint sem tocar segurança |
| 023_schedule_derived_artifacts | 1 | 4 | ✅ Quadruple RLS (SELECT/INSERT/UPDATE/DELETE) per ADR-0014 |
| 024_projects_status_state | 0 | 0 | ⚠ ALTER em projects (RLS herdada de 001/002). Verificado: ALTER TABLE não muda enabled_state — RLS continua ON. Sub-finding em AUDIT-2026-04-26-004 |
| 025_lifecycle_phase | 1 | 2 | ✅ `lifecycle_phase_locks` + `lifecycle_phase_overrides` |
| 026_api_keys_schema_align | 0 | 3 | ✅ ALTER em api_keys (RLS herdada de 017). 3 policies novas/realinhadas (`api_keys_select`, `api_keys_insert`, `api_keys_update`) |

---

## AUDIT-2026-04-26-004 · P3 · Migration 024 ALTER TABLE sem re-asserção explícita de RLS

**Arquivo:** `supabase/migrations/024_projects_status_state.sql`.

**Por que isto NÃO é bug:** Postgres ALTER TABLE preserva `enable row security`
flag — RLS continua ON. Migration 001 + 002 já habilitaram RLS em `projects`.

**Por que MERECE flag:** doc discipline. ADR-0014 §"Decision" estabelece que
"toda migration que toca tabela user-owned deve emitir RLS guard como exercício
de revisão" (paráfrase). 024 toca `projects` (user-owned) e não emite explicit
re-assertion. Migration 023 emite `ENABLE ROW LEVEL SECURITY` mesmo sendo CREATE
TABLE (defensive); migration 024 omite porque é ALTER + CHECK CONSTRAINT.

**Risco:** baixíssimo. **Conformidade:** ainda OK. **Discipline gap:** existe.

**Ação:** sem ação imediata. Considerar amendment a ADR-0014 ou ADR-0015
estabelecendo que "ALTER em user-owned table com checks novas requer re-assertion
explícita de RLS para visibilidade da policy". Caso contrário, deletar este
finding na próxima rodada.

---

## FK / CASCADE coverage

Verificado em [`023_schedule_derived_artifacts.sql`](../../../supabase/migrations/023_schedule_derived_artifacts.sql):

```sql
project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
artifact_kind TEXT NOT NULL CHECK (...)
UNIQUE NULLS NOT DISTINCT (project_id, artifact_kind, engine_version, ruleset_version, input_hash)
```

`ON DELETE CASCADE` é semanticamente correto — derived artifact não deve sobreviver
ao project pai. **MAS:** ADR-0014 §"Decision drivers" #5 nota que cascade
"propaga deleção silenciosamente" — futuro auto-grouping (Cycle 5+ A1+A2 deferido)
precisará de migration de mitigação (ex: tombstone column, soft-delete) antes de
mexer com merge-cascade. ADR-0021 §"Why NOT the PV deep" item #2 cita exatamente
este risco como bloqueador para A1+A2.

**Conformidade atual:** OK. **Future risk:** documentado em ADR-0021.

---

## Idempotência de migration 026

Verificado em [`026_api_keys_schema_align.sql`](../../../supabase/migrations/026_api_keys_schema_align.sql):

- Detecta schema legado via `pg_attribute` queries antes de mutar.
- Backfill em loop (`UPDATE api_keys SET key_id = 'legacy_' || id::text WHERE key_id IS NULL`).
- `DROP COLUMN IF EXISTS` em `key_prefix`, `is_active`, `expires_at`.
- Re-emit policies com `DROP POLICY IF EXISTS` antes de `CREATE POLICY`.

Em instância nova (apenas 017): no-op completo. Em instância antiga (apenas 012):
backfill. Em instância mista: indeterminado (deve detectar via pg_attribute).
Tests de regressão estática shippados em `tests/test_api_keys_schema.py` (8 testes).

---

## Gotchas conhecidos (continuam válidos)

- **Pooler porta 6543** — Supabase usa transaction pooler em 6543, não 5432
  direct connection. CLAUDE.md já documenta.
- **JWT ES256** — não HS256/RS256. JWKS auto-detecta.
- **WeasyPrint system deps** — libpango + libcairo no Dockerfile (v4.1.0
  Dockerfile inclui).

---

**Sumário desta camada:** 1 achado P3 (AUDIT-2026-04-26-004 — discipline gap em
024 ALTER), 5 migrations novas verificadas, FK/CASCADE coverage adequada,
idempotência 026 verificada estaticamente. **Schema saudável.** Carry-over operator
para #26 prod apply é o único item ainda em flight.
