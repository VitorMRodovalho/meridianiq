<!-- Audit run: 2026-04-22 · Layer 2b -->
# Camada 2b — Schema (Supabase PostgreSQL)

## Inventário

25 migrations em `supabase/migrations/001..025`. Extração automática por migration:

| Migration | CREATE TABLE | ENABLE RLS | CREATE POLICY |
|---|---|---|---|
| 001_initial_schema | 19 | 0 | 0 |
| 002_auth_rls | 1 | 9 | 20 |
| 003_intelligence | 4 | 4 | 0 |
| 004_storage_refactor | 0 | 0 | 0 |
| 005_programs_table | 1 | 1 | 0 |
| 006_cleanup_orphan_uploads | 0 | 0 | 3 |
| 007_organizations | 5 | 5 | 8 |
| 008_value_milestones | 1 | 1 | 3 |
| 009_forensic_workspace | 1 | 1 | 2 |
| 010_sandbox | 0 | 0 | 1 |
| **012_api_keys** ⚠ | **1** | **1** | **3** |
| 013_benchmarks | 2 | 2 | 5 |
| 014_security_rpcs | 0 | 0 | 6 |
| 015_v3_persistence | 5 | 5 | 12 |
| 016_risk_register | 1 | 1 | 4 |
| **017_api_keys** ⚠ | **1** | **1** | **3** |
| 018_schedule_persistence | 3 | 14 | 42 |
| 019_erp_cost_tables | 8 | 8 | 26 |
| 020_projects_program_columns | 0 | 0 | 0 |
| 021_audit_trail_user_agent | 0 | 0 | 0 |
| 022_programs_unique_upsert | 0 | 0 | 0 |
| 023_schedule_derived_artifacts | 1 | 1 | 4 |
| 024_projects_status_state | 0 | 0 | 0 |
| 025_lifecycle_phase | 1 | 1 | 2 |

Observação: `011_rls_fixes.sql` (sem `CREATE TABLE`) backfilla 20 políticas cobrindo
`alerts`, `analysis_results`, `comparison_results`, `evm_analyses`, `float_snapshots`,
`forensic_timelines`, `health_scores`, `programs`, `reports`, `risk_simulations`,
`tia_analyses`. Isto é a **remediação** para as 19 tabelas criadas em 001 sem RLS.

## Migrations duplicadas `api_keys`

Já detalhado em [AUDIT-001 (Camada 1)](01-critical-findings.md#audit-001). Resumo:

| Aspecto | `012_api_keys.sql` | `017_api_keys.sql` |
|---|---|---|
| PK | `id UUID` | `id BIGINT GENERATED ALWAYS AS IDENTITY` |
| Unique chave externa | `key_prefix TEXT` | `key_id TEXT NOT NULL UNIQUE` |
| Invalidação | `is_active BOOLEAN` | `revoked_at TIMESTAMPTZ` |
| Expiração | `expires_at TIMESTAMPTZ` | — |
| Policy naming | `"Users see own keys"` | `api_keys_select` |

**Canônico = 017** (o código em `src/api/auth.py` só usa colunas de 017).

**Decisão técnica a tomar (escolha uma, documentar em ADR-0017 a seguir):**

1. **Reduzir 012 a no-op** (corpo vazio comentado) — preserva sequência numérica.
   Simples. Recomendado se nenhuma instalação em produção rodou 012 antes de 017.
2. **Criar 026 que faz `DROP TABLE IF EXISTS api_keys CASCADE` e re-aplica 017** —
   garante idempotência em qualquer ambiente. Recomendado se há dúvida sobre ordem.

Em ambos os casos, **ADR-0017** ("Deduplicate api_keys migration") deve ser aberto.

## RLS — estado geral

- **Todas as tabelas user-owned criadas em 002+ têm RLS habilitada**. Confirmado por
  busca: `grep "CREATE TABLE" supabase/migrations/ | cat` vs. `grep "ENABLE ROW LEVEL
  SECURITY"`.
- **As 19 tabelas de 001 foram cobertas por 002 + 011** (o trabalho de backfill).
- **Storage RLS** (`004_storage_refactor.sql`) — não cria tabelas, mas
  reorganiza o bucket `xer-files` com políticas mirror da ownership de `projects`.
  Verificação manual das políticas em Supabase Dashboard é recomendada (não há
  `CREATE POLICY` textual porque storage policies são aplicadas via função RPC).

**Pendência baixa-criticidade:** gerar um artefato `docs/audit/rls-matrix.md`
automaticamente — script que itera `supabase/migrations/*.sql` e imprime
`table_name · rls_enabled · policy_count · policy_names`. Facilita revisão de
segurança em CI.

## Indexação

Pontos críticos observados (via `grep -E "CREATE INDEX" supabase/migrations/*.sql`):

- `017_api_keys.sql`: `idx_api_keys_hash` e `idx_api_keys_user` — OK.
- `018_schedule_persistence.sql`: 42 policies + indexação explícita — bom.
- `023_schedule_derived_artifacts.sql`: `UNIQUE NULLS NOT DISTINCT` + indexes por
  `input_hash` — ADR-0014 aplicado.
- `015_v3_persistence.sql`: covering indexes não examinados item-a-item nesta rodada.

Sugestão de follow-up (P3): rodar `EXPLAIN ANALYZE` nos top-10 endpoints por latência
(via Sentry performance traces) e validar que há índice suportando cada `WHERE` crítico.

## FK e cascata

Por amostragem:

- `auth.users(id) ON DELETE CASCADE` aplicado em `api_keys`, `programs`, `projects`,
  `organizations`, `forensic_timelines`, `risk_register` — consistente.
- `projects(id) ON DELETE CASCADE` em `activities`, `wbs_elements`,
  `analysis_results`, `schedule_derived_artifacts` — consistente.

Não encontrei órfão explícito. O `006_cleanup_orphan_uploads.sql` já trata uma classe
histórica (BUG-009). Se fizer sentido, adicionar um CI check que roda
`SELECT count(*) FROM activities WHERE project_id NOT IN (SELECT id FROM projects)`
e falha > 0 — barato.

## Evolução do schema — ritmo

```
001–011 → bootstrap + RLS fixes (v0.x → v2.0)
012–017 → enterprise (api keys, benchmarks, RPCs, risk register)
018     → schedule persistence (grande: 14 RLS × 42 policies)
019     → ERP/CBS (migração de peso)
020–022 → housekeeping (columns, audit trail, uniqueness)
023–025 → Cycle 1 (derived artifacts, project state machine, lifecycle phase)
```

Ritmo saudável. Não há "mega-migration" monstro — cada uma é focada. Sugestão:
manter doc 1-linha por migration em `docs/schema-evolution.md` (não existe hoje)
para onboarding rápido de DBA/contribuidor.
