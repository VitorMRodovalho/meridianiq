<!-- Audit run: 2026-04-22 · Layer 2a -->
# Camada 2a — Arquitetura

## Estado real vs. documentado

| Dimensão | Doc (`docs/architecture.md`) | Doc (`README.md`) | Realidade (contagem) | Fonte |
|---|---|---|---|---|
| Engines analíticos | 47 + 1 export | **40 + 1 export** | **47** | `ls src/analytics/*.py \| grep -v __init__` |
| Endpoints REST | 121 | **98** | **~110 decorators** (roteadores incluem WS + paths dinâmicos; 121 inclui sub-paths) | `grep -c '@router\.' src/api/routers/*.py` |
| Routers | 23 | — | **23** | `ls src/api/routers/*.py \| grep -v __init__ \| wc -l` |
| Páginas Svelte | 54 | **52** | **54** | `find web/src/routes -name '+page.svelte' \| wc -l` |
| Migrations | 25 (um bloco diz **20**) | — | **25** | `ls supabase/migrations/*.sql` |
| Testes | 1350 | **870+** | 870+ (valor do CLAUDE.md) | `README.md` desatualizado |
| Chart components | 11 | 11 | 11 | `web/src/lib/components/charts/` |
| MCP tools | 22 | 22 | 22 | `docs/mcp-tools.md` |
| PDF report types | 15 | — (não mencionado) | 15 | CLAUDE.md |
| Versão runtime | 4.0.1 (`pyproject`), `4.0.0` (hard-coded em `app.py:23`) | — | Mismatch | `src/api/app.py:23` |

Resumo: **números centrais de produto estão defasados em 3 locais distintos**
(`README.md`, `docs/architecture.md`, `src/api/app.py:23`). Tratar como doc-drift
ritual: regenerar catálogos (`scripts/generate_*.py`) após cada wave e auto-atualizar
`README.md` via o `doc-sync-check.yml` workflow.

Detalhe técnico: `src/api/app.py:23` passa `release="meridianiq-api@4.0.0"` ao
`sentry_sdk.init` mesmo em v4.0.1 — telemetria Sentry vai rotular toda exception
como release antiga.

---

## Estilo arquitetural

**Modular monolito, bem aplicado.** Cada uma das 47 unidades em `src/analytics/` é
uma implementação standalone de uma metodologia citada (AACE RP, DCMA, SCL Protocol,
PMBOK, ANSI/EIA-748, GAO). Não há imports cruzados entre engines — orquestração
vive em `src/api/routers/`. Isto é coerente com o princípio declarado em
`docs/architecture.md` §"Design principles §1".

O `src/materializer/` (adicionado na Wave 2 do Cycle 1) é um pacote próprio que
executa engines em `ProcessPoolExecutor` com `Semaphore(1)` — ADR-0015 é a fonte
canônica. A separação entre "engine puro" e "executor assíncrono" está saudável.

## Superfície de transporte

| Transporte | Local | Observação |
|---|---|---|
| HTTP REST | `src/api/routers/*.py` (23 routers, 110 endpoints) | Todos sob `/api/v1/` |
| WebSocket | `src/api/routers/ws.py` (2 endpoints) | ADR-0013 hardening aplicado (4401/4403/4404, reaper de 15 min) |
| MCP stdio | `src/mcp_server.py` (22 tools) | Claude Desktop/Code integration |
| MCP HTTP/SSE | mesmo arquivo, flag `--transport http/sse` | ADR-0008 |

Não há endpoints gRPC ou GraphQL. Correto para o estágio do projeto.

## Documentos obsoletos

### `docs/GAP_ASSESSMENT_v3.3.md` (2026-04-07)

Foi útil ao final da v3.3 mas aponta gaps já resolvidos por W0–W6 do Cycle 1
(e.g. "CORS Exception Handler Bypass" foi removido; "Rate Limiting Not Applied"
agora é parcialmente aplicado — ver Camada 2c). **Recomenda-se mover para
`docs/archive/v3.3-planning/`** e, se desejado, gerar um novo `GAP_ASSESSMENT_v4.0.1.md`
que aproveite desta auditoria.

### `BUGS.md` header `v3.6.0-dev`

Texto é factualmente correto hoje (sem bugs abertos), mas a âncora de versão
engana o leitor novo. Corrigir header para `v4.0.1` e mover a seção "Previously
Fixed" pre-v3.0 para um `docs/archive/BUGS_HISTORY.md` — 62 linhas de backlog
histórico que ofuscam a situação atual.

### `SECURITY.md` "v3.6.x current stable"

Idem — atualizar para `v4.0.x current stable`. Política em si (3 dias ack, 7 dias
assessment, PVR preferido) é madura e não precisa mudar.

## Runtime drift

### Python version

- `pyproject.toml`: `requires-python = ">=3.12"`, tool.mypy python_version `3.14`,
  classifiers listam 3.12/3.13/3.14.
- `Dockerfile`: `FROM python:3.13-slim`.
- `CLAUDE.md`: "Dockerfile: Python 3.13-slim (pyiceberg lacks 3.14 wheel)".

Verificação: `grep -rn pyiceberg src/ tests/ pyproject.toml` retorna **zero matches**.
A justificativa citada não se aplica mais (se é que já se aplicou — `pyiceberg` nunca
entrou no `pyproject.toml`). Mover Dockerfile para `python:3.14-slim` é P3 mas
alinha o deploy com o target real do type-check.

### Node version

- `web/package.json`: `"@types/node": "^25.5.2"` (Node 25 types).
- `CLAUDE.md`: "CI: Python 3.14, Node 24".

Tipos de Node 25 em CI de Node 24 é aceitável (backwards-compatible), mas merece
uma decisão explícita: ou sobe CI para Node 25, ou desce types para `^24`.

## Branch hygiene

Branches locais presentes no clone:

```
v0.2-forensics
v0.3-claims
v0.4-controls
v0.5-risk
```

Conforme `STATUS_REPORT.md` §2, todas são **subconjunto estrito** das tags
`v0.2.0..v0.5.0` (zero commits únicos). Decisão recomendada: deletá-las localmente
via `git branch -D v0.{2,3,4,5}-*`. Não há perda — o histórico definitivo vive nas
tags anotadas. Não foram empurradas para `origin`, então a deleção é puramente
local-cleanup.

## ADR index gap

`docs/adr/README.md` lista 0000–0009, 0012–0016 — pula **0010** e **0011** sem
explicitar o status. O conteúdo "reservado" está enterrado no corpo de
`0009-cycle1-lifecycle-intelligence.md` (§"Amendment 2 — W4 outcome"). Um leitor
novo vai se perguntar se foram deletados acidentalmente.

**Ação:** adicionar linhas explícitas na tabela:

```markdown
| 0010 | (reservado) Lifecycle health engine methodology | reserved — ver ADR-0009 §W4 outcome |
| 0011 | (reservado) Fuzzy-match dep category | reserved — ver ADR-0009 §Wave A |
```

## Observações positivas (manter)

- **ADR discipline:** 15 ADRs cobrindo todas as decisões de peso (framework,
  auth, hosting, persistence, WS, materialização). MADR format aplicado.
  Imutabilidade respeitada (0007 → superseded by 0013).
- **Citação de standards em docstrings:** verificado por amostragem — AACE RP 29R-03,
  52R-06, 49R-06, 57R-09, 10S-90; DCMA EVMS; ANSI/EIA-748; GAO Schedule Assessment
  Guide; SCL Protocol. Alinhado com §"Design principles §2".
- **Self-describing:** 3 scripts geradores (`scripts/generate_*.py`) + `doc-sync-check.yml`
  workflow são o contrato. Quando usados, fecham drift automaticamente.
- **CI discipline:** 3 workflows (`ci.yml`, `doc-sync-check.yml`, `gitleaks.yml`) +
  CodeQL scheduled. Dependabot ativo (npm + GH Actions).
