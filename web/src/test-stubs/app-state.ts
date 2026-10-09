// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// Vitest runs without SvelteKit's plugin, so `$app/state` does not resolve
// there. vitest.config.ts aliases it here; a test overrides `page` with
// vi.mock('$app/state', ...) when the route reads the URL or params.
export const page = {
	url: new URL('http://localhost/'),
	params: {} as Record<string, string>,
	status: 200,
	error: null as { message: string } | null
};
