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
import { compilerOptions } from './vite.config';

export default defineConfig({
	// svelte.config.js is gone (SvelteKit 3), so the compiler options come
	// from vite.config.ts; without them the plugin falls back to its defaults.
	plugins: [svelte({ compilerOptions })],
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
			// `#lib/*` needs no alias: it is a subpath import declared in
			// package.json, which Vite resolves natively (SvelteKit 3).
			// $app/* comes from SvelteKit's plugin, absent here. Pages import
			// `page` from $app/state; tests mock it per case.
			'$app/state': fileURLToPath(new URL('./src/test-stubs/app-state.ts', import.meta.url)),
		},
	},
});
