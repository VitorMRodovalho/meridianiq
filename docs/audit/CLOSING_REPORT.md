<!-- Session closure · generated 2026-04-22 -->
# Audit 2026-04-22 — Closing Report

Este é o artefato de **encerramento de sessão** da auditoria estrutural de
2026-04-22. Escrito para ser lido em 2 minutos por qualquer pessoa do time
(dev, product, ops, stakeholder) que queira saber "o que aconteceu, o que
mudou, o que ainda falta".

Para o detalhe técnico por domínio, ler os 7 docs da auditoria em ordem —
índice em [`README.md`](README.md).

---

## Em uma frase

Fizemos uma auditoria estrutural de 6 camadas sobre o `main` em `v4.0.1`,
identificamos 18 achados (1 P0, 3 P1, 8 P2, 6 P3), shipamos correções
automáticas para 7 deles em 6 commits, e registramos 8 ações de handoff
que exigem sign-off humano antes de fechar — todas com issue GitHub e
checklist operacional.

## Números

| Métrica | Valor |
|---|---|
| Commits na sessão | 8 |
| Linhas adicionadas | 2.265 |
| Linhas removidas | 96 |
| Arquivos tocados | 32 |
| Novos testes de regressão | 19 (4 CORS + 7 api_key fail-closed + 8 migration schema) |
| Suíte final de testes | **1.337 passed, 5 skipped, 0 failed** |
| ADRs autorados | 2 (0017, 0018) |
| Migrations de schema | 1 nova (026) + 1 convertida em no-op (012) |
| Docs de auditoria | 8 (6 camadas + handoff + este report) |
| Issues GitHub abertas pela auditoria | 13 (#16–#28) |
| Issues já fechadas | 6 (#16–#21) |
| Labels criadas | 11 (audit-2026-04-22 + 4 priority + 5 area + 2 requires-human/ops) |
| Issues com `requires-human-decision` | 3 (#26 P0 ops, #27 P2, #28 P2) |

## Timeline (ordem de execução)

1. **Recon** — leitura de CLAUDE.md, README.md, BUGS.md, STATUS_REPORT.md,
   SECURITY.md, docs/architecture.md, docs/adr/*, configs (pyproject,
   fly.toml, docker-compose, Dockerfile, .env.example).
2. **Verificação ativa** — grep direcionado de `@limiter.limit`, RLS por
   migration, `$:` legado Svelte 4 (= 0), `$t(` por página, chart.js refs
   (= 0), defusedxml, duplicate tables.
3. **Entrega camada 0–2** (commit `9b15f6a`) — `docs/audit/{README,01-06}.md`.
4. **Criação de labels + issues** (10 issues iniciais: `#16`–`#25`).
5. **Wave A** (commit `a97be36`) — docs hygiene + ADR-0017 + ADR-0018 +
   .env.example + app.py release via importlib.metadata + archival.
6. **Wave B1** (commit `93809e9`) — CORS `ALLOWED_ORIGINS` env + 4 testes.
7. **Wave B2** (commit `8faf002`) — rate limits em risk/forensics/reports/
   exports + constantes `RATE_LIMIT_*` em deps.py.
8. **Wave B3** (commit `06fa945`) — api_key fail-closed em produção + 7
   testes de regressão.
9. **Wave B4** (commit `cd3b907`) — migration 012 no-op + migration 026
   idempotente + 8 testes estáticos.
10. **Wave C** (commit `4a255ee`) — extensão do
    `check_stats_consistency.py` para cobrir `README.md §Key Numbers` +
    atualização do workflow doc-sync-check.yml.
11. **Fechamento de issues** — #16, #17, #18, #19, #20, #21 closed.
12. **Handoff humano** (commit `1e7a2b3`) — `docs/audit/HANDOFF.md`
    (Layer 3) + 3 issues novas (`#26`–`#28`) com label
    `requires-human-decision`.
13. **Exit** (este commit) — `CLOSING_REPORT.md` + CHANGELOG.md
    Unreleased + pointer em README.md.

## O que mudou no produto

### Correções de segurança com impacto runtime

- **CORS** configurável via `ALLOWED_ORIGINS` — forks, previews e review
  apps deixam de exigir code-change.
- **Rate limits** em endpoints compute-heavy (Monte Carlo, MIPs forensic,
  WeasyPrint PDF, XER/Excel export) — um único ator hostil não derruba mais
  o VM Fly.io.
- **API key lookup fail-closed em produção** — HTTP 503 distinto de "key
  inválida", Supabase vira sole-source-of-truth, dict in-memory confinado a
  `ENVIRONMENT != "production"`.

### Correções de schema

- **Migration 012 e 017 desambiguadas** via ADR-0017. 012 virou no-op,
  026 reconcilia qualquer instância legada de forma idempotente. Nenhum
  histórico reescrito. (Aplicação em produção ainda pendente — ver #26.)

### Governança e CI

- **ADR-0018** formaliza 5 artefatos de cycle-close (ROADMAP, BUGS pruning,
  LESSONS, catalog regen, audit re-run).
- **`check_stats_consistency.py`** agora valida README.md além de CLAUDE.md
  → drift de números em releases bloqueia CI automaticamente.
- **Labels** `requires-human-decision` e `ops` criadas para itens que
  nunca podem ser fechados por automação.

### Correções de documentação

- `README.md`, `CLAUDE.md`, `docs/architecture.md`, `SECURITY.md`, `BUGS.md`
  todos alinhados a `v4.0.1` + números reais (47 engines / 121 endpoints /
  54 páginas / 1337 testes).
- `docs/GAP_ASSESSMENT_v3.3.md` arquivado em `docs/archive/v3.3-planning/`.
- ADR index explicita o status "reservado" de 0010 e 0011.
- `.env.example` completo (SUPABASE_JWT_SECRET, ALLOWED_ORIGINS, SENTRY_DSN,
  ANTHROPIC_API_KEY, PUBLIC_POSTHOG_KEY, PORT, FLY_API_TOKEN).

## O que NÃO mudou (deliberadamente)

- Engines analíticos (`src/analytics/*.py`) — fora do escopo da auditoria
  estrutural; já validados por 1.337 testes e citação de standards.
- Rotas web individuais — não tocadas além do roadmap Wave 7.
- Fluxos de auth OAuth (Google / LinkedIn / Microsoft) — só o api_key path
  foi endurecido; JWT verification (ADR-0005 ES256 + JWKS) permaneceu igual.
- Dockerfile Python 3.13 — bump para 3.14 é P3 (ver #24).
- Branches `v0.{2,3,4,5}-*` locais — são subsets estritos de tags e não
  afetam o remoto; cleanup só local, à critério do mantenedor (#24).

## Backlog pós-exit

### Humano (bloqueadores para "fim de verdade")

| # | Severidade | Ação | Prazo alvo |
|---|---|---|---|
| [`#26`](https://github.com/VitorMRodovalho/meridianiq/issues/26) | **P0 ops** | Aplicar migration 026 em produção Supabase | ≤ 7 dias |
| [`#27`](https://github.com/VitorMRodovalho/meridianiq/issues/27) | P2 | Autorar `docs/ROADMAP.md` no kickoff Cycle 2 | Kickoff Cycle 2 |
| [`#28`](https://github.com/VitorMRodovalho/meridianiq/issues/28) | P2 | Ratificar ADR-0017 e ADR-0018 pelo time | Antes de Cycle 2 |

Procedimento de cada uma em [`HANDOFF.md`](HANDOFF.md).

### Escopo de próximos cycles (não-bloqueadores)

| # | Severidade | Item |
|---|---|---|
| [`#22`](https://github.com/VitorMRodovalho/meridianiq/issues/22) | P2 | i18n em 15 páginas (~5 sprints a 3 páginas/sprint) |
| [`#23`](https://github.com/VitorMRodovalho/meridianiq/issues/23) | P2 | Wave 7 — Resource + Cost Integration no Gantt |
| [`#24`](https://github.com/VitorMRodovalho/meridianiq/issues/24) | P3 | Housekeeping residual (Dockerfile, dependabot weekly, stale branches) |
| [`#8`](https://github.com/VitorMRodovalho/meridianiq/issues/8) | — | 17 TS errors em 7 arquivos (pré-existente) |
| [`#13`](https://github.com/VitorMRodovalho/meridianiq/issues/13) | — | Calibration dataset contributions (ADR-0009 W4 outcome) |
| [`#14`](https://github.com/VitorMRodovalho/meridianiq/issues/14) | — | `/optimizer` page field mismatch (pré-existente) |

## Onde tudo vive (índice único)

| O que | Onde |
|---|---|
| Auditoria completa | [`docs/audit/`](.) |
| ADRs (inclui 0017, 0018) | [`docs/adr/`](../adr/) |
| Migrations (inclui 012 no-op, 026 align) | [`supabase/migrations/`](../../supabase/migrations/) |
| Testes novos (19) | [`tests/test_cors_config.py`](../../tests/test_cors_config.py), [`test_api_keys_fail_closed.py`](../../tests/test_api_keys_fail_closed.py), [`test_api_keys_schema.py`](../../tests/test_api_keys_schema.py) |
| Issues abertas | [label `audit-2026-04-22`](https://github.com/VitorMRodovalho/meridianiq/issues?q=label%3Aaudit-2026-04-22) |
| Issues de sign-off humano | [label `requires-human-decision`](https://github.com/VitorMRodovalho/meridianiq/issues?q=label%3Arequires-human-decision) |
| Release notes | [`CHANGELOG.md`](../../CHANGELOG.md) (seção `Unreleased`) |
| Meta-tracking | Issue [`#25`](https://github.com/VitorMRodovalho/meridianiq/issues/25) |

## Canais usados, canais considerados

- **GitHub (core)** — único canal oficial do projeto. Usado: issues, PRs,
  labels, workflow files, CHANGELOG, docs em `docs/audit/`. Cobertura: 100%
  do que a automação pode shipar.
- **GitHub Discussions** — **desabilitado** no repo. Recomenda-se habilitar
  (Settings → General → Features) para releases/broadcast comunitário; fora
  do escopo desta sessão porque muda config do repo.
- **Sentry / PostHog / Slack** — não tocados; sem mudança de config
  observada nesta auditoria.
- **Notion / docs externos** — projeto é solo-maintainer. Caso o time cresça,
  recomenda-se espelhar `docs/audit/CLOSING_REPORT.md` e `HANDOFF.md` em
  um Notion compartilhado. Não feito aqui por ausência de database-alvo.

## Critério de "exit" desta sessão

Considerar encerrada quando:

- [x] Todos os achados documentados em camadas apropriadas.
- [x] Toda correção automatizável shipada em `main` com testes verdes.
- [x] Todas as ações humanas rastreadas em issues com label
      `requires-human-decision`.
- [x] CHANGELOG.md Unreleased reflete o que mudou.
- [x] README.md aponta para `docs/audit/`.
- [x] Meta-issue #25 comentada com links + status.
- [ ] **(humano) Issue #26 fechada** após apply de 026 em produção.
- [ ] **(humano) Issue #28 fechada** após ratificação de ADRs.

Os 6 primeiros checkboxes estão marcados. Os 2 últimos são pré-requisito
para considerar esta auditoria **totalmente** encerrada; esta sessão entrega
até o limite do que a automação pode fazer sem sign-off humano.

## Ponto de retomada

Qualquer agente ou humano retomando este trabalho deve começar por:

1. Ler este `CLOSING_REPORT.md` (este documento).
2. Abrir `docs/audit/HANDOFF.md` para o checklist operacional das 8 ações
   humanas.
3. Triar a fila de issues por label `requires-human-decision` (3 itens).
4. Não remover labels, comentários, ou ADRs desta rodada sem autorização —
   são evidência histórica imutável.

Fim da sessão de auditoria 2026-04-22.
