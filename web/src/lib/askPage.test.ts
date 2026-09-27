// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// The /ask page states, rendered: a closed state must read as a designed
// early-access page (approval by the administrators, a paid plan later, and
// where to go next), never as a broken page, and must offer no composer.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/svelte';
import { get } from 'svelte/store';
import { locale, t } from '$lib/i18n';
import AskPage from '../routes/ask/+page.svelte';

const { statusMock } = vi.hoisted(() => ({ statusMock: vi.fn() }));

vi.mock('$lib/supabase', () => ({
	supabase: {
		auth: {
			getSession: vi.fn(async () => ({ data: { session: { access_token: 'token' } } }))
		}
	}
}));

vi.mock('$lib/api', async () => {
	const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api');
	return {
		ApiError: actual.ApiError,
		getAiStatus: statusMock,
		getProjects: vi.fn(async () => ({
			projects: [{ project_id: 'p1', name: 'Synthetic project', activity_count: 3 }]
		})),
		askSchedule: vi.fn()
	};
});

function status(available: boolean, reason: string | null, extra: Record<string, unknown> = {}) {
	return {
		available,
		reason,
		daily_limit: null,
		used_today: null,
		remaining_today: null,
		resets_at: null,
		...extra
	};
}

beforeEach(() => {
	locale.set('en');
	statusMock.mockReset();
});
afterEach(() => cleanup());

describe('/ask closed states', () => {
	for (const reason of ['ai_disabled', 'ai_not_entitled']) {
		it(`${reason}: early-access panel, approval and paid plan, ways forward, no composer`, async () => {
			statusMock.mockResolvedValue(status(false, reason));
			render(AskPage);
			const tr = get(t);
			const heading = await screen.findByRole('heading', { name: tr('ask.access_title') });
			const panel = heading.closest('#ask-gate-message') as HTMLElement;
			expect(panel.textContent).toContain(tr(`ask.reason_${reason.slice(3)}`));
			expect(panel.textContent).toMatch(/approved by the MeridianIQ administrators/);
			expect(panel.textContent).toMatch(/paid plan/);
			expect(panel.textContent).toContain(tr('ask.rest_available'));
			expect(screen.getByRole('link', { name: tr('ask.go_projects') }).getAttribute('href')).toBe(
				'/projects'
			);
			expect(screen.getByRole('link', { name: tr('ask.go_upload') }).getAttribute('href')).toBe(
				'/upload'
			);
			expect(screen.queryByRole('textbox')).toBeNull();
			expect(screen.queryByRole('combobox')).toBeNull();
			expect(screen.queryByRole('alert')).toBeNull();
		});
	}

	it('a status that fails to load closes the page with the same kind of panel', async () => {
		statusMock.mockRejectedValue(new Error('network'));
		render(AskPage);
		const tr = get(t);
		await screen.findByRole('heading', { name: tr('ask.unavailable_title') });
		expect(screen.getByRole('link', { name: tr('ask.go_projects') })).toBeTruthy();
		expect(screen.queryByRole('textbox')).toBeNull();
	});
});

describe('/ask open states (control)', () => {
	it('available: the composer is there and no access panel', async () => {
		statusMock.mockResolvedValue(
			status(true, null, { daily_limit: 20, used_today: 3, remaining_today: 17 })
		);
		render(AskPage);
		await screen.findByRole('textbox');
		expect(screen.queryByRole('heading', { name: get(t)('ask.access_title') })).toBeNull();
	});

	it('daily quota: the composer stays, disabled and described by the message', async () => {
		statusMock.mockResolvedValue(
			status(false, 'ai_daily_quota', { daily_limit: 20, used_today: 20, remaining_today: 0 })
		);
		render(AskPage);
		const input = await screen.findByRole('textbox');
		expect((input as HTMLInputElement).disabled).toBe(true);
		expect(input.getAttribute('aria-describedby')).toBe('ask-gate-message');
	});
});
