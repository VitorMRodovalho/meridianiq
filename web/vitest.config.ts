// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// Vitest config separate from vite.config.ts so SvelteKit's dev plugin
// does not participate in test resolution. Tests target plain .ts
// composables — component tests are out of scope for this setup and
// would require vitest-browser-svelte.

import { defineConfig } from 'vitest/config';

export default defineConfig({
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
	},
});
