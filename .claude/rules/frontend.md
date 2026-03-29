---
paths:
  - "web/src/**/*.svelte"
  - "web/src/**/*.ts"
---

# SvelteKit Frontend Rules

- Svelte 5 runes: use `$state()`, `$derived()`, `$effect()` — not legacy reactive `$:` syntax
- TypeScript strict mode — no `any` without justification
- Tailwind CSS v4 for all styling — no custom CSS files
- Charts are hand-crafted SVG — do NOT use chart.js (it's a dead dependency)
- Auth state lives in `web/src/lib/stores/auth.ts` (lazy init pattern)
- API calls go through `web/src/lib/api.ts`
- Route structure: `web/src/routes/` with SvelteKit file-based routing
- Components in `web/src/lib/components/`
- Adapter: adapter-static for Cloudflare Pages (SSR disabled)
- Always handle loading and error states in pages
