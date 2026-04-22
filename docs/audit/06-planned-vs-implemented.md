<!-- Audit run: 2026-04-22 · Layer 2e -->
# Camada 2e — Planejado vs. Implementado

## Roadmap e onde ele vive

O repo **não tem um `docs/ROADMAP.md` atual**. Os documentos de roadmap ativos são:

| Documento | Escopo | Status |
|---|---|---|
| `docs/SCHEDULE_VIEWER_ROADMAP.md` | Feature-specific (Gantt viewer) | Parcialmente atualizado; header diz "v3.6.0-dev" |
| `docs/archive/v06-planning/ROADMAP_v06_to_v20.md` | Histórico (até v2.0) | Arquivado — CLAUDE.md o cita como contexto |
| `docs/archive/v08-planning/*` | Histórico (v0.8 waves) | Arquivado |
| `docs/adr/0009-cycle1-lifecycle-intelligence.md` | Ciclo 1 v4.0 planning (W0–W6 + amendments) | Accepted — a única fonte viva de planejamento recente |
| Agent memory (`.claude/` + `memory/`) | Cycle planning notes | Fora do escopo git |

**Consequência:** um contribuidor externo não tem visão de roadmap futuro. ADR-0009
é denso e específico a um cycle fechado. `BUGS.md` tem uma seção "Feature Backlog"
mas é parcialmente obsoleta (ver abaixo).

**Recomenda-se criar `docs/ROADMAP.md` versionado** — mesmo que seja apenas:
"Cycle 2 inicia <data>. Escopo provável: Wave 7 (resource & cost) + TS errors (#8)
+ optimizer fix (#14). Não planejado: lifecycle_health (deferred per ADR-0009 §W4
outcome)."

## Status do Cycle 1 v4.0 (ADR-0009)

Extraído do CLAUDE.md e `docs/adr/0009-*`:

| Wave | Escopo | Status |
|---|---|---|
| W0 | Governance + hardening (migration 021, ADRs 0006–0008 backfill, defusedxml, programs uniqueness, schedule `status` machine, ADR-0013 WS hardening) | ✅ Shipped |
| W1 | Materialization foundation (migration 023, ADR-0014 input_hash) | ✅ Shipped |
| W2 | Async materializer (`src/materializer/`, asyncio + Semaphore + ProcessPool, ADR-0015) | ✅ Shipped |
| W3 | Lifecycle phase inference (`src/analytics/lifecycle_phase.py`, override + sticky lock, ADR-0016) | ✅ Shipped |
| W4 | Calibration + gate (ADR-0009 Amendments 1+2, 103-XER sandbox) | ✅ Ran — **gate failed at every threshold**; fallback activated |
| W5/W6 | **Path A fallback** (carry-over: `progress_callback` em evolution_optimizer, `useWebSocketProgress` composable, i18n 7 keys × 3 locales) | ✅ Shipped |
| W5/W6 | **Path B (if W4 passed): `lifecycle_health.py` + ADR-0010** | ❌ **NOT shipped** (pre-committed deferral; ADR-0010 reservado) |

**Observação:** este é um registro exemplar de "planejado vs. implementado" —
o cycle foi explicitamente dividido em branches condicionais, o gate foi rodado,
o resultado foi registrado, e a decisão pré-comprometida foi honrada. Modelo
para futuros cycles.

## Doc-drift — catálogo

Cruzamento entre `CLAUDE.md`, `README.md`, `docs/architecture.md`, e realidade:

| Afirmação | Local | Realidade | Severidade |
|---|---|---|---|
| "40 + 1 export module" | `README.md` §"Key Numbers" | **47 + 1** | P2 |
| "98 API endpoints" | `README.md` §"Key Numbers" | **121** | P2 |
| "52 frontend pages" | `README.md` §"Key Numbers" | **54** | P2 |
| "870+ tests" | `README.md` + CLAUDE.md | **1350** | P2 |
| "no web/Dockerfile yet" | `CLAUDE.md` §"Build & Run" | Arquivo existe (`web/Dockerfile`, BUG-011 fechado em v0.9.0) | P2 |
| "20 .sql files (RLS enforced on user-owned tables)" | `docs/architecture.md` §"Repository layout" | **25** | P3 |
| "Dockerfile: Python 3.13-slim (pyiceberg lacks 3.14 wheel)" | `CLAUDE.md` | `pyiceberg` não está em `pyproject.toml` — justificativa obsoleta | P3 |
| "v3.6.x current stable" | `SECURITY.md` §"Supported Versions" | `v4.0.x` | P2 |
| "Version: v3.6.0-dev" | `BUGS.md` header | `v4.0.1` | P2 |
| `release="meridianiq-api@4.0.0"` | `src/api/app.py:23` | `4.0.1` | P2 |
| "Cycle 1 delivered in 7 waves" | `CLAUDE.md` §"Workflow" | 7 waves OK (W0–W6, mas W4 também rodou calibration parcialmente); acurado. | OK |

**Proposta de mitigação:** auto-gerar `README.md §Key Numbers` a partir do mesmo
script que regenera `docs/api-reference.md`. Adicionar ao `doc-sync-check.yml`
workflow para travar PRs que deixam a discrepância passar.

## Backlog sem issue

Itens identificados em `BUGS.md §Feature Backlog` e em `docs/SCHEDULE_VIEWER_ROADMAP.md`
que **não têm issue GitHub correspondente**:

| Item | Fonte | Effort | Prioridade sugerida |
|---|---|---|---|
| Resource histogram below Gantt | SV Roadmap Wave 7 | High | P1 (feature-gap principal) |
| Cost-loading curve overlay | SV Roadmap Wave 7 | Medium-High | P2 |
| Budget vs actual por activity | SV Roadmap Wave 7 + CBS persistence | High | P2 |
| Resource-constrained CP highlighting | SV Roadmap Wave 7 | High | P3 |
| PNG/SVG raster export | SV Roadmap Wave 8 | Medium | P3 |
| Excel com Gantt styling | SV Roadmap Wave 8 | Medium | P3 |
| Print preview com WBS page breaks | SV Roadmap Wave 8 | Low | P3 |
| AIA G703 schedule submission PDF | SV Roadmap Research | High | P3 (future) |
| AACE RP 29R-03 §5.3 forensic submission PDF | SV Roadmap Research | High | P3 |
| Federated learning (cross-org ML) | BUGS.md #17 | High | P4 (research) |
| BIM-lite (IFC metadata) | BUGS.md #18 | High | P4 (research) |
| GIS para linear scheduling | BUGS.md #20 | High | P4 (research) |

**Ação:** abrir issues individuais para as Wave 7/8 (feature-gap) com labels
`type:feature`, `wave:7` ou `wave:8`, `audit-2026-04-22`. Research items (last 3)
podem ser agregados em um único tracking issue "Research backlog — not scheduled".

## Backlog com issue aberta mas sem progresso rastreado

| Issue | Aberta desde | Release subsequente citou? |
|---|---|---|
| #8 (17 TS errors, 7 files) | 2026-03-29 | Nenhuma referência em v4.0.0 / v4.0.1 release notes |
| #13 (calibration dataset contributions) | 2026-04-19 | Cita o W4 outcome (ADR-0009 §W4) — issue É o contrib ask |
| #14 (optimizer page field mismatch) | 2026-04-19 | v4.0.1 notes explicitamente "NOT fixed this patch" |

**Observação:** #13 está corretamente posicionado (contribuidor externo ask).
#8 e #14 deveriam estar em roadmap do Cycle 2.

## Histórico → arquivo

Recomendações de arquivamento para reduzir ruído cognitivo:

- `docs/GAP_ASSESSMENT_v3.3.md` → `docs/archive/v3.3-planning/GAP_ASSESSMENT.md`
- `BUGS.md` seção "Previously Fixed" (linhas 17–62) → `docs/archive/BUGS_HISTORY.md`
  com link reverso no `BUGS.md` principal.
- Branches `v0.{2,3,4,5}-*` → `git branch -D` local (ver Camada 2a).

## Lacuna metodológica

Hoje o projeto tem:

- ADRs (decisões de arquitetura) ✅
- BUGS.md (bugs abertos/fechados) ✅
- CHANGELOG.md (release notes) ✅

Mas não tem:

- **Roadmap ativo** (apenas fragmentos em ADR-0009 e SV Roadmap)
- **Feature Backlog registrado em issues** (parcialmente em BUGS.md)
- **Post-mortem / lessons learned por cycle** (LESSONS_LEARNED.md é de 2026-04-02
  e não foi atualizado desde)

Propor em nova **ADR-0018**: "Cycle cadence doc artifacts" — listar quais 5 docs
devem existir/atualizar a cada cycle (roadmap, backlog-pruning, lessons-learned,
catalog regeneration, audit re-run).
