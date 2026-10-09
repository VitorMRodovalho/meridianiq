// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// The /admin/ai access requests, rendered: a list that could not be read never
// reads as "no requests", each action names its account, one action runs at a
// time, focus returns to the section heading, an outcome the server did not
// confirm says so, and a requester's note is shown as text, never as markup.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { get } from 'svelte/store';
import { locale, t } from '$lib/i18n';
import { ApiError, TimeoutError } from '$lib/api';
import AdminAiPage from '../routes/admin/ai/+page.svelte';

const { adminMock, approveMock, dismissMock } = vi.hoisted(() => ({
	adminMock: vi.fn(),
	approveMock: vi.fn(),
	dismissMock: vi.fn()
}));

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
		TimeoutError: actual.TimeoutError,
		getAiAdmin: adminMock,
		grantAiAccess: vi.fn(),
		revokeAiAccess: vi.fn(),
		approveAiRequest: approveMock,
		dismissAiRequest: dismissMock
	};
});

const REQ_A = {
	user_id: 'user-a',
	email: 'a@example.com',
	note: 'Weekly look-ahead reviews',
	requested_at: '2026-09-20T15:00:00Z'
};
const REQ_B = { user_id: 'user-b', email: null, note: null, requested_at: '2026-09-21T15:00:00Z' };

function summary(extra: Record<string, unknown> = {}) {
	return {
		available: false,
		reason: 'ai_disabled',
		config: {
			enabled: false,
			api_key_set: false,
			model_set: false,
			prices_set: false,
			global_budget_set: false,
			sdk_available: true,
			durable_ledger: true
		},
		model: null,
		global_budget_usd: null,
		global_spent_month_usd: '0',
		defaults: { daily_questions: 20, account_monthly_budget_usd: '5.00' },
		stale_reservations: 0,
		month_calls: { reserved: 0, completed: 0, failed: 0, unknown: 0 },
		last_failure_at: null,
		reserve_per_question_usd: null,
		entitlements: [],
		requests: [REQ_A, REQ_B],
		requests_total: 2,
		...extra
	};
}

const entitlementFor = (userId: string, email: string | null) => ({
	user_id: userId,
	email,
	active: true,
	granted_at: '2026-09-27T12:00:00Z',
	revoked_at: null,
	daily_questions: null,
	monthly_budget_usd: null,
	note: null,
	used_today: 0,
	spent_month_usd: '0.00'
});

const tr = (key: string) => get(t)(key);
const fill = (key: string, values: Record<string, string>) =>
	Object.entries(values).reduce((s, [k, v]) => s.replace(`{${k}}`, v), tr(key));

const approveName = (account: string) => fill('admin_ai.approve_aria', { account });
const dismissName = (account: string) => fill('admin_ai.dismiss_aria', { account });

async function renderSection() {
	render(AdminAiPage);
	const heading = await screen.findByRole('heading', { name: /^Access requests/ });
	return heading.closest('section') as HTMLElement;
}

beforeEach(() => {
	locale.set('en');
	adminMock.mockReset();
	approveMock.mockReset();
	dismissMock.mockReset();
});
afterEach(() => cleanup());

describe('/admin/ai access requests: states', () => {
	it('null: "could not be read", which is not "none"', async () => {
		adminMock.mockResolvedValue(summary({ requests: null, requests_total: null }));
		const section = await renderSection();
		expect(section.textContent).toContain(tr('admin_ai.requests_unread'));
		expect(section.textContent).not.toContain(tr('admin_ai.requests_empty'));
		expect(within(section).getByRole('heading').textContent?.trim()).toBe(tr('admin_ai.requests_heading'));
		expect(within(section).queryByRole('list')).toBeNull();
	});

	it('an API without the field is also "could not be read"', async () => {
		const body = summary();
		delete (body as Record<string, unknown>).requests;
		delete (body as Record<string, unknown>).requests_total;
		adminMock.mockResolvedValue(body);
		const section = await renderSection();
		expect(section.textContent).toContain(tr('admin_ai.requests_unread'));
	});

	it('empty: one muted line and a count of 0', async () => {
		adminMock.mockResolvedValue(summary({ requests: [], requests_total: 0 }));
		const section = await renderSection();
		expect(section.textContent).toContain(tr('admin_ai.requests_empty'));
		expect(section.textContent).not.toContain(tr('admin_ai.requests_unread'));
		expect(within(section).getByRole('heading').textContent?.trim()).toBe('Access requests (0)');
		expect(within(section).queryByRole('button')).toBeNull();
	});

	it('items: cards in a list, each action named after the account, the default limits stated', async () => {
		adminMock.mockResolvedValue(summary());
		const section = await renderSection();
		expect(within(section).getByRole('heading').textContent?.trim()).toBe('Access requests (2)');
		const items = within(within(section).getByRole('list')).getAllByRole('listitem');
		expect(items).toHaveLength(2);
		// The section comes before the grant form on the page.
		const grantHeading = screen.getByRole('heading', { name: tr('admin_ai.grant_heading') });
		expect(section.compareDocumentPosition(grantHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

		for (const account of ['a@example.com', 'user-b']) {
			const approve = screen.getByRole('button', { name: approveName(account) });
			const dismiss = screen.getByRole('button', { name: dismissName(account) });
			// The accessible name starts with the visible label.
			expect(approve.textContent?.trim()).toBe(tr('admin_ai.btn_approve'));
			expect(dismiss.textContent?.trim()).toBe(tr('admin_ai.btn_dismiss'));
		}
		expect(items[0].textContent).toContain('Weekly look-ahead reviews');
		expect(items[1].textContent).toContain(tr('admin_ai.request_no_note'));
		expect(section.textContent).toContain('(20 questions a day, $5.00 a month)');
		expect(section.textContent).not.toMatch(/Showing \d+ of/);
	});

	it('a capped list says how many are shown of the total', async () => {
		adminMock.mockResolvedValue(summary({ requests_total: 5 }));
		const section = await renderSection();
		expect(within(section).getByRole('heading').textContent?.trim()).toBe('Access requests (5)');
		expect(section.textContent).toContain('Showing 2 of 5 pending requests, oldest first.');
	});

	it('a note is shown as text, never as markup', async () => {
		const note = '<script>window.__pwned = 1</script><b>bold</b>\nsecond line';
		adminMock.mockResolvedValue(summary({ requests: [{ ...REQ_A, note }], requests_total: 1 }));
		const section = await renderSection();
		const item = within(section).getByRole('listitem');
		expect(item.querySelector('script')).toBeNull();
		expect(item.querySelector('b')).toBeNull();
		expect(item.textContent).toContain('<script>window.__pwned = 1</script><b>bold</b>');
		expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined();
	});
});

describe('/admin/ai access requests: actions', () => {
	it('approve: one call, the list reloaded, the announcement, focus on the section heading', async () => {
		adminMock
			.mockResolvedValueOnce(summary())
			.mockResolvedValueOnce(
				summary({
					requests: [REQ_B],
					requests_total: 1,
					entitlements: [entitlementFor('user-a', 'a@example.com')]
				})
			);
		approveMock.mockResolvedValue(entitlementFor('user-a', 'a@example.com'));
		const section = await renderSection();
		await fireEvent.click(screen.getByRole('button', { name: approveName('a@example.com') }));
		const status = within(section).getByRole('status');
		await waitFor(() => expect(status.textContent).toContain('Access approved for a@example.com.'));
		expect(approveMock).toHaveBeenCalledTimes(1);
		expect(approveMock).toHaveBeenCalledWith('user-a');
		expect(dismissMock).not.toHaveBeenCalled();
		expect(adminMock).toHaveBeenCalledTimes(2);
		const heading = within(section).getByRole('heading');
		await waitFor(() => expect(document.activeElement).toBe(heading));
		expect(heading.id).toBe('ai-requests-title');
		expect(screen.queryByRole('button', { name: approveName('a@example.com') })).toBeNull();
	});

	it('while one action runs every request button is disabled and the active one says so', async () => {
		adminMock.mockResolvedValue(summary());
		let resolve: (v: unknown) => void = () => undefined;
		dismissMock.mockImplementation(() => new Promise((r) => (resolve = r)));
		const section = await renderSection();
		await fireEvent.click(screen.getByRole('button', { name: dismissName('user-b') }));
		const buttons = within(within(section).getByRole('list')).getAllByRole('button');
		expect(buttons).toHaveLength(4);
		for (const b of buttons) expect((b as HTMLButtonElement).disabled).toBe(true);
		expect(buttons.map((b) => b.textContent?.trim())).toContain(tr('admin_ai.btn_dismissing'));
		// A second click on another row does nothing while the first runs.
		await fireEvent.click(buttons[0]);
		expect(approveMock).not.toHaveBeenCalled();
		resolve({ dismissed: true });
		await waitFor(() =>
			expect(within(section).getByRole('status').textContent).toContain(
				'Request from user-b dismissed. The account can request again in 30 days.'
			)
		);
		expect(dismissMock).toHaveBeenCalledTimes(1);
		expect(dismissMock).toHaveBeenCalledWith('user-b');
	});

	it('404 ai_request_not_found: informational, not an error, and the list reloaded', async () => {
		adminMock
			.mockResolvedValueOnce(summary())
			.mockResolvedValueOnce(summary({ requests: [REQ_B], requests_total: 1 }));
		approveMock.mockRejectedValue(new ApiError('Not found', 404, 'ai_request_not_found'));
		const section = await renderSection();
		await fireEvent.click(screen.getByRole('button', { name: approveName('a@example.com') }));
		const status = within(section).getByRole('status');
		await waitFor(() => expect(status.textContent).toContain(tr('admin_ai.request_not_found')));
		expect(within(section).queryByRole('alert')).toBeNull();
		expect(adminMock).toHaveBeenCalledTimes(2);
		await waitFor(() =>
			expect(screen.queryByRole('button', { name: approveName('a@example.com') })).toBeNull()
		);
		await waitFor(() => expect(document.activeElement).toBe(within(section).getByRole('heading')));
	});

	it('timeout: the outcome-unknown message after reloading the list', async () => {
		adminMock.mockResolvedValue(summary());
		approveMock.mockRejectedValue(new TimeoutError());
		const section = await renderSection();
		await fireEvent.click(screen.getByRole('button', { name: approveName('a@example.com') }));
		const alert = await within(section).findByRole('alert');
		expect(alert.textContent).toContain(tr('admin_ai.outcome_unknown'));
		expect(approveMock).toHaveBeenCalledTimes(1);
		expect(adminMock).toHaveBeenCalledTimes(2);
		expect(within(section).getByRole('status').textContent?.trim()).toBe('');
	});

	it('a 5xx with the list not reloadable: the stale variant', async () => {
		adminMock.mockResolvedValueOnce(summary()).mockRejectedValueOnce(new Error('network'));
		dismissMock.mockRejectedValue(new ApiError('boom', 503, null));
		const section = await renderSection();
		await fireEvent.click(screen.getByRole('button', { name: dismissName('a@example.com') }));
		const alert = await within(section).findByRole('alert');
		expect(alert.textContent).toContain(tr('admin_ai.outcome_unknown_stale'));
		expect(alert.textContent).not.toContain('boom');
	});

	it('approve succeeds but the reload fails: both lists are patched from the answer', async () => {
		adminMock.mockResolvedValueOnce(summary()).mockRejectedValueOnce(new Error('network'));
		approveMock.mockResolvedValue(entitlementFor('user-a', 'a@example.com'));
		const section = await renderSection();
		await fireEvent.click(screen.getByRole('button', { name: approveName('a@example.com') }));
		await waitFor(() =>
			expect(within(section).getByRole('status').textContent).toContain('Access approved for a@example.com.')
		);
		expect(screen.queryByRole('button', { name: approveName('a@example.com') })).toBeNull();
		expect(within(section).getByRole('heading').textContent?.trim()).toBe('Access requests (1)');
		expect(
			screen.getByRole('button', { name: fill('admin_ai.revoke_aria', { email: 'a@example.com' }) })
		).toBeTruthy();
	});
});
