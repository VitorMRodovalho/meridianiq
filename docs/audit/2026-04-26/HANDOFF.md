<!-- Audit handoff · generated 2026-04-26 · base commit ea4ee4d on main -->
# Audit 2026-04-26 — Handoff para o time dev

Esta rodada é dramaticamente menor que a baseline 2026-04-22 — **nenhuma
ação P0/P1 nova**. O backlog se divide em:

1. **Carry-over P0/P1/P2** ainda em flight desde 2026-04-22 (operator items).
2. **Achados P2/P3 novos** desta rodada (10 items, todos doc-drift / process /
   discipline gaps).

**Regra de ouro:** mantida do baseline — itens classificados `requires-human-decision`
exigem 2+ revisores antes de fechar.

---

## Índice

| # | Ação | Severidade | Owner sugerido | Issue / Source | Prazo alvo |
|---|---|---|---|---|---|
| **H-01-carryover** | Aplicar migration 026 em produção (Supabase) | **P0 ops** | Maintainer + DBA/ops | [`#26`](https://github.com/VitorMRodovalho/meridianiq/issues/26) (em flight desde 2026-04-22) | Imediata — janela de manutenção próxima |
| **H-02-carryover** | Ratificar ADRs 0017–0021 (5 ADRs, ampliado de 2) | **P2** | Maintainer / council review | [`#28`](https://github.com/VitorMRodovalho/meridianiq/issues/28) (atualizar body) | Antes de Cycle 3 W2 fechar |
| **H-03-new** | README mermaid + ASCII tree fix | P2 | Maintainer | AUDIT-2026-04-26-001 ([02-architecture.md](02-architecture.md#audit-2026-04-26-001)) | Próximo PR doc-only |
| **H-04-new** | Estender `check_stats_consistency.py` para cobrir mermaid + arch.md | P3 | Maintainer | AUDIT-2026-04-26-001 + 002 | Mesmo PR de H-03 |
| **H-05-new** | architecture.md + CLAUDE.md migration count + test count fix | P3 | Maintainer | AUDIT-2026-04-26-002 | Mesmo PR de H-03/H-04 |
| **H-06-new** | Devils-advocate-as-second-reviewer protocol — codify | P2 | Maintainer | AUDIT-2026-04-26-003 | Cycle 3 close OR Cycle 4 W0 |
| **H-07-new** | Migration 024 ALTER discipline gap — review | P3 | Maintainer | AUDIT-2026-04-26-004 ([03-schema.md](03-schema.md#audit-2026-04-26-004)) | Discretionary |
| **H-08-new** | Rate-limit policy contract — amendment a ADR | P3 | Maintainer | AUDIT-2026-04-26-005 ([04-security.md](04-security.md#audit-2026-04-26-005)) | Cycle 3 W4 ou Cycle 4 |
| **H-09-new** | `RATE_LIMIT_ENABLED` doc em `.env.example` | P3 | Maintainer | AUDIT-2026-04-26-006 | Mesmo PR de H-03/H-04/H-05 |
| **H-10-new** | `_ENGINE_VERSION` → `__about__.py` (já pre-committed Cycle 3 W4) | P3 | Maintainer | AUDIT-2026-04-26-007 | Cycle 3 W4 |
| **H-11-new** | Detail page i18n carry-over | P3 | Frontend eng | AUDIT-2026-04-26-008 ([05-ux-frontend.md](05-ux-frontend.md#audit-2026-04-26-008)) | Cycle 4 W5 ou Cycle 5 |
| **H-12-new** | Issue #28 body update + título extension | P3 | Maintainer | AUDIT-2026-04-26-009 | Junto com H-02-carryover |
| **H-13-new** | Meta-issue #25 exit policy clarification | P3 | Maintainer | AUDIT-2026-04-26-010 | Discretionary |

---

## H-01-carryover · Aplicar migration 026 em produção

**Status:** OPEN há 5 dias (2026-04-22 → 2026-04-26).

Per [baseline HANDOFF §H-01](../HANDOFF.md#h-01--aplicar-migration-026-em-produção)
— procedure complete. **Re-cita aqui para evitar drift por click-through:**

1. **Diagnóstico** (read-only, qualquer hora):
   ```sql
   \d api_keys
   SELECT column_name, data_type, is_nullable
     FROM information_schema.columns
    WHERE table_name = 'api_keys'
    ORDER BY ordinal_position;
   SELECT name, executed_at FROM supabase_migrations.schema_migrations
    WHERE name LIKE '%api_keys%' ORDER BY executed_at;
   ```

2. **Backup obrigatório:**
   ```sql
   CREATE TABLE api_keys_backup_20260426 AS SELECT * FROM api_keys;
   SELECT COUNT(*) FROM api_keys_backup_20260426;
   ```
   *(Note: data label atualizada de baseline 20260422 para 20260426 para que o backup
   reflita a janela atual de execução.)*

3. **Aplicar 026:** via supabase CLI ou SQL editor. Conteúdo idempotente.

4. **Verificação pós-apply:**
   ```sql
   \d api_keys                                        -- esperado: id BIGINT, key_id TEXT, key_hash TEXT, user_id UUID, name, created_at, revoked_at, last_used_at
   SELECT count(*) FROM api_keys;                     -- igual ao backup
   SELECT count(*) FROM api_keys WHERE key_id LIKE 'legacy_%';   -- rows backfilladas (se schema antigo)
   ```

5. **Smoke test runtime:** criar/validar/revogar uma API key via endpoints
   `POST /api/v1/api-keys`, `X-API-Key` header em `GET /api/v1/health` com auth
   opcional, `DELETE /api/v1/api-keys/{key_id}`.

6. **Registro:** comentar resultado em #26 com:
   - output dos diagnósticos (passos 1 e 4)
   - número de rows backfilladas
   - horário do apply
   - quem executou e quem revisou
   - **link para este audit** (H-01-carryover)

**Rollback:** backup permite restore via `DROP + RENAME`. Preservar ≥30 dias.

---

## H-02-carryover · Ratificar ADRs 0017–0021 (escopo ampliado)

**Status:** OPEN há 5 dias.

**Por que escopo ampliado:** desde 2026-04-22 (quando #28 foi aberta com escopo 2 ADRs)
shipparam:
- ADR-0019 (Cycle 2 entry consolidation+primitive) — accepted em PR pre-tag v4.1.0
- ADR-0020 (calibration harness primitive) — accepted em Cycle 2 W3
- ADR-0021 (Cycle 3 entry) — accepted em PR #38

Por convenção ADR-0000, todos pressupõem revisão humana council. **5 ADRs precisam
ratificação explícita** antes de Cycle 3 W2 fechar.

**Ação:**

1. **Atualizar `body` da issue #28**:
   - Re-renomeie título para `H-03 (P2): council review + ratification of ADRs 0017–0021`.
   - Liste 5 sub-checklists (cada ADR com 3 outcomes: ratify-as-is / reopen-as-proposed / supersede).

2. **Council review** — mantenedor convoca review do time (mesmo solo). Outcome:
   - Ratify-as-is se concordar.
   - Reopen-as-proposed se objeção estrutural.
   - Supersede se decisão diferente — autorar ADR-0024+.

3. **Registrar:** comentário em #28 com nomes + datas. Não fecha issue até todos os 5 ratificados.

---

## H-03-new · README mermaid + ASCII tree fix

**Source:** [02-architecture.md §AUDIT-2026-04-26-001](02-architecture.md#audit-2026-04-26-001).

**Comando para encontrar drift:**

```bash
grep -n "Analysis Engines (40)\|98 endpoints\|40 engines total" README.md
```

**Esperado depois do fix:** zero matches (substituir 40 → 47 e 98 → 122 nas 3
linhas afetadas).

**Bonus:** atualizar mermaid label para refletir contagem ATUAL (e considerar
auto-gerar mermaid section via script, não hard-code).

---

## H-04-new · Estender `check_stats_consistency.py`

**Padrões a adicionar:**

```python
# Em README.md — mermaid blocks
ARCH_MERMAID_PATTERN = r'Analysis Engines\s*\((\d+)\)'

# Em README.md — ASCII tree
ARCH_TREE_PATTERN = r'(\d+) engines total'

# Em README.md — ASCII tree (endpoints)
ARCH_TREE_ENDPOINTS_PATTERN = r'(\d+) endpoints across modular routers'

# Em docs/architecture.md — migration count
ARCH_MIGRATIONS_PATTERN = r'(\d+) migrations\b'

# Em docs/architecture.md — test count
ARCH_TESTS_PATTERN = r'(\d+) tests\b'
```

**Ação:** adicionar checks à `_check()` chain no script + atualizar `paths` no
workflow `doc-sync-check.yml` para listar `docs/architecture.md`.

---

## H-05-new · architecture.md + CLAUDE.md count fix

**Edits manuais:**

- `docs/architecture.md` linha 6: `1435 tests` → `1449 tests`
- `docs/architecture.md` linhas 29 + 90: `25 migrations` → `26 migrations`, `25 .sql files` → `26 .sql files`
- `CLAUDE.md` § Architecture linha ~27: `24 migrations` → `26 migrations`

(Test count em CLAUDE.md está dentro de prosa narrativa do v4.1.0 baseline —
fica como histórico, não atualizar.)

---

## H-06-new · Devils-advocate-as-second-reviewer protocol — codify

**Decisão entre 3 opções:**

| Opção | Custo | Benefício |
|---|---|---|
| (a) ADR-0024 standalone | ~30 min | Indexável, citable; eleva visibilidade |
| (b) Amendment a ADR-0018 §"Process discipline" | ~15 min | Menor surface; mantém 1 ADR como source-of-truth de cycle cadence + PR cadence |
| (c) Section em GOVERNANCE.md | ~10 min | Mais informal; menos rigor histórico |

**Recomendação:** (b) — amendment a ADR-0018. PR cadence é continuação
natural de cycle cadence; manter 1 ADR de governance + process menos overhead.

**Conteúdo do amendment:**

```markdown
### Amendment 1 (2026-04-XX) — PR-level cadence

In addition to the cycle-close 5 doc artifacts (§5), MeridianIQ adopts a
**devils-advocate-as-second-reviewer protocol** for all PRs that:

- Touch ADR-level decisions OR substantive code changes (not 1-line typos,
  Dependabot, catalog regen-only, doc-only LESSONS appends).

The protocol:

1. Author opens PR.
2. Run `Agent(subagent_type="devils-advocate", ...)` with PR-specific prompt.
3. Address blocking findings in fix-up commit on the same branch.
4. Post structured comment: blocking-fixed table + non-blocking-deferred + clean.
5. Self-merge `gh pr merge <N> --rebase --delete-branch` to preserve audit trail.

Rationale: 5 sample PRs in 2026-04-27 (#33, #35, #36, #37, #38) caught
**2 blocking + 4 substantive non-blocking findings/PR average**, including
re-occurring ADR-citation drift. The protocol pays for itself per LESSONS_LEARNED
Cycle 2 §"Post-tag close-arc lessons".
```

---

## H-07-new · Migration 024 ALTER discipline gap

**Discretionary.** Considerar amendment a ADR-0014 ou ADR-0015 §"Decision
drivers" estabelecendo que ALTER em user-owned table com checks novas requer
re-assertion explícita de RLS para visibilidade da policy.

Ou: deletar este finding na próxima rodada se decidirem que o gap não merece
ADR amendment.

---

## H-08-new · Rate-limit policy contract

**Recomendação:** amendment a ADR-0017 (api_keys) ou ADR-0018 (cycle cadence)
documentando heurística:

- `RATE_LIMIT_EXPENSIVE` (3/min) — endpoints que iniciam Monte Carlo, MIP windows, PDF generate.
- `RATE_LIMIT_MODERATE` (10/min) — XER round-trip, batch CRUD, queries N+1 pesadas.
- `RATE_LIMIT_READ` (30/min) — single-resource GETs, healthchecks excetuados.
- **Nenhum decorator** — `/health`, `/openapi.json`, `/docs`.

Test de regressão `tests/test_rate_limit_policy.py` que falha se contract violado.

**Pode aguardar Cycle 4** — não bloqueante.

---

## H-09-new · `RATE_LIMIT_ENABLED` doc em `.env.example`

**Ação simples:** adicionar 3 linhas em `.env.example`:

```bash
# Rate limiting kill-switch — set to "false" to disable all @limiter.limit
# decorators (only useful for incident response or test environments).
# RATE_LIMIT_ENABLED=true
```

---

## H-10-new · `_ENGINE_VERSION` migration

**Já pre-committed Cycle 3 W4** per ADR-0021 §"Wave plan" W4. Sem ação adicional
do handoff — execução wave-time:

1. Editar `src/materializer/runtime.py:54`: `_ENGINE_VERSION = "4.0"` →
   `from src.__about__ import __version__ as _ENGINE_VERSION`.
2. Re-materialize event para 88 derived artifact rows (decisão operator: aceitar
   re-mat OR migration de tombstone).
3. Test de regressão pinning sourcing-from-__about__.

---

## H-11-new · Detail page i18n carry-over

**Issue propose para abrir:**

```
title: i18n: detail + sub-feature pages com $t() = 0 (carry-over de #22)
labels: audit-2026-04-26, priority:P3, area:frontend-ux, type:enhancement
body:

Per [05-ux-frontend.md §AUDIT-2026-04-26-008](docs/audit/2026-04-26/05-ux-frontend.md#audit-2026-04-26-008).

8 páginas com $t() = 0 detectadas. Triagem rápida sugerida:
- auth/callback — minimal, OK em inglês
- [id]/+page.svelte (5 páginas) — verificar individualmente
- cost/g702, cost/compare — alta prioridade, traduzir

Defer: Cycle 4 W5 ou Cycle 5 (não Cycle 3 — escopo W5 é Field Engineer mobile,
não i18n cleanup).
```

---

## H-12-new · Issue #28 body update

**Per AUDIT-2026-04-26-009.** Atualização in-place quando H-02-carryover for
executado. Edit body para listar 5 ADRs.

---

## H-13-new · Meta-issue #25 exit policy

**Discretionary.** Comentar em #25 explicitando uma de duas:

- (a) "Meta-issue fica OPEN como tracking-only até #26 e #28 fecharem; após
  isso, comentar `handoff encerrado` e fechar."
- (b) "Meta-issue de audit é evidência histórica, fica OPEN indefinidamente.
  Remover label `requires-human-decision`."

Decisão de processo, não bloqueante.

---

## Como registrar conclusão (igual baseline)

Para cada item:

1. Comentar na issue/PR o output da verificação.
2. Comentar quem fez / quem revisou + data.
3. Atualizar checkbox aqui via PR.
4. Atualizar meta-issue (se aplicável).

Quando todos H-01-carryover .. H-13-new estiverem fechados/decididos, comentar
em meta-issue desta rodada (a ser criada via H-12-new).

---

## Contato (igual baseline)

- Mantenedor: @VitorMRodovalho
- Canal de segurança: vitorodovalho@gmail.com · `[MeridianIQ security] …`
- Para dúvidas sobre esta auditoria: comentar na issue meta desta rodada
  ou nas issues individuais com label `audit-2026-04-26`.
