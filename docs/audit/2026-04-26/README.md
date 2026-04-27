<!-- Audit run: 2026-04-26 · Base: post-PR #38 (commit ea4ee4d) · Cycle 3 W0 deliverable per ADR-0018 §5 + ADR-0021 §"Pre-registered success criteria" #1 -->
# MeridianIQ — Auditoria Estrutural 2026-04-26

Esta é a **segunda rodada** da auditoria estrutural do repositório, requerida
pelo **ciclo-cadence** estabelecido em [ADR-0018 §5](../../adr/0018-cycle-cadence-doc-artifacts.md)
e pré-registrada como [success criterion #1 do Cycle 3](../../adr/0021-cycle-3-entry-floor-plus-field-shallow.md)
em ADR-0021. A baseline 2026-04-22 vive na raiz de `docs/audit/`; esta rodada
vive em `docs/audit/2026-04-26/`.

**Base do audit:** `main` em `ea4ee4d` (post-PR #38, Cycle 3 W0 entry).
**Tag de produção atual:** `v4.1.0` (Cycle 2 close, 2026-04-26).

## Camadas

| Camada | Documento | Público | Objetivo |
|---|---|---|---|
| **0 — Index** | `README.md` (este) | Todos | Navegação + carry-over consolidado + matriz |
| **1 — Crítico (P0/P1)** | [`01-critical-findings.md`](01-critical-findings.md) | Dev lead, mantenedor | Issues bloqueantes — minimal nesta rodada |
| **2a — Arquitetura** | [`02-architecture.md`](02-architecture.md) | Eng. backend | Stack real vs documentado, contagens estruturais |
| **2b — Schema** | [`03-schema.md`](03-schema.md) | Eng. backend, DBA | Migrations 022-026, RLS, FK/cascade |
| **2c — Segurança** | [`04-security.md`](04-security.md) | Security eng. | Rate-limit gaps, fail-closed status, CORS, env hygiene |
| **2d — UX / Frontend** | [`05-ux-frontend.md`](05-ux-frontend.md) | Eng. frontend, design | i18n cobertura em detail pages, runes purity |
| **2e — Planejado vs. Implementado** | [`06-planned-vs-implemented.md`](06-planned-vs-implemented.md) | Product, tech lead | Cycle 1+2 ADR cross-check, Cycle 3 plan |
| **3 — Handoff** | [`HANDOFF.md`](HANDOFF.md) | Todo o time | Carry-over + novas ações humanas |
| **4 — Closing** | [`CLOSING_REPORT.md`](CLOSING_REPORT.md) | Todos | Sumário executivo do que aconteceu nesta rodada |

Issues do GitHub rotuladas com `audit-2026-04-26` apontam cada item acionável
para uma seção destes documentos.

## Metodologia

Idêntica à baseline 2026-04-22 (5 etapas — recon estático + inventário por
contagem + verificação ativa via grep + cross-check de consistência + cruzamento
com ADRs); ver [baseline `README.md`](../README.md#metodologia).

**Adições nesta rodada (cobertura nova):**

- **5 novos ADRs (0017–0021)** cross-checked contra código corrente (cada um deve continuar em vigor ou ter sucessor).
- **Migrations 022–026** verificadas individualmente quanto a RLS / FK / CASCADE.
- **Engine novo `lifecycle_phase.py`** — citação de standard + integração com store + ADR-0016.
- **Módulo novo `tools/calibration_harness.py`** — ADR-0020 — verificar localização fora de `src/` + decisão caveat.
- **D4 backend wiring** — `RiskStore.bind_job` + `GET /api/v1/risk/simulations/by-job/{job_id}` (PR #35).
- **Materializer** (`src/materializer/runtime.py`, ADR-0014/0015) — `_ENGINE_VERSION` divergence status.
- **Process scope** — devils-advocate-as-second-reviewer protocol (ADR-0021 §"Open process gap").

## Carry-over consolidado dos 18 AUDIT-NNN da baseline

Verificado endpoint-a-endpoint via grep matrices + git log + `gh issue view`.

| ID | Sev (orig) | Status atual | Evidência |
|---|---|---|---|
| AUDIT-001 | P0 | **Resolvido em código (carry-over operator)** | `012_api_keys.sql` header reads "SUPERSEDED BY 017 + 026". Migration 026 presente. Prod apply ainda PENDENTE — issue [#26](https://github.com/VitorMRodovalho/meridianiq/issues/26) OPEN há 5 dias |
| AUDIT-002 | P1 | **Resolvido** | `src/api/auth.py:141,151,273,291,337,346,384,395` — 8 checks `ENVIRONMENT == "production"` |
| AUDIT-003 | P1 | **Parcialmente resolvido — gap remanescente** | Matrix abaixo + [04-security.md §rate-limit-coverage-gaps](04-security.md#rate-limit-coverage-gaps). risk 1/9, analysis 0/11, intelligence 1/8, programs 0/5, benchmarks/bi/plugins ainda 0 |
| AUDIT-004 | P1 | **Resolvido** | `src/api/app.py:73` — `os.environ.get("ALLOWED_ORIGINS", _DEFAULT_CORS_ORIGINS)` ativo |
| AUDIT-005 | P2 | **Resolvido** | `.env.example` documenta ALLOWED_ORIGINS, SENTRY_DSN, ANTHROPIC_API_KEY, PUBLIC_POSTHOG_KEY, PORT, FLY_API_TOKEN (commented = optional). `RATE_LIMIT_ENABLED` ainda não documentado — minor sub-finding em [04-security.md](04-security.md) |
| AUDIT-006 | P2 | **REGRESSÃO** — fix incompleto | `README.md` mermaid (linha 123) ainda diz "Analysis Engines (40)... 98 endpoints"; ASCII tree (linhas 323, 327) idem. `check_stats_consistency.py` valida só §"Key Numbers" header não-Mermaid. Ver AUDIT-2026-04-26-001 em [02-architecture.md](02-architecture.md) |
| AUDIT-007 | P2 | **Resolvido** | BUGS.md header `v4.1.0`; SECURITY.md sem versão stale |
| AUDIT-008 | P2 | **Resolvido** | CLAUDE.md linha 15: "Docker (API + web — `web/Dockerfile` builds a static Nginx image)" |
| AUDIT-009 | P3 | **REGRESSÃO** — drift novo | `docs/architecture.md` ainda diz "25 migrations" em 3 lugares; CLAUDE.md diz "24 migrations" (linha 27); contagem real = 26. Test count também: arch.md=1435, CLAUDE.md=1429, real=1449. Ver AUDIT-2026-04-26-002 |
| AUDIT-010 | P2 | **Parcialmente resolvido — escopo só top-level** | #22 fechou as 15 top-level pages mas detail pages (`[id]/+page.svelte`, `cost/g702/`, `cost/compare/`) ainda têm `$t=0`. Eram out-of-scope de #22 — agora reabre como AUDIT-2026-04-26-008 em [05-ux-frontend.md](05-ux-frontend.md) |
| AUDIT-011 | P2 | **Resolvido** | `docs/GAP_ASSESSMENT_v3.3.md` arquivado em `docs/archive/v3.3-planning/GAP_ASSESSMENT.md` |
| AUDIT-012 | P3 | **Reaffirmed (justificativa corrigida)** | Dockerfile `python:3.13-slim`; `pyiceberg` é transitivo via `storage3` (CLAUDE.md já reflete). f1bd4e2 tentou 3.14, df672d9 reverteu. **Manter** |
| AUDIT-013 | P3 | **Resolvido** | `git branch -a \| grep "v0\.[2-5]"` → vazio (local + remote limpos) |
| AUDIT-014 | P3 | **Resolvido + ampliado** | `docs/adr/README.md` agora explicita "reservado, não autorado" para 0010, 0011, 0022, 0023 (PR #38). 0010/0011 conformes; 0022/0023 com link para ADR-0021 §"Decision" |
| AUDIT-015 | P2 | **Resolvido** | Sub-issues #29 (P1), #30 (P2), #31 (P2), #32 (P3) abertos; #23 ainda OPEN como umbrella |
| AUDIT-016 | P3 | **Resolvido (closed not_planned)** | Issue #8 CLOSED, stateReason `NOT_PLANNED` |
| AUDIT-017 | P3 | **Resolvido (closed completed)** | Issue #14 CLOSED, stateReason `COMPLETED` (8005ac5 + ADR-0019 §W0) |
| AUDIT-018 | P3 | **Resolvido** | PRs #11, #15, #34 todos MERGED |

**Resumo carry-over:** 11 resolvidos limpos, 3 com regressão/sub-finding identificado nesta rodada (AUDIT-006/009/010), 1 reaffirmed (012), 3 ainda em flight como operator (#26 P0 prod migration, #28 P2 ratificação, #23/#29-32 P1/P2/P3 Wave 7 features).

## Matriz consolidada — achados NOVOS desta rodada

Numeração date-namespaced (`AUDIT-2026-04-26-NNN`) para evitar colisão com baseline `AUDIT-001`–`AUDIT-018`.

| ID | Camada | Severidade | Título | Docs |
|----|----|----|----|----|
| AUDIT-2026-04-26-001 | Docs/Arch | **P2** | `README.md` mermaid + ASCII tree retêm "40 engines / 98 endpoints" — `check_stats_consistency.py` não captura | [02-architecture.md](02-architecture.md#audit-2026-04-26-001) |
| AUDIT-2026-04-26-002 | Docs | **P3** | `docs/architecture.md` desatualizado (25 migrations, 1435 tests) + CLAUDE.md (24 migrations, 1429 tests) — drift assimétrico | [02-architecture.md](02-architecture.md#audit-2026-04-26-002) |
| AUDIT-2026-04-26-003 | Arch/Process | **P2** | Devils-advocate-as-second-reviewer protocol — open process gap (auto-disclosure em ADR-0021 §"Open process gap" — confirma) | [02-architecture.md](02-architecture.md#audit-2026-04-26-003) |
| AUDIT-2026-04-26-004 | Schema | **P3** | Migration `024_projects_status_state.sql` altera tabela existente sem re-emitir `ENABLE ROW LEVEL SECURITY` (RLS herdada de migration 001 — verificar não-degradação) | [03-schema.md](03-schema.md#audit-2026-04-26-004) |
| AUDIT-2026-04-26-005 | Security | **P3** | Rate-limit coverage matrix tem ≥9 routers com < metade dos endpoints limitados; falta política documentada no ADR de qual endpoint precisa de qual bucket | [04-security.md](04-security.md#audit-2026-04-26-005) |
| AUDIT-2026-04-26-006 | Security | **P3** | `.env.example` não documenta `RATE_LIMIT_ENABLED` (variável real consumida em `src/api/deps.py:116`) | [04-security.md](04-security.md#audit-2026-04-26-006) |
| AUDIT-2026-04-26-007 | Arch | **P2** | `_ENGINE_VERSION = "4.0"` hardcoded em `src/materializer/runtime.py:54` — ADR-0014 §"Decision Outcome" sources from `src/__about__.py::__version__` (load-bearing forensic provenance — parte do UNIQUE constraint em `schedule_derived_artifacts`; reescalado P3→P2 pós-DA review) | [02-architecture.md](02-architecture.md#audit-2026-04-26-007) |
| AUDIT-2026-04-26-008 | UX | **P3** | Detail pages (`[id]/+page.svelte`) + `cost/g702`, `cost/compare`, `auth/callback` têm `$t() = 0` — out-of-scope de #22 mas blockam i18n end-to-end | [05-ux-frontend.md](05-ux-frontend.md#audit-2026-04-26-008) |
| AUDIT-2026-04-26-009 | Planned | **P3** | Issue #28 ADR ratification escopo agora inclui ADR-0019/0020/0021 (3 ADRs adicionais sobre os 2 originais 0017+0018) — atualizar issue body | [06-planned-vs-implemented.md](06-planned-vs-implemented.md#audit-2026-04-26-009) |
| AUDIT-2026-04-26-010 | Planned | **P3** | Issue #25 (meta-tracking) ainda aberta; checklist de exit ainda tem 2 unchecked (#26 prod apply, #28 ratificação). Considerar amendar ADR-0018 §5 explicitando que meta-issue só fecha após apply+ratificação | [06-planned-vs-implemented.md](06-planned-vs-implemented.md#audit-2026-04-26-010) |
| AUDIT-2026-04-26-011 | Arch | **P2** | ADR-0014 §"Decision Outcome" cita `src/__about__.py::__version__` como source-of-truth de `engine_version` — **arquivo nunca existiu no repo** (verificado via `ls`). ADR aceito 2026-04-18 (Cycle 1 W1) é non-implementable as-written desde então; multi-cycle invisible structural drift | [02-architecture.md](02-architecture.md#audit-2026-04-26-011) |

**P0 = perda de integridade / bloqueio de produção; P1 = mitigar ≤ 30 dias; P2 = mitigar ≤ 90 dias; P3 = higiene contínua.**

## Inventário (contagens autoritativas em 2026-04-26)

| Métrica | Valor | Fonte canonical | Drift detectado |
|---|---|---|---|
| Engines | 47 + 1 export | `docs/methodologies.md` header | README mermaid + ASCII (legacy 40); CLAUDE.md OK; arch.md OK |
| API endpoints | 122 | `docs/api-reference.md` header | README mermaid (legacy 98); CLAUDE.md OK; arch.md OK |
| Routers | 23 (22 .py + `__init__`) | api-reference.md | OK |
| MCP tools | 22 | `docs/mcp-tools.md` header | OK |
| Frontend pages | 54 | `find web/src/routes -name +page.svelte` | OK |
| Migrations | 26 | `ls supabase/migrations/*.sql` | CLAUDE.md=24 (drift); arch.md=25 (drift) |
| ADRs | 22 .md (incl. README + 0009-w4-outcome) | `ls docs/adr/*.md` | OK |
| Tests | **1449 collected** | `pytest --collect-only` | CLAUDE.md=1429 (Cycle 1); arch.md=1435 (v4.0.2); drift novo |
| Pre-existente Co-Authored-By: Claude commits | ≥5 (histórico) | `git log --grep=Co-Authored-By: Claude` | Não-acionável (user CLAUDE.md proíbe rewrite sem auth explícita) |

## Escopo NÃO coberto

- Teste de carga / performance (idem baseline).
- Varredura SAST/DAST (gitleaks + CodeQL agendados — ver `.github/workflows/`).
- Revisão linha-a-linha dos 47 engines.
- Revisão jurídica binding (LGPD/GDPR/LICENSE — `legal-and-accountability` agent só hipóteses).
- Re-verificação numérica de W4 calibration (depende de `/tmp/w4_*.json` que estão extant em 2026-04-26 mas não pertencem a este audit).
- **Materializer state machine ADR-0015 runtime behavior** — verificação estática (RLS coverage de migrations 022-026) feita; mas comportamento `pending → ready → failed` em cold-start cascade + StaleMaterializationError recovery não foi exercitado nesta rodada. Considerar contract test em rodada futura.
- **Sentry / observability event-flow** — `SENTRY_DSN` documentado, init em `src/api/app.py`, mas se eventos chegam corretamente em produção não foi verificado nesta rodada (presume-se OK; `04-security.md` walks past).
- **Issue #28 body atual** — assertiva "ainda lista só 0017+0018" inferida via `gh issue view 28 --json body` (verificada em pre-flight). Estado pode mudar até este PR mergear.

## Quando re-rodar

Per [ADR-0018 §5](../../adr/0018-cycle-cadence-doc-artifacts.md):

- Ao **fechar Cycle 3** (próxima rodada esperada: post-tag v4.2.0 — eta indefinido entre maio-junho 2026).
- Antes de qualquer release rotulada `vX.0.0` (major).
- Se um ADR de peso for autorado (ex: ADR-0024 que formalize devils-advocate-as-second-reviewer).

— Esta rodada arquivada em `docs/audit/2026-04-26/`. Próxima rodada vai para
`docs/audit/YYYY-MM-DD/` no fechamento de Cycle 3.
