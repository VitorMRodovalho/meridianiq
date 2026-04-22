<!-- Audit run: 2026-04-22 · Base: v4.0.1 (commit 4abd682) -->
# MeridianIQ — Auditoria Estrutural 2026-04-22

Este diretório registra a auditoria completa do repositório feita em **2026-04-22** sobre a
base **v4.0.1** (HEAD `4abd682`), cobrindo arquitetura, schema, aplicação web, segurança,
UX e o delta entre "planejado" e "implementado". Cada camada abaixo é um documento
autocontido — ler em ordem para a leitura completa, ou ir direto ao domínio de interesse.

## Camadas

| Camada | Documento | Público | Objetivo |
|---|---|---|---|
| **0 — Index** | `README.md` (este) | Todos | Navegação + metodologia + matriz consolidada |
| **1 — Crítico (P0/P1)** | [`01-critical-findings.md`](01-critical-findings.md) | Dev lead, mantenedor | Issues bloqueantes com evidência citada e fix sugerido |
| **2a — Arquitetura** | [`02-architecture.md`](02-architecture.md) | Eng. backend | Stack real vs documentado, drift, descobertas de modularidade |
| **2b — Schema** | [`03-schema.md`](03-schema.md) | Eng. backend, DBA | Cobertura RLS, duplicação de migrations, indexação, FK/cascade |
| **2c — Segurança** | [`04-security.md`](04-security.md) | Security eng. | Rate-limit, auth fallbacks, CORS, env hygiene, LGPD/GDPR |
| **2d — UX / Frontend** | [`05-ux-frontend.md`](05-ux-frontend.md) | Eng. frontend, design | i18n, a11y, dark mode, páginas órfãs |
| **2e — Planejado vs. Implementado** | [`06-planned-vs-implemented.md`](06-planned-vs-implemented.md) | Product, tech lead | Roadmap vs. código; features deferidas; doc-drift |
| **3 — Handoff** | [`HANDOFF.md`](HANDOFF.md) | Todo o time | Ações humanas pendentes (prod apply, revisão de ADR, decisões de produto) |

Issues do GitHub rotuladas com `audit-2026-04-22` apontam cada item acionável de volta
para uma seção de um destes documentos. Itens que exigem sign-off do time carregam
também o label `requires-human-decision` e — quando aplicável — `ops`.

## Metodologia

1. **Recon estático**: leitura de `CLAUDE.md`, `README.md`, `BUGS.md`, `STATUS_REPORT.md`,
   `SECURITY.md`, `PRIVACY.md`, `GOVERNANCE.md`, `docs/architecture.md`, `docs/adr/*`,
   `docs/GAP_ASSESSMENT_v3.3.md`, `docs/SCHEDULE_VIEWER_ROADMAP.md`, `pyproject.toml`,
   `web/package.json`, `fly.toml`, `docker-compose.yml`, `Dockerfile`, `.env.example`.
2. **Inventário por contagem**: routers (23), endpoints (110 decoradores vs 121 doc),
   engines (47), migrations (25), rotas web (54), tags (18), issues abertas (3),
   PRs abertos (2), ADRs (15 arquivos; gaps 0010/0011 intencionais).
3. **Verificação ativa** via grep direcionado:
   - `@limiter.limit` por router (matriz de cobertura).
   - `ENABLE ROW LEVEL SECURITY` e `CREATE POLICY` por migration.
   - `$:` legado Svelte 4 (= 0 — Svelte 5 runes 100%).
   - `$t(` por página (cobertura i18n).
   - `chart.js` (0 refs — dead-dep já removida).
   - `defusedxml` (presente em `msp_reader.py` — XXE/DTD fechados).
4. **Cross-check de consistência** entre: CLAUDE.md, README.md, `docs/architecture.md`,
   e código. Toda divergência vira item "doc-drift" em [06](06-planned-vs-implemented.md).
5. **Cruzamento com ADRs**: cada decisão arquitetural de peso foi checada contra código
   atual para validar se continua em vigor ou foi silenciosamente superada.

## Matriz consolidada de severidade

| ID | Camada | Severidade | Título | Docs |
|----|----|----|----|----|
| AUDIT-001 | Schema | **P0** | Migrations 012 e 017 definem a tabela `api_keys` com schemas divergentes | [03](03-schema.md#migrations-duplicadas-api_keys) |
| AUDIT-002 | Security | **P1** | `validate_api_key` cai silenciosamente em dict in-memory quando Supabase falha | [04](04-security.md#api-key-fallback-silencioso) |
| AUDIT-003 | Security | **P1** | Rate-limit ausente em routers compute-heavy (risk/forensics/analysis/reports/exports) | [04](04-security.md#rate-limit-gap) |
| AUDIT-004 | Security | **P1** | CORS origins hard-coded em `src/api/app.py` — sem env override | [04](04-security.md#cors-hardcoded) |
| AUDIT-005 | Security | **P2** | `.env.example` omite variáveis obrigatórias (`SUPABASE_JWT_SECRET`, `SENTRY_DSN`, `ANTHROPIC_API_KEY`, `FLY_API_TOKEN`, `ENVIRONMENT` etc.) | [04](04-security.md#env-example-incompleto) |
| AUDIT-006 | Docs | **P2** | `README.md` lista números estruturais defasados (40 engines / 98 endpoints / 52 pages / 870 tests vs. 47 / 121 / 54 / 1350) | [06](06-planned-vs-implemented.md#doc-drift) |
| AUDIT-007 | Docs | **P2** | `BUGS.md` header "v3.6.0-dev" + `SECURITY.md` "v3.6.x current stable" contra `v4.0.1` em produção | [06](06-planned-vs-implemented.md#doc-drift) |
| AUDIT-008 | Docs | **P2** | `CLAUDE.md` afirma "no web/Dockerfile yet" — arquivo existe desde v0.9.0 (BUG-011 fechado) | [06](06-planned-vs-implemented.md#doc-drift) |
| AUDIT-009 | Docs | **P3** | `docs/architecture.md` diz "20 .sql files" em um bloco e "25 migrations" em outro | [06](06-planned-vs-implemented.md#doc-drift) |
| AUDIT-010 | UX | **P2** | 15 páginas têm ≤ 4 chamadas `$t(…)` (i18n mínima) enquanto 10+ já estão >20 | [05](05-ux-frontend.md#i18n-coverage) |
| AUDIT-011 | Arch | **P2** | `docs/GAP_ASSESSMENT_v3.3.md` desatualizado (data 2026-04-07, antes de W0–W6); precisa ser arquivado ou re-rodado | [02](02-architecture.md#documentos-obsoletos) |
| AUDIT-012 | Arch | **P3** | Dockerfile pinned em Python 3.13 — justificativa (pyiceberg) não se aplica mais (dep não está em `pyproject.toml`) | [02](02-architecture.md#runtime-drift) |
| AUDIT-013 | Arch | **P3** | Branches locais `v0.2-forensics`..`v0.5-risk` são subconjuntos estritos das tags v0.x e podem ser podadas | [02](02-architecture.md#branch-hygiene) |
| AUDIT-014 | Arch | **P3** | ADR README não registra explicitamente o status "reservado, não usado" de 0010 e 0011 | [02](02-architecture.md#adr-index-gap) |
| AUDIT-015 | Planned | **P2** | Backlog "Wave 7 — Resource & Cost Integration" (Schedule Viewer Roadmap) não tem rastreio em issues | [06](06-planned-vs-implemented.md#backlog-sem-issue) |
| AUDIT-016 | Planned | **P3** | Issue #8 (17 TypeScript errors) aberta desde 2026-03-29 — sem commits de progresso citados | [06](06-planned-vs-implemented.md#backlog-sem-issue) |
| AUDIT-017 | Planned | **P3** | Issue #14 (optimizer page field mismatch, pre-existente a v4.0.0) aberta desde 2026-04-19 e não foi incluída em nenhum wave explícito | [06](06-planned-vs-implemented.md#backlog-sem-issue) |
| AUDIT-018 | Security | **P3** | Dependabot PR #11 (upload-artifact v6→v7) + #15 (frontend minor-patch group) abertos com CI verde | [04](04-security.md#dependabot-aberto) |

**P0 = perda de integridade / bloqueio de produção; P1 = mitigar ≤ 30 dias; P2 = mitigar ≤ 90 dias; P3 = higiene contínua.**

## Escopo NÃO coberto

Esta rodada não inclui:

- Teste de carga / performance sob tráfego real.
- Varredura SAST/DAST (o repo já tem `gitleaks.yml` e CodeQL agendado — ver `.github/workflows/`).
- Revisão linha-a-linha dos 47 engines quanto a correção metodológica
  (estas já são validadas por 1.350 testes e pelas citações de standard em docstrings).
- Revisão de contratos legais (LGPD/GDPR/LICENSE) — há hypothesis gaps em
  [04](04-security.md), mas parecer jurídico binding é fora de escopo.

## Quando re-rodar

- Sempre ao fechar um **cycle** (hoje: ao final do Cycle 2, sucessor ao Cycle 1 v4.0).
- Antes de qualquer release rotulada `vX.0.0` (major).
- Ao integrar primeiro contribuidor externo não-mantenedor (para normalizar doc-drift
  antes do handoff).

— Gerado automaticamente; registrar qualquer revisão futura como novo subdiretório
`docs/audit/YYYY-MM-DD/`.
