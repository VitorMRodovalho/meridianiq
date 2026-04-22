<!-- Audit run: 2026-04-22 · Layer 2d -->
# Camada 2d — UX & Frontend

## Inventário

- **54 páginas** (`+page.svelte`) em `web/src/routes/`.
- **11 chart components** em `web/src/lib/components/charts/` (BarChart, PieChart,
  GaugeChart, ScatterChart, WaterfallChart, TimelineChart, ResourceChart, HeatMapChart,
  ParetoChart, GanttChart, EVMSCurveChart) — todos SVG hand-crafted, **zero** refs
  a `chart.js` no repo (confirmado).
- **Svelte 5 runes**: `grep '\$:' web/src/{routes,lib}` → **0 matches**. Migração
  para runes (`$state`, `$derived`, `$effect`) é **completa**.
- **ScheduleViewer** em `web/src/lib/components/ScheduleViewer/` — documentado em
  `docs/SCHEDULE_VIEWER_ROADMAP.md`, Waves 1-6 + parte da 8 entregues, Wave 7
  (resource & cost integration) é o maior gap de feature aberto.

## i18n coverage

Método: `grep -c '\$t(' web/src/routes/<slug>/+page.svelte`.

### Bem internacionalizadas (≥ 20 chamadas)

```
compare           82
milestones        63
risk-register     43
trends            34
recovery          33
ips               31
contract          30
builder           26
projects          26
forensic          25
cost              24
pareto            23
demo              22
settings          23
```

### Pouco/quase nada (≤ 4 chamadas)

```
float-trends       1
tia                1
alerts             2
anomalies          2
benchmarks         2
cashflow           2
delay-attribution  2
delay-prediction   2
duration-prediction 2
optimizer          2
reports            2
resources          2
root-cause         2
schedule           2
whatif             2
```

**15 páginas com i18n próximo a zero, 14 páginas com i18n robusto.** Gap simétrico
sugere que o esforço de i18n rodou por ondas temáticas e deixou as páginas auxiliares
para trás. Keys em `web/src/lib/i18n/` (en/pt-BR/es) existem para muitos dos termos
(observação do BUGS.md backlog linha 74 — "Keys exist, most page titles still
hardcoded English").

**Ação recomendada:** task de **P2 baixo esforço** — escolher 3 páginas por sprint
até fechar as 15. Priorizar `risk`, `whatif`, `schedule` (tráfego alto).

## Dark mode

`grep -l 'dark:' web/src/routes/**/+page.svelte | wc -l` retorna coverage parcial.
`docs/GAP_ASSESSMENT_v3.3.md` (abril/7) reportava 5 de 45 páginas. A v3.3.0 → v4.0.1
passou por uma batch "Loading skeletons on 24 pages" (BUGS.md) e dark-mode foi
propagado. Aguardar verificação completa com script que compara `dark:` por página.

**Follow-up sugerido (P3):** gerar `docs/audit/darkmode-matrix.md` automaticamente
em CI.

## A11y

Últimas melhorias documentadas (BUGS.md):

- v3.8 wave 10: 12 warnings → 0 em ScheduleViewer (GanttCanvas `<g>` com keyboard handlers).
- Upload drop zone: `role="button"` + `tabindex="0"` necessário — status final não
  verificado nesta auditoria.

Não rodei `axe-core`/`pa11y` nesta rodada — follow-up.

## Rotas órfãs / inconsistências

A partir da lista de rotas e da lista de routers backend:

| Rota web | Router backend | Observação |
|---|---|---|
| `/pareto` | `analysis.py` (pareto endpoint) | Ambos presentes — GAP v3.3 resolvido. |
| `/optimizer` | `whatif.py` / `analysis.py` | **Issue #14** aberta: field mismatch frontend/backend |
| `/ips` | `analysis.py` (`/ips-reconciliation`) | OK |
| `/forensic` | `forensics.py` | OK |
| `/programs` | `programs.py` | OK |
| `/org` | `organizations.py` | OK |

Nenhuma rota web totalmente órfã detectada nesta rodada. O único mismatch documentado
é o **Issue #14 (optimizer)** — fix deliberadamente deferido para não expandir o escopo
da v4.0.1 (conforme CLAUDE.md release notes). Precisa estar rastreado em backlog
do próximo cycle.

## TypeScript strict

Issue **#8** "Frontend: 17 TypeScript type errors across 7 files" aberta desde
2026-03-29 (data UTC). Não houve commit de progresso citado nos release notes de
v4.0.0 / v4.0.1. **Sugestão:** anexar a #8 à próxima wave como "technical debt
fast-track" — 17 erros em 7 arquivos são ~1 dia de trabalho.

## Feedback de loading / error

Backlog BUGS.md documenta:

- Loading skeletons: 24 páginas (v3.1.0).
- Error boundary: `svelte:boundary` implementado (v3.1.0).
- Toast notification system: implementado (v1.1.0).

**Gap de observação:** páginas com i18n baixo (seção anterior) tendem a ter também
loading/error menos cuidados. Worth checking `alerts`, `anomalies`, `resources`,
`cashflow` especificamente.

## Mobile

`BUGS.md` Open Testing Checklist: `[ ] Mobile — all pages + hamburger menu +
collapsible sections`. Unchecked. Não há evidência de teste sistemático mobile
nos últimos 3 waves. **P2 recommend**: escolher 5 páginas core (home, upload,
schedule, risk, compare) e rodar Lighthouse Mobile em cada.

## Observação positiva (manter)

- Adapter `@sveltejs/adapter-static` (confirmado em `web/package.json`) — deploy
  Cloudflare Pages sem SSR é a decisão ADR-0002 implementada.
- Tailwind v4 via `@tailwindcss/vite` — sem PostCSS overhead.
- 11 componentes SVG custom — zero chart.js (BUGS.md item closed) → nenhuma dep
  runtime pesada no frontend além de Supabase e PostHog.
- Vitest harness adicionado no v4.0.1 — 15 testes compose. Abre espaço para
  co-localizar testes de componente. Ação: aumentar cobertura aos poucos.
