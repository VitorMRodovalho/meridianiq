// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// The error page picks its copy from the status. hooks.client.ts replaces
// every error message with a generic one, and a 404 used to show
// "An unexpected error occurred" under "Page not found".

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/svelte';
import { get } from 'svelte/store';
import { t } from '$lib/i18n';
import ErrorPage from '../routes/+error.svelte';

const state = vi.hoisted(() => ({
	page: {
		status: 404,
		error: { message: 'An unexpected error occurred. Please try again.' } as { message: string } | null,
		url: new URL('http://localhost/missing'),
		params: {} as Record<string, string>
	}
}));

vi.mock('$app/state', () => state);

const tr = (key: string) => get(t)(key);

describe('+error.svelte', () => {
	afterEach(cleanup);

	it('shows the not-found copy for a 404, whatever the hook set as message', () => {
		state.page.status = 404;
		render(ErrorPage);

		expect(screen.getByRole('heading', { name: tr('error_page.not_found_title') })).toBeTruthy();
		expect(screen.getByText(tr('error_page.not_found_body'))).toBeTruthy();
		expect(screen.queryByText(tr('error_page.generic_body'))).toBeNull();
	});

	it('shows the generic copy for any other status', () => {
		state.page.status = 500;
		render(ErrorPage);

		expect(screen.getByRole('heading', { name: tr('error_page.generic_title') })).toBeTruthy();
		expect(screen.getByText(tr('error_page.generic_body'))).toBeTruthy();
	});
});
