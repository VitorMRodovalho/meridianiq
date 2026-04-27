<!-- Audit run: 2026-04-26 · Layer 1 (Critical) -->
# Camada 1 — Achados Críticos (P0/P1)

**Resumo:** **Zero achados P0 ou P1 NOVOS** nesta rodada. Os 4 P0/P1 da
baseline 2026-04-22 (AUDIT-001..004) estão **todos resolvidos em código**;
um deles permanece em flight como ação de operador.

Este documento existe para registro formal — a ausência de novos P0/P1 é
um sinal positivo da efetividade do Cycle 2 W0 + Wave-A/B/C remediação da
baseline. Mantemos a estrutura de 6 camadas para consistência com a
baseline e para auditorias futuras.

---

## Carry-over P0/P1

### Carry-over · P0 ops · #26 · Aplicar migration 026 em produção (`api_keys` schema dedup)

**Status:** OPEN há 5 dias (2026-04-22 → 2026-04-26).

**Por que ainda é crítico:** se o produto for usado em produção entre a
baseline e agora, qualquer instância Supabase em que migration `012` rodou
antes de `017` ainda tem schema legado (`id UUID`, `key_prefix`, `is_active`,
`expires_at`) — incompatível com `src/api/auth.py` que espera o schema do
017 (`id BIGINT`, `key_id`, `revoked_at`). Para tais instâncias:

1. `POST /api/v1/api-keys` falha silenciosamente (insert rejeita por coluna ausente).
2. `validate_api_key` retorna 503 (fail-closed implementado em [Wave B3 do baseline](../CLOSING_REPORT.md#wave-b3)).
3. End-users veem "Auth service degraded" sem clareza de que o root cause é o schema.

**Severidade não escalou** — o fail-closed do Wave B3 transformou a falha
silenciosa em 503 estruturado, então o ponto de saturação é UX-degraded
e não data-corruption. **Mas o item ainda é P0 porque:** o produto não consegue
emitir API keys novas, e qualquer documentação que prometa "API key auth funciona"
é falsa em prod-instances pre-026.

**Ação:** ver [`HANDOFF.md §H-01-carryover`](HANDOFF.md#h-01-carryover) — runbook
operator-only, executor maintainer + DBA. Output: comentar resultado em #26.

### Carry-over · Sem novos P1

AUDIT-002 (api_key fail-closed in prod) — RESOLVIDO `06fa945` + verificado por
8 ocorrências de `if settings.ENVIRONMENT == "production":` em `src/api/auth.py`.
Sem regressão.

AUDIT-003 (rate-limit gap) — PARCIALMENTE resolvido em Wave B2; gap remanescente
é **classificação P3** (matrix coverage discipline, não falha runtime). Tratado
como AUDIT-2026-04-26-005 em [`04-security.md`](04-security.md#audit-2026-04-26-005)
em vez de carry-over P1.

AUDIT-004 (CORS hardcoded) — RESOLVIDO `93809e9` + verificado em
`src/api/app.py:73`. Sem regressão.

---

## Por que zero P0/P1 novos é crível, não complacente

Cycle 1 + Cycle 2 não introduziram novos componentes de superfície de ataque
runtime (auth, network ingress, schema FK). Tudo que entrou:

- **Migration 022** — adiciona UNIQUE em coluna existente (`programs`); ALTER
  não toca RLS herdada de migration 005.
- **Migration 023** — `schedule_derived_artifacts` table com quadruple RLS
  (4 policies). Cobertura adequada — verificado em [`03-schema.md`](03-schema.md).
- **Migration 024** — adiciona `status` column + CHECK em `projects`. RLS herdada
  de 001/002. Verificado.
- **Migration 025** — `lifecycle_phase_locks` + `lifecycle_phase_overrides` —
  RLS enable + 2 policies. Verificado.
- **Migration 026** — ALTER `api_keys` (idempotent) + 3 policies. RLS herdada
  de 017. Verificado.
- **`tools/calibration_harness.py`** — fora de `src/` (não exposto em endpoint),
  não toca runtime auth/network.
- **D4 backend wiring** — `RiskStore.bind_job` (in-memory + sintetiza ID) +
  `GET /api/v1/risk/simulations/by-job/{job_id}` — endpoint **autenticado** com
  rate-limit `RATE_LIMIT_READ`. Verificado em [`04-security.md`](04-security.md).
- **WS heartbeat** (Cycle 2 W1) — re-checa JWT exp + valida API key — endurece
  surface, não amplia.

A ausência de P1/P0 novos reflete:

1. Cycle 1 (materialização + lifecycle) ficou nos contratos pre-existentes.
2. Cycle 2 (consolidação) deliberadamente NÃO commitou um deep — risco contido por design.
3. Cycle 3 W0 (até agora) é doc-only — sem novo código runtime.

Esta característica **muda em Cycle 3 W3** quando a regression test do W4 for
adicionada (acessa harness + testes — superfície CI, não runtime) e em **W4**
quando `_ENGINE_VERSION` migrar (toca materializer state — verificar em audit
post-Cycle-3).

---

**Escopo encerrado desta camada.** Itens P2/P3 estão nas camadas 2a–2e.
