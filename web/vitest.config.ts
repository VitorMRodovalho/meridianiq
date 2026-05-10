// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// Vitest config separate from vite.config.ts so SvelteKit's dev plugin
// does not participate in test resolution. Covers (a) plain .ts
// composables (e.g. ``useWebSocketProgress.test.ts``) and (b) Svelte 5
// rune-based components via ``@testing-library/svelte`` v5 + jsdom
// (Cycle 5 W3-B per ADR-0024 — issue #87 closure).

import { svelte } from '@sveltejs/vite-plugin-svelte';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [svelte()],
	test: {
		environment: 'jsdom',
		include: ['src/**/*.test.ts'],
		globals: false,
	},
	resolve: {
		// Force browser entry points so svelte/store's `writable` etc.
		// resolve to the client build rather than an SSR variant that
		// does not carry the subscribe semantics we rely on.
		conditions: ['browser'],
		alias: {
			// SvelteKit's $lib alias — provided by adapter at build time;
			// vitest needs it explicitly. Pointing at src/lib means tests
			// resolve $lib/api, $lib/i18n, etc. the same way the app does.
			$lib: fileURLToPath(new URL('./src/lib', import.meta.url)),
		},
	},
});
