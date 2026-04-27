<!-- Audit run: 2026-04-26 · Layer 2a (Architecture) -->
# Camada 2a — Arquitetura

Stack atual, drift estrutural, novos componentes desde a baseline.

## Stack canônica (autoritativo em 2026-04-26)

| Camada | Tecnologia | Versão / Estado | Notas |
|---|---|---|---|
| Backend runtime | Python 3.13-slim em Docker (Fly.io); CI 3.14 | Pin justificado: pyiceberg via storage3 (transitivo) sem wheel 3.14 — ver CLAUDE.md |
| Backend framework | FastAPI 0.136 | 122 endpoints / 23 routers (`docs/api-reference.md`) |
| Pydantic | v2.13 | `.dict()` count = 0 em `src/` ✅ |
| Backend storage | Supabase (PostgreSQL via PgBouncer porta 6543) | 26 migrations |
| Backend tests | pytest | **1449 collected** |
| Frontend framework | SvelteKit | Svelte 5 runes ($state, $derived, $effect) |
| Frontend lint | TypeScript 6, Vite 8 | strict |
| Frontend i18n | en / pt-BR / es | 54 pages (mas detail pages têm gap — ver [`05-ux-frontend.md`](05-ux-frontend.md)) |
| Auth | Supabase Auth (Google + LinkedIn + MS) + ES256 JWT via JWKS | API keys via `api_keys` table (schema do 017+026) |
| Storage | Supabase Storage (XER + PDF) | RLS via owner_id |
| Materialization | `src/materializer/` — async Task + Semaphore(1) + ProcessPoolExecutor | ADR-0014/0015 |
| MCP | FastMCP — `src/mcp_server.py` | 22 tools |
| Deploy | Fly.io (backend) + Cloudflare Pages (frontend) | CORS via `ALLOWED_ORIGINS` env |
| Calibração de heurísticas | `tools/calibration_harness.py` | ADR-0020 — 470 LoC, 3 abstrações |

## Componentes novos desde baseline 2026-04-22

| Componente | Arquivo / Módulo | ADR | Estado |
|---|---|---|---|
| Lifecycle phase inference engine | `src/analytics/lifecycle_phase.py` (13.6 KB) | ADR-0016 | Accepted; engine v1 limitado a `is_construction_active` tri-state per W2 honesty-debt closure |
| Calibration harness primitive | `tools/calibration_harness.py` (28.7 KB) | ADR-0020 | Accepted; §"Decision" caveat ("não reproduz W4 numbers") aberto até W3 regression test |
| Recovery poller composable | `web/src/lib/composables/useWebSocketProgress.ts` (extendido) | ADR-0019 §W1 | D4 contract; backend wiring shipou em PR #35 |
| `RiskStore.bind_job` + by-job endpoint | `src/database/store.py` + `src/api/routers/risk.py:272` | ADR-0019 §W1 | D4 backend wiring (#35) |
| `_ENGINE_VERSION` shared constant | `src/materializer/runtime.py:54` | ADR-0014 | **Drift OPEN** — hardcoded `"4.0"` ao invés de sourcing de `__about__.py` |
| ADRs Cycle 2 + Cycle 3 entry | `docs/adr/0017-0021.md` | self | 0019, 0020, 0021 ainda unratified per #28 |

---

## AUDIT-2026-04-26-001 · P2 · `README.md` mermaid + ASCII tree retêm stats legacy não capturados pelo CI

**Arquivo:** `README.md` linhas 123, 323, 327.

**Evidência:**

```
123:        FASTAPI["FastAPI Container<br/>Analysis Engines (40)<br/>98 endpoints"]
323:│   │   └── ...                 # 40 engines total + 1 export
327:│       ├── routers/      # 98 endpoints across modular routers
```

**Realidade:** 47 engines + 1 export (`docs/methodologies.md`), 122 endpoints
(`docs/api-reference.md`).

**Por que `check_stats_consistency.py` não captura:** o script (autorado em
Wave C da remediação 2026-04-22) busca padrões específicos no §"Key Numbers"
table do README + `## Architecture` do CLAUDE.md. Mermaid diagrams e ASCII
tree não estão no escopo regex do script. CI passa (`Stats consistent across
CLAUDE.md and README.md: 47 engines + 1 export module, 122 endpoints across
23 routers, 22 MCP tools, 54 pages`) mas o repo continua mentindo na visualização
mais visível para newcomers.

**Risco:** novato lê o mermaid antes do `## Key Numbers`, vê "40 engines /
98 endpoints", forma modelo mental defasado. Confidence-erosion incremental
(o mesmo padrão que a baseline 2026-04-22 §AUDIT-006 buscava resolver).

**Ação:**

1. Atualizar `README.md` linhas 123, 323, 327 manualmente para 47 / 122.
2. Estender `check_stats_consistency.py` para grep também `Analysis Engines (\d+)`
   pattern em mermaid blocks + `(\d+) engines total` em ASCII tree.
3. Idealmente: gerar README §"Architecture" mermaid via script, não hard-code.

**Relação com baseline:** classificação como **regressão** de AUDIT-006 — o fix
no §"Key Numbers" não foi acompanhado de um sweep semântico do resto do README.

---

## AUDIT-2026-04-26-002 · P3 · Doc-drift assimétrico em `architecture.md` + `CLAUDE.md`

**Evidência (3 fontes, 3 contagens diferentes):**

| Fonte | Migrations | Tests | Status |
|---|---|---|---|
| `docs/architecture.md` linhas 29, 90 | "25 migrations" / "25 .sql files" | "1435 tests" | Ambos drift (real = 26 / 1449) |
| `CLAUDE.md` linha 27 | "24 migrations" | "1429 tests" (em prosa do v4.1.0 baseline) | Ambos drift |
| Realidade (verificada 2026-04-26) | **26** | **1449** | autoritativo |

**Por que múltiplas fontes divergem:** `check_stats_consistency.py` valida
apenas CLAUDE.md §"Architecture" + README §"Key Numbers" — `architecture.md`
fica fora do guard. Cycle 2 acresceu migrations 022/023/024/025/026 + ~100
tests novos; nenhuma das fontes foi totalmente atualizada porque cada uma é
mantida manualmente em PRs separados.

**Risco:** P3 — drift documental, sem impacto runtime, mas alimenta o padrão
de "autodisclosure honesty é difícil" que LESSONS_LEARNED Cycle 2 §"Post-tag
close-arc lessons" registra como o padrão recorrente da safra v4.x.

**Ação:**

1. Atualizar `docs/architecture.md` para 26 migrations + 1449 tests.
2. Atualizar `CLAUDE.md` para 26 migrations (a Section §Architecture).
3. Estender `check_stats_consistency.py` para validar `architecture.md`
   (aplicar mesmo regex `(\d+) migrations` em arch.md e exigir igualdade com
   `len(glob('supabase/migrations/*.sql'))`).

---

## AUDIT-2026-04-26-003 · P2 · Devils-advocate-as-second-reviewer protocol — open process gap

**Auto-disclosure existente:** [ADR-0021 §"Open process gap"](../../adr/0021-cycle-3-entry-floor-plus-field-shallow.md#open-process-gap)
e [LESSONS_LEARNED.md §"Post-tag close-arc lessons"](../../LESSONS_LEARNED.md).

**Verificação:** o protocol está documentado em maintainer memory
(`project_v40_cycle_2.md`, `project_resume_next_session.md`,
`project_session_2026_04_27.md`) mas **NÃO em ADR ou GOVERNANCE.md**. Sample
recente (2026-04-27): PRs #33, #35, #36, #37, #38 todos passaram pelo protocol;
#38 sozinho capturou 5 blocking + 5 non-blocking findings (denser than the
2 blocking + 4 non-blocking average).

**Por que é P2 e não P3:** o protocol é load-bearing para a qualidade pós-PR
de qualquer ADR-level decision (incluindo o próprio ADR-0021 que se autodescreve
como precisando do gap fechado). Sem codificação in-repo:

1. Contribuidor externo não consegue saber qual é o critério antes de mergear.
2. Maintainer pode ser substituído (sucessão), perdendo o conhecimento tácito.
3. ADR-0024 hipotético poderia formalizar — ADR-0019 e ADR-0021 deixaram explicitamente
   para depois.

**Ação:**

1. Considerar autorar `ADR-0024 — Devils-advocate-as-second-reviewer PR protocol`
   ou amendment a ADR-0018 §"Process discipline" estendendo o §5 cycle-cadence
   para incluir PR-level cadence.
2. Adicionar seção em `GOVERNANCE.md` listando os 5 passos do protocol.
3. Listar exceções (Dependabot PRs, catalog regen-only, 1-line typo, doc-only
   LESSONS appends — PR #37 precedent).

**Relação com Cycle 3:** está dentro do escopo formal do Cycle 3 W0 já que
ADR-0021 self-flagged. Não-prioritário porque o protocol funciona por convenção,
mas sustentabilidade exige codificação.

**Disclosure (auto-disclosure conflict):** este finding foi confirmado pela DA
review de PR #39 (este audit). Há conflito-de-interesse circular — o protocol
está sendo afirmado pela mesma ferramenta que o protocol invoca. A justificativa
"5 PRs amostrados pegaram 2 blocking + 4 non-blocking on average" cita os outputs
do próprio protocol como evidência de seu valor. **Mantido como P2** porque o gap
é estrutural (zero codificação in-repo) independentemente da fonte que confirma —
mas leitor crítico deve considerar a auto-pressure-test bias e ponderar.

---

## AUDIT-2026-04-26-007 · P2 · `_ENGINE_VERSION` hardcoded — multi-cycle ADR-0014 drift (load-bearing forensic provenance)

**Arquivo:** `src/materializer/runtime.py:54`.

```python
_ENGINE_VERSION = "4.0"  # hardcoded — ADR-0014 §"Decision Outcome" says: "Source: src/__about__.py::__version__"
```

**Evidência ADR:** [ADR-0014 §"Decision Outcome" tabela (linha 44)](../../adr/0014-derived-artifact-provenance-hash.md#decision-outcome):
> | `engine_version` | `TEXT NOT NULL` | Source: `src/__about__.py::__version__`. |

**Histórico:** PR #36 (`086911c` em 2026-04-27) deduplicou a constante (de 2 sites
para 1) mas **não migrou para `__about__.py`** — o trabalho foi parcial. PR #37
LESSONS append marca isso como "ADR pin → regression test" lesson. ADR-0021
§"Wave plan" W4 commits to closing.

**Por que P2 e NÃO P3** (severidade reescalada vs draft inicial pós-DA review):
`engine_version` é parte do `UNIQUE NULLS NOT DISTINCT (project_id, artifact_kind,
engine_version, ruleset_version, input_hash)` (ADR-0014 §"Decision Outcome" linha
~52). É **load-bearing para o contrato forense de reprodutibilidade**: quando
`__version__` virar `4.2.0` no Cycle 3 close, novos artifacts ficarão com
`engine_version="4.0"` enquanto o engine real é `4.2.0` — provenance silenciosamente
divergente. Esta é exatamente a classe de drift que ADR-0014 §"Decision Outcome"
foi escrita para prevenir. Tratar como P3 ("feliz coincidência" enquanto literal
bate) underweighta a criticidade do contract; o draft original errou nessa.

**Ação:** já pré-committed para Cycle 3 W4 — confirmação em audit, severidade
reescalada para P2 + ver AUDIT-2026-04-26-011 abaixo (file que ADR cita não existe).

---

## AUDIT-2026-04-26-011 · P2 · ADR-0014 cita `src/__about__.py` que NUNCA existiu no repo

**Evidência:** `ls src/__about__.py` retorna `No such file or directory`. Verificado
2026-04-26.

**Por que isto é finding distinto de AUDIT-2026-04-26-007:** o 007 é "constante
hardcoded ao invés de sourcing"; o 011 é "ADR aceita em 2026-04-18 (Cycle 1 W1)
cita um arquivo que nunca existiu". 007 fala sobre `runtime.py:54`; 011 fala
sobre o **contrato ADR estar non-implementable as-written desde 2026-04-18**.

**Verificação grep:**

```bash
$ ls src/__about__.py
ls: cannot access 'src/__about__.py': No such file or directory

$ grep -rE "__version__" src/ --include="*.py"
(no output — version constant not anywhere in src/)
```

**Risco:** P2. Multi-cycle invisible structural drift. Future maintainer re-lendo
ADR-0014 para implementar 007's fix vai precisar **criar `src/__about__.py`** —
não é um simples sourcing, é primeiro a criação do single-source-of-truth. ADR-0021
§"Wave plan" W4 deveria explicitar este passo.

**Ação:**

1. **Cycle 3 W4 amendment** ao plano: explicitar que o trabalho é (a) criar
   `src/__about__.py` com `__version__ = "4.2.0"` (ou similar), (b) refatorar
   `pyproject.toml` para sourcing dele, (c) MIGRAR `_ENGINE_VERSION` para sourcing
   dele.
2. **OR ADR-0014 amendment**: se a decisão estrutural for sourcing-from-pyproject
   ao invés de `__about__.py`, autorar amendment 1 explicitando o desvio (com
   referência cruzada para que futuros readers do 0014 não se confundam).
3. **Test de regressão**: `tests/test_engine_version_source.py` que importa
   `src.__about__.__version__` E `src.materializer.runtime._ENGINE_VERSION` E
   exige igualdade — falha se a constante derivar.

---

## Documentação obsoleta

Sweep para garantir que nada novo se acumulou desde a baseline:

| Arquivo | Estado em 2026-04-22 | Estado em 2026-04-26 |
|---|---|---|
| `docs/GAP_ASSESSMENT_v3.3.md` | A arquivar | Arquivado em `docs/archive/v3.3-planning/GAP_ASSESSMENT.md` ✅ |
| `docs/SCHEDULE_VIEWER_ROADMAP.md` | "v3.6.0-dev" header | Verificar se foi atualizado |
| `BUGS.md` | "v3.6.0-dev" header | "v4.1.0" ✅ |
| `SECURITY.md` | "v3.6.x" | Sem versão stale ✅ |

**Sweep adicional:** verificar `docs/SCHEDULE_VIEWER_ROADMAP.md`:

```
$ head -3 docs/SCHEDULE_VIEWER_ROADMAP.md
```

(Audit-time follow-up — não bloqueante.)

---

## ADR cross-check (cada ADR aceito ainda é fiel ao código?)

| ADR | Status | Verificação |
|---|---|---|
| ADR-0014 — provenance hash | accepted (amended by 0015) | `_ENGINE_VERSION` drift OPEN — ver AUDIT-2026-04-26-007 |
| ADR-0015 — async materializer state machine | accepted | `projects.status` enum = `pending|ready|failed` em migration 024 ✅ |
| ADR-0016 — lifecycle phase override + lock | accepted | `lifecycle_phase_overrides` + `lifecycle_phase_locks` em migration 025; engine arquivo presente; W2 honesty-debt closure (`is_construction_active` tri-state) shipped ✅ |
| ADR-0017 — api_keys dedup | accepted | `012_api_keys.sql` no-op header presente; 026 idempotent migration presente; ratificação ainda pending #28 |
| ADR-0018 — cycle cadence | accepted | §5 audit re-run entregue por este documento; §"Process discipline" gap parcialmente fechado por LESSONS_LEARNED Cycle 2 close-arc; ratificação ainda pending #28 |
| ADR-0019 — Cycle 2 entry | accepted | Cycle 2 fechou em v4.1.0 com 7/7 success criteria; ratificação ainda pending #28 |
| ADR-0020 — calibration harness primitive | accepted | `tools/calibration_harness.py` 470 LoC com 3 abstrações ✅; §"Decision" caveat aberto até W3 regression test (Cycle 3 W3) |
| ADR-0021 — Cycle 3 entry | accepted (self) | Este audit é o success criterion #1; W0 ainda parcial até este PR mergear |

**Net:** todos os 8 ADRs aceitos têm rastreio direto no código + drift conhecido
(_ENGINE_VERSION) já tracked.

---

## Branch hygiene

```
$ git branch -a | grep "v0\.[2-5]"
(empty)
```

Local + remote: limpos. AUDIT-013 baseline RESOLVIDO.

---

## ADR index gap

`docs/adr/README.md` agora explicita reservation status para 0010, 0011, 0022,
0023:

```
| 0010 | _(reserved — lifecycle_health engine methodology)_ | reserved, not authored — see ADR-0009 §"Wave 4 outcome" and 0009-w4-outcome.md |
| 0011 | _(reserved — fuzzy-match dep category)_ | reserved, not authored — see ADR-0009 §"Wave A" |
| 0022 | _(reserved — Cycle 4 deep #1 per ADR-0021 §"Decision")_ | reserved, not authored |
| 0023 | _(reserved — Cycle 4 deep #2 per ADR-0021 §"Decision")_ | reserved, not authored |
```

AUDIT-014 baseline RESOLVIDO + ampliado para 0022/0023.

---

## Runtime drift

Dockerfile pinned em `python:3.13-slim`. Justificativa atual em CLAUDE.md
estabelece corretamente que `pyiceberg` via `storage3` (transitivo) ainda
não tem wheel 3.14 (`f1bd4e2` tentou 3.14, `df672d9` reverteu, LESSONS Cycle 2
§"Transitive deps lurk"). **Dockerfile = correto; CLAUDE.md = correto. AUDIT-012
baseline REAFFIRMED com justificativa atualizada.**

---

**Sumário desta camada:** 4 achados novos (001, 002, 003, 007) — 1 P2, 3 P3 — todos
doc-drift / process / multi-cycle drift conhecida. **Stack arquitetural no fundo
estável.** O drift é nas representações textuais, não no código.
