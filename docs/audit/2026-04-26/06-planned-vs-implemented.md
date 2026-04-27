<!-- Audit run: 2026-04-26 · Layer 2e (Planned vs Implemented) -->
# Camada 2e — Planejado vs. Implementado

Cycle 1+2 ADR cross-check, Cycle 3 plan reconciliation, doc-drift status.

## Cycle 1 (v4.0.0) — RECAP retrospectivo

Per ADR-0009 + W4 outcome record:

| Wave | Escopo | Status |
|---|---|---|
| W0 | Governance + hardening (mig 021, ADRs 0006-0008 backfilled, defusedxml, programs UNIQUE, schedule status, ADR-0013 WS hardening) | ✅ Shipped |
| W1 | Materialization foundation (mig 023, ADR-0014 input_hash) | ✅ Shipped |
| W2 | Async materializer (asyncio Task + Semaphore + ProcessPool, ADR-0015) | ✅ Shipped |
| W3 | Lifecycle phase inference (lifecycle_phase.py, ADR-0016) | ✅ Shipped |
| W4 | Calibration + gate (ADR-0009 Am.1+2, 103-XER) | ✅ Ran — gate failed at all thresholds. Path A activated |
| W5/W6 | Path A carry-over (progress_callback + useWebSocketProgress) | ✅ Shipped |
| W5/W6 | Path B (lifecycle_health) — conditional on W4 pass | ❌ Pre-committed deferral; ADR-0010 reserved |

**Modelar:** este wave foi explicitamente dividido em branches condicionais com
gate runado, outcome registrado, decisão pré-comprometida honrada. Mantém-se como
template para Cycle 3.

## Cycle 2 (v4.1.0) — RECAP retrospectivo

Per ADR-0019:

| Wave | Escopo | Status |
|---|---|---|
| W0 | hygiene — RATE_LIMIT_READ on jobs/progress/start; slowapi in [dev] extras; useWebSocketProgress.destroy() | ✅ Shipped (b924b93) |
| W1 | WS resilience — heartbeat + recoveryPoller composable (D4 contract) | ✅ Shipped (567a604) |
| W2 | B2 honesty-debt closure — is_construction_active tri-state + LifecyclePhaseCard split UI + 7 i18n keys × 3 locales + W4 post-mortem | ✅ Shipped (b40d184) |
| W3 | Calibration harness primitive — tools/calibration_harness.py + ADR-0020 | ✅ Shipped |
| Pre-registered success criteria | 7/7 closed (criterion 7 = release tag) | ✅ |

**Pendências post-tag:** D4 backend wiring deferred at composable level (PR #35,
v4.1.0 Cycle 2 close-arc). `_ENGINE_VERSION` divergence partially closed (PR #36,
v4.1.0 Cycle 2 close-arc) — hardcoded constant deduped but ADR-0014 source-of-truth
contract still violated.

## Cycle 3 (v4.2.0 ou v4.1.1) — Plan e progresso atual

Per ADR-0021 §"Wave plan":

| Wave | Delivers | Status |
|---|---|---|
| W0 | This entry + ADR-0021 + ADR-0022/0023 reservations + 2026-04-26 audit re-run | **In flight** — ADR-0021 + ROADMAP shippado em PR #38 (`ea4ee4d`); audit re-run = ESTE PR |
| W1 | #26 migration apply per HANDOFF §H-01 (operator) | OPEN (5 dias) |
| W2 | #28 ratifications + W4 manifest archive (re-run protocol if /tmp rotated) | OPEN |
| W3 | tests/test_w4_reproduction.py — pins harness vs script equivalence on W4 input | NOT STARTED |
| W4 | _ENGINE_VERSION → src/__about__.py per ADR-0014 + 88-row re-materialize | NOT STARTED |
| W5 (optional) | Field Engineer mobile look-ahead spike. Sub-pick deferred to W4 close | NOT STARTED |

**Pre-registered success criteria (9 from ADR-0021):**

1. ✅ Audit re-run published — closes em mergear deste PR
2. OPEN — #26 prod migration apply
3. OPEN — #28 ADR ratifications  
4. OPEN — W4 manifest archive
5. OPEN — W3 reproduction regression test
6. OPEN — `_ENGINE_VERSION` → `__about__.py` migration
7. OPEN — 88-row re-materialize event
8. OPTIONAL — W5 Field Engineer spike
9. OPEN — release tag (v4.2.0 ou v4.1.1)

Cycle 3 fica **graceful** se ≥5 dos 9 critérios fechem; o resto é cleanly
documentado para Cycle 3.5 ou Cycle 4.

---

## Doc-drift catálogo desta rodada

Cruzamento atualizado entre CLAUDE.md, README.md, docs/architecture.md,
docs/api-reference.md, docs/methodologies.md, docs/mcp-tools.md, e realidade:

| Afirmação | Local | Realidade | Severidade |
|---|---|---|---|
| "47 + 1 export" / "122 endpoints" | `README.md` §"Key Numbers" | OK | ✅ |
| `Analysis Engines (40)... 98 endpoints` | `README.md` mermaid linha 123 | **47 / 122** | P2 (AUDIT-2026-04-26-001) |
| `40 engines total + 1 export` / `98 endpoints across modular routers` | `README.md` ASCII tree linhas 323, 327 | **47 / 122** | P2 (AUDIT-2026-04-26-001) |
| "24 migrations" | `CLAUDE.md` §Architecture | **26** | P3 (AUDIT-2026-04-26-002) |
| "25 migrations" | `docs/architecture.md` linhas 29, 90 (3 lugares) | **26** | P3 |
| "1429 tests" | `CLAUDE.md` (v4.1.0 baseline prosa) | **1449** | P3 |
| "1435 tests" | `docs/architecture.md` linha 6 | **1449** | P3 |
| "v4.0.x current stable" | `SECURITY.md` | OK (fica sem versão stale) | ✅ |
| "v3.6.0-dev" | `BUGS.md` header | OK ("v4.1.0") | ✅ |

**Mitigação:**

- `check_stats_consistency.py` cobre CLAUDE.md §Architecture + README §"Key Numbers".
  **Falha em capturar mermaid + ASCII tree drift no README** + **architecture.md
  está fora do escopo do guard** → AUDIT-2026-04-26-001 + AUDIT-2026-04-26-002.

- Estender o script para escanear:
  - mermaid blocks (`Analysis Engines\s*\(\d+\)`) em README.
  - ASCII tree (`(\d+) engines total`) em README.
  - architecture.md (`(\d+) migrations`, `(\d+) tests`).

---

## Backlog status (post-Cycle 2 audit-2026-04-22 closure)

Issues abertas com label `audit-2026-04-22`:

| # | Sev | Título | Status |
|---|---|---|---|
| #23 | P2 | AUDIT-015 — Schedule Viewer Wave 7 umbrella | OPEN — sub-issues #29-#32 abertos |
| #25 | — | Meta: 2026-04-22 structural audit tracking | OPEN (não fecha até #26 + #28 closed) |
| #26 | **P0 ops** | H-01 — apply migration 026 prod | OPEN há 5 dias |
| #28 | P2 | H-03 — ratify ADR-0017 + ADR-0018 | OPEN há 5 dias |

**Sub-issues Wave 7 (#29-#32):** todos OPEN. Cycle 3 W0 entry deliberadamente não
commit a essas. Cycle 4 W5 alternative pick (Cost Engineer responsive Gantt)
poderia consumir uma delas.

**Backlog #29 #30 #31 #32 cross-check:**

- #29 (P1): Resource histogram below Gantt — Wave 7-A
- #30 (P2): Cost-loading curve overlay on timeline — Wave 7-B
- #31 (P2): Budget vs actual cost per activity (BVA) — Wave 7-C
- #32 (P3): Resource-constrained critical path highlighting — Wave 7-D

---

## AUDIT-2026-04-26-009 · P3 · Issue #28 escopo desatualizado

**Estado atual:** Issue #28 body lista apenas ADR-0017 e ADR-0018 (do escopo da
remediação 2026-04-22).

**Realidade:** ADRs adicionais shipados desde então também precisam ratificação
explícita por convenção ADR-0000 (acceptance pressupõe revisão humana):
- ADR-0019 (Cycle 2 entry consolidation+primitive)
- ADR-0020 (calibration harness primitive)
- ADR-0021 (Cycle 3 entry — em flight neste PR)

**Risco:** P3. **Discipline gap:** issue body desatualizado faz a ratificação
correr em half-state — alguém pode ratificar 0017+0018 e fechar a issue, deixando
0019/0020/0021 sem ratificação registrada.

**Ação:**

1. Atualizar `body` da issue #28 para listar 5 ADRs (0017, 0018, 0019, 0020, 0021).
2. Renomear título para `H-03 (P2): council review + ratification of ADRs 0017–0021`.
3. Adicionar checkboxes individuais por ADR.

---

## AUDIT-2026-04-26-010 · P3 · Meta-issue #25 exit checklist precisa amendment

**Estado atual:** issue #25 (meta-tracking 2026-04-22) tem `exit checklist` no
body com 6 checkboxes marcados + 2 unchecked (`#26 prod migration`, `#28 ratify`).

**Realidade:** estes 2 unchecked **continuam unchecked** após 5 dias. ADR-0018 §5
estabelece que "audit re-run encerra" sem cláusula explícita sobre o que conta
como "audit fully closed".

**Discipline gap:** meta-issue pode ficar OPEN indefinidamente — o que ainda é
fiel ao espírito do ADR-0018 §5 (audit é evidência histórica, não "task aberto"),
mas labels podem proliferar.

**Ação proposta:**

1. Considerar amendment a ADR-0018 §5: "meta-issue de audit fica OPEN até
   `requires-human-decision` items associados fecharem; após isso, fechar
   meta-issue com comentário `handoff encerrado`."
2. Ou comentar em #25 explicitando que meta-issue fica OPEN como tracking-only
   (não actionable) e remover label `requires-human-decision`.

---

## Lacuna metodológica (carry-over)

Baseline §"Lacuna metodológica" listou 3 docs faltando:

| Doc | Estado em 2026-04-22 | Estado em 2026-04-26 |
|---|---|---|
| Roadmap ativo | Faltando | ✅ `docs/ROADMAP.md` shipado em audit Wave A + refresh em Cycle 3 W0 (PR #38) |
| Feature Backlog em issues | Parcial | ✅ Sub-issues #29-#32 + 13 issues audit-2026-04-22 |
| Post-mortem / lessons learned por cycle | Stale | ✅ LESSONS_LEARNED.md com Cycle 1, Cycle 2, post-tag close-arc lessons em PR #37 |

**ADR-0018 §5 entregáveis (5 docs por cycle close):**

1. ROADMAP refresh — ✅ shipou em Cycle 3 W0 (PR #38)
2. BUGS.md pruning — ✅ Cycle 2 close
3. LESSONS_LEARNED.md update — ✅ Cycle 2 close + post-tag close-arc (PR #37)
4. Catalog regen — ✅ verified by `check_stats_consistency.py` passing
5. **Audit re-run** — ✅ ESTE DOCUMENTO

**Cycle 2 fechou completo nos 5 deliverables com este audit. ADR-0018 §5
mandate cumprido.**

---

**Sumário desta camada:** 2 achados P3 (009 + 010) — ambos sobre disciplina
de issue tracking, não conteúdo. Cycle 1+2 status totalmente reconciliado.
Cycle 3 W0 plan executando. Doc-drift catálogo lista 4 itens novos (linhas
125, 323, 327 do README + arch.md/CLAUDE.md migration count + test count) que
gera AUDIT-2026-04-26-001 e -002 em [`02-architecture.md`](02-architecture.md).
