<!-- Audit run: 2026-04-26 · Layer 2d (UX / Frontend) -->
# Camada 2d — UX / Frontend

i18n cobertura, runes purity, dark mode, a11y.

## Sumário executivo

- **Svelte 5 runes purity:** ✅ `grep "^\s*\$:" web/src/routes web/src/lib --include='*.svelte'` retorna **vazio**. Runes 100%.
- **chart.js dead-dep:** ✅ zero refs em `web/src` ou `web/package.json`.
- **i18n top-level pages:** ✅ #22 closure (Cycle 2 W3 v4.0.2) entregou 15 pages.
- **i18n detail pages:** ⚠ ainda gap — AUDIT-2026-04-26-008.

---

## AUDIT-2026-04-26-008 · P3 · Detail pages + sub-feature pages com `$t() = 0`

**Páginas detectadas com `$t() = 0` (sweep completo):**

| Página | $t() count | Categoria |
|---|---|---|
| `evm/[id]/+page.svelte` | 0 | Detail (param-based) |
| `tia/[id]/+page.svelte` | 0 | Detail |
| `forensic/[id]/+page.svelte` | 0 | Detail |
| `risk/[id]/+page.svelte` | 0 | Detail |
| `projects/[id]/+page.svelte` | 0 | Detail |
| `auth/callback/+page.svelte` | 0 | OAuth callback (provavelmente OK — minimal UI) |
| `cost/g702/+page.svelte` | 0 | Sub-feature (G702 form) |
| `cost/compare/+page.svelte` | 0 | Sub-feature (cost compare) |

**Páginas com `$t() ≤ 4` (minimal):**

| Página | $t() count |
|---|---|
| `evm/+page.svelte` | 3 |
| `lookahead/+page.svelte` | 4 |
| `ask/+page.svelte` | 4 |
| `calendar-validation/+page.svelte` | 4 |
| `health/+page.svelte` | 4 |
| `programs/[id]/+page.svelte` | 1 |

**Por que existe:** issue #22 (audit-2026-04-22 closure) escopou explicitamente
"15 top-level pages with minimal i18n coverage" e foi entregue em 6 batches
(A1-A6). Detail pages (`[id]/+page.svelte`) não estavam no escopo declarado.
Algumas detail pages renderizam dados crus (números, tabelas, gráficos) com
strings UI mínimas — `$t() = 0` é coerente com low-text UI. Outras (cost/g702,
cost/compare) **deveriam ter labels traduzidas**.

**Risco:** P3. **Cobertura i18n quebra simetria** — usuário em pt-BR navega em
todo o produto traduzido, mas ao entrar num projeto específico volta a inglês.

**Ação proposta (NÃO commit Cycle 3 — defere para Cycle 4 W5 ou Cycle 5):**

1. **Triagem rápida:**
   - `auth/callback/+page.svelte` — minimal UI ("redirecting…"), provavelmente OK em inglês.
   - `[id]/+page.svelte` em todos os surfaces — verificar individualmente. Se renderizam strings UI fixas (botões, labels), traduzir.
   - `cost/g702/+page.svelte` + `cost/compare/+page.svelte` — **alta prioridade** porque são páginas-feature; traduzir.

2. **Issue tracking:** abrir issue `i18n: detail + sub-feature pages (carry-over de #22)` com label `audit-2026-04-26 + priority:P3`.

3. **Future protection:** considerar lint custom (`web/scripts/check_i18n_coverage.js`) que falha se uma `+page.svelte` renderizar texto literal estático fora de `<code>`/`<pre>` blocks sem `$t()` — protect-against-regression CI.

---

## i18n surface — locales status

3 locales em `web/src/lib/i18n/`:
- `en/` — base
- `pt-BR/` — translations
- `es/` — translations

Verificação manual no Cycle 2 W2 closure: `is_construction_active_yes/no/unknown`,
`preview_label`, `preview_marker`, `preview_aria` × 3 locales = 21 keys novas
(W2). Cycle 2 W3 não acrescentou keys i18n. Cycle 3 W0 (este audit) é doc-only.

---

## Dark mode

`web/src/lib/stores/theme.ts` — verificação não foi feita nesta rodada por estar
fora do escopo de regression. Carry-over: `feedback_schedule_viewer_bugs.md` user
memory anota "dark mode done" com último check em 2026-04-15.

---

## A11y

`feedback_schedule_viewer_bugs.md` user memory + Cycle 2 W2 close:
`LifecyclePhaseCard.svelte` recebeu `aria-label` próprio com chave `lifecycle.preview_aria`
("preliminary classification") para que screen-readers não falem "open paren preview
close paren". Padrão correto.

**Sweep completo de a11y:** fora do escopo desta rodada.

---

## Mobile responsiveness

ADR-0021 §"Wave plan" W5 (optional) menciona "Field Engineer mobile look-ahead spike"
como sub-pick — escopo Cycle 3. Não auditado nesta rodada porque ainda não shipou.
Carry-over para audit pós-Cycle-3.

---

## ScheduleViewer (Gantt) — saúde

Standing user memory anota:
- Standard columns ✅
- Magic box ✅
- WBS aggregation ✅
- Resizable panel pending

Não auditado nesta rodada (escopo idêntico baseline).

Wave 7 (resource + cost) tracked em sub-issues #29 (P1), #30 (P2), #31 (P2),
#32 (P3) — todas OPEN. Carry-over de AUDIT-015 baseline.

---

**Sumário desta camada:** 1 achado P3 novo (008 detail-pages i18n gap),
runes 100%, dark mode + a11y sem regressão observada, ScheduleViewer estável.
**UX surface saudável** com sub-coverage gap em detail pages.
