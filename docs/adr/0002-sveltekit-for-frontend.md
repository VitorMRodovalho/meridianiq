# 0002. SvelteKit + Tailwind v4 for the frontend

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-17 (retroactive — decision made circa v0.6, 2024)

## Context and Problem Statement

MeridianIQ needs a web frontend that:
- Renders complex analysis UI (Gantt chart with 1000+ activities, S-curves, DCMA scorecards, cost variance matrices).
- Charts are **hand-crafted SVG** — no `chart.js`-style runtime dependency acceptable.
- Runs as a static SPA on Cloudflare Pages (free tier) with the backend on Fly.io.
- Is small enough to be read end-to-end by one person.
- Supports i18n (en / pt-BR / es), dark mode, keyboard shortcuts.
- Has TypeScript strict mode as a non-negotiable.

## Decision Drivers

- **Bundle size** — a Gantt-heavy schedule viewer must not feel heavy on first paint.
- **Runtime performance** — 1000+ SVG elements must render smoothly on laptop-class hardware.
- **Ergonomic reactivity** — the ScheduleViewer has deep nested state (WBS expand/collapse, date range, zoom, selected activities). A reactive primitive that isn't a hook is desirable.
- **Solo-maintainability** — one person reads the whole frontend.
- **Hosting flexibility** — static-output adapter for Cloudflare Pages.

## Considered Options

1. **SvelteKit + Tailwind v4**
2. **Next.js (React) + Tailwind**
3. **Remix (React) + Tailwind**
4. **Vue 3 + Nuxt + Tailwind**
5. **SolidJS + SolidStart**

## Decision Outcome

**Chosen: SvelteKit + Tailwind v4.**

### Rationale

- **Smaller bundles than React** — matters because the app has to feel fast despite rendering hand-crafted SVG Gantt charts.
- **Runes (`$state`, `$derived`, `$effect`) in Svelte 5** are the cleanest reactivity primitive available in any mainstream framework. The ScheduleViewer's nested state (date range × zoom × WBS tree × selected activities) is ~40% shorter in runes than an equivalent React hooks implementation would be.
- **adapter-static** produces a pure static output suitable for Cloudflare Pages. No Node runtime needed at the edge.
- **TypeScript 6 strict mode** works cleanly with Svelte 5; no `.svelte.ts` vs `.ts` dance.
- **Tailwind v4's Vite plugin** fits SvelteKit's build pipeline with one import line.
- **File-system routing** in `web/src/routes/` is a good match for a 53-page app — no routing config file to drift out of sync.

### Rejected alternatives

- **Next.js** — larger bundle baseline, and React's reactivity primitives (hooks + context) get awkward fast for deep nested state. Also, Next's server-component model is a poor fit when the backend is a separate Fly.io FastAPI service. We'd be paying for a server we don't use.
- **Remix** — same React cost issue. Remix's server-centric story is mismatched with the SPA-on-Cloudflare-Pages target.
- **Vue 3 + Nuxt** — solid reactivity story with the Composition API, but a meaningfully smaller ecosystem for our use case and larger bundle than Svelte. No decisive advantage over SvelteKit.
- **SolidJS + SolidStart** — attractive reactivity story, but the ecosystem is substantially thinner (fewer libraries, fewer hiring candidates, less stability on major releases). Betting a frontend on SolidStart would have added project risk.

## Consequences

**Positive**:
- Initial-load bundle is small enough for Cloudflare Pages to serve without complaint.
- Svelte 5 runes made the v3.6 Gantt stability refactor possible — the state machine is explicit in ~200 lines of runes that would have been 500+ lines of hooks.
- `adapter-static` keeps the frontend deploy story trivially simple: one `npm run build`, one `wrangler pages deploy`.

**Negative**:
- **Smaller hiring pool** than React — if the team grows past one person, onboarding cost is higher.
- **Fewer third-party components** than React — charts being hand-crafted SVG is partly a consequence of this (though also a deliberate methodology choice).
- **Svelte 5 was new when chosen** — we ate some breakage in the v5 pre-release period.

**Neutral**:
- Tailwind v4 was picked when it was stable. Upgrading to v5 (when it lands) will be a non-trivial task; that cost is known.
