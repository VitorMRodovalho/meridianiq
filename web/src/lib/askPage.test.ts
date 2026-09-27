// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// The /ask page states, rendered: a closed state must read as a designed
// early-access page (approval by the administrators, a paid plan later, and
// where to go next), never as a broken page, and must offer no composer.
// Inside it, the "request access" block follows the account's request, and
// a request whose outcome is unknown is confirmed by reading the status
// without ever replacing the panel with "Temporarily unavailable".

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { get } from 'svelte/store';
import { locale, t } from '$lib/i18n';
import { ApiError, TimeoutError } from '$lib/api';
import AskPage from '../routes/ask/+page.svelte';

const { statusMock, requestMock } = vi.hoisted(() => ({
	statusMock: vi.fn(),
	requestMock: vi.fn()
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
		getAiStatus: statusMock,
		getProjects: vi.fn(async () => ({
			projects: [{ project_id: 'p1', name: 'Synthetic project', activity_count: 3 }]
		})),
		askSchedule: vi.fn(),
		requestAiAccess: requestMock
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

/** A closed status carrying an access value (the request fields of the contract). */
function closed(reason: string, access: unknown, extra: Record<string, unknown> = {}) {
	return status(false, reason, {
		access,
		access_requested_at: null,
		access_retry_after: null,
		...extra
	});
}

const REQUESTED_AT = '2026-09-20T15:00:00Z';
const RETRY_AFTER = '2026-10-20T15:00:00Z';
const longDate = (iso: string) => new Date(iso).toLocaleDateString('en-US', { dateStyle: 'long' });

const tr = (key: string) => get(t)(key);
/** The question input, by its accessible name (not any textbox). */
const composer = () => screen.queryByRole('textbox', { name: tr('ask.input_label') });
const noteBox = () => screen.queryByRole('textbox', { name: tr('ask.access_note_label') });
const requestButton = () => screen.queryByRole('button', { name: tr('ask.access_request') });

async function renderPanel() {
	render(AskPage);
	return screen.findByRole('heading', { name: tr('ask.access_title') });
}

beforeEach(() => {
	locale.set('en');
	statusMock.mockReset();
	requestMock.mockReset();
});
afterEach(() => cleanup());

describe('/ask closed states', () => {
	for (const reason of ['ai_disabled', 'ai_not_entitled']) {
		it(`${reason}: early-access panel, approval and paid plan, ways forward, no composer`, async () => {
			statusMock.mockResolvedValue(status(false, reason));
			render(AskPage);
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
			expect(composer()).toBeNull();
			expect(screen.queryByRole('combobox')).toBeNull();
			expect(screen.queryByRole('alert')).toBeNull();
			// No `access` field (an API that predates it): the plain panel, no form.
			expect(noteBox()).toBeNull();
			expect(requestButton()).toBeNull();
		});
	}

	it('a status that fails to load closes the page with the same kind of panel', async () => {
		statusMock.mockRejectedValue(new Error('network'));
		render(AskPage);
		await screen.findByRole('heading', { name: tr('ask.unavailable_title') });
		expect(screen.getByRole('link', { name: tr('ask.go_projects') })).toBeTruthy();
		expect(composer()).toBeNull();
		expect(noteBox()).toBeNull();
	});
});

describe('/ask request access: states', () => {
	for (const reason of ['ai_disabled', 'ai_not_entitled']) {
		it(`${reason} + none: the form, labelled and described, and no competing primary link`, async () => {
			statusMock.mockResolvedValue(closed(reason, 'none'));
			await renderPanel();
			const note = noteBox() as HTMLTextAreaElement;
			expect(note).toBeTruthy();
			expect(note.tagName).toBe('TEXTAREA');
			expect(note.maxLength).toBe(500);
			expect(note.rows).toBe(3);
			expect(document.activeElement).not.toBe(note);
			const hintId = note.getAttribute('aria-describedby') as string;
			expect(document.getElementById(hintId)?.textContent).toContain('Up to 500 characters');
			expect(requestButton()).toBeTruthy();
			// Both links are outline links while the request button is showing.
			for (const name of [tr('ask.go_projects'), tr('ask.go_upload')]) {
				const cls = screen.getByRole('link', { name }).className;
				expect(cls).toContain('border');
				expect(cls).not.toContain('bg-blue-600');
			}
			expect(composer()).toBeNull();
		});
	}

	it('control: without the form the projects link is the primary one', async () => {
		statusMock.mockResolvedValue(closed('ai_disabled', 'pending', { access_requested_at: REQUESTED_AT }));
		await renderPanel();
		expect(screen.getByRole('link', { name: tr('ask.go_projects') }).className).toContain('bg-blue-600');
	});

	it('pending: the day it was requested (local time), no form', async () => {
		statusMock.mockResolvedValue(closed('ai_disabled', 'pending', { access_requested_at: REQUESTED_AT }));
		const heading = await renderPanel();
		const panel = heading.closest('#ask-gate-message') as HTMLElement;
		expect(panel.textContent).toContain(`You requested access on ${longDate(REQUESTED_AT)}.`);
		expect(panel.textContent).not.toContain(tr('ask.access_sent'));
		expect(noteBox()).toBeNull();
		expect(requestButton()).toBeNull();
		// Loading into a non-form state moves no focus.
		expect(document.activeElement).toBe(document.body);
	});

	it('dismissed: from when a new request can be sent, no form, nothing red, no alert', async () => {
		statusMock.mockResolvedValue(
			closed('ai_not_entitled', 'dismissed', {
				access_requested_at: REQUESTED_AT,
				access_retry_after: RETRY_AFTER
			})
		);
		const heading = await renderPanel();
		const panel = heading.closest('#ask-gate-message') as HTMLElement;
		expect(panel.textContent).toContain(`You can send a new request from ${longDate(RETRY_AFTER)}.`);
		expect(noteBox()).toBeNull();
		expect(requestButton()).toBeNull();
		expect(screen.queryByRole('alert')).toBeNull();
		expect(panel.innerHTML).not.toMatch(/(?:bg|text|border)-red-/);
	});

	it('entitled (feature not open yet): already approved, no form', async () => {
		statusMock.mockResolvedValue(closed('ai_disabled', 'entitled'));
		const heading = await renderPanel();
		const panel = heading.closest('#ask-gate-message') as HTMLElement;
		expect(panel.textContent).toContain(tr('ask.access_entitled'));
		expect(noteBox()).toBeNull();
	});

	it('null or an unknown access value: the plain panel', async () => {
		for (const access of [null, 'approved', '__proto__', 'constructor']) {
			statusMock.mockResolvedValue(closed('ai_disabled', access));
			const heading = await renderPanel();
			const panel = heading.closest('#ask-gate-message') as HTMLElement;
			expect(noteBox()).toBeNull();
			// No block at all: neither the form nor a (possibly empty) state message.
			expect({ access, form: panel.querySelector('form'), state: panel.querySelector('p[tabindex]') }).toEqual({
				access,
				form: null,
				state: null
			});
			expect(panel.textContent).not.toContain('requested access');
			cleanup();
		}
	});

	it('control: a known non-form state does render the state message the test above looks for', async () => {
		statusMock.mockResolvedValue(closed('ai_disabled', 'entitled'));
		const heading = await renderPanel();
		const panel = heading.closest('#ask-gate-message') as HTMLElement;
		expect(panel.querySelector('p[tabindex]')?.textContent).toContain(tr('ask.access_entitled'));
	});

	it('another closed reason never shows the block', async () => {
		statusMock.mockResolvedValue(closed('ai_global_budget', 'none'));
		render(AskPage);
		await screen.findByRole('heading', { name: tr('ask.paused_title') });
		expect(noteBox()).toBeNull();
	});
});

describe('/ask request access: sending', () => {
	it('success: exactly one POST with a null note, the pending view, focus on its message', async () => {
		statusMock.mockResolvedValue(closed('ai_disabled', 'none'));
		requestMock.mockResolvedValue({ state: 'created', requested_at: REQUESTED_AT, retry_after: null });
		await renderPanel();
		await fireEvent.click(requestButton() as HTMLElement);
		const message = await screen.findByText(/^Request sent\. You requested access on/);
		expect(requestMock).toHaveBeenCalledTimes(1);
		expect(requestMock).toHaveBeenCalledWith(null);
		expect(message.textContent).toContain(longDate(REQUESTED_AT));
		await waitFor(() => expect(document.activeElement).toBe(message));
		expect(message.getAttribute('tabindex')).toBe('-1');
		expect(message.closest('[aria-live],[role="status"],[role="alert"]')).toBeNull();
		expect(noteBox()).toBeNull();
		expect(statusMock).toHaveBeenCalledTimes(1);
	});

	it('sends the trimmed note', async () => {
		statusMock.mockResolvedValue(closed('ai_disabled', 'none'));
		requestMock.mockResolvedValue({ state: 'created', requested_at: REQUESTED_AT, retry_after: null });
		await renderPanel();
		await fireEvent.input(noteBox() as HTMLElement, { target: { value: '  weekly look-ahead  ' } });
		await fireEvent.click(requestButton() as HTMLElement);
		await screen.findByText(/^Request sent\./);
		expect(requestMock).toHaveBeenCalledWith('weekly look-ahead');
	});

	it('a double click sends one request, with the button disabled and busy meanwhile', async () => {
		statusMock.mockResolvedValue(closed('ai_disabled', 'none'));
		let resolve: (v: unknown) => void = () => undefined;
		requestMock.mockImplementation(() => new Promise((r) => (resolve = r)));
		await renderPanel();
		const button = requestButton() as HTMLButtonElement;
		// Both clicks land before the DOM updates, so only the guard can stop the second.
		void fireEvent.click(button);
		void fireEvent.click(button);
		await waitFor(() => expect(button.disabled).toBe(true));
		expect(button.textContent?.trim()).toBe(tr('ask.access_requesting'));
		expect(requestMock).toHaveBeenCalledTimes(1);
		resolve({ state: 'created', requested_at: REQUESTED_AT, retry_after: null });
		await screen.findByText(/^Request sent\./);
		expect(requestMock).toHaveBeenCalledTimes(1);
	});

	it('timeout, then the status says pending: the pending view', async () => {
		statusMock
			.mockResolvedValueOnce(closed('ai_disabled', 'none'))
			.mockResolvedValueOnce(closed('ai_disabled', 'pending', { access_requested_at: REQUESTED_AT }));
		requestMock.mockRejectedValue(new TimeoutError());
		await renderPanel();
		await fireEvent.click(requestButton() as HTMLElement);
		const message = await screen.findByText(/You requested access on/);
		expect(requestMock).toHaveBeenCalledTimes(1);
		expect(statusMock).toHaveBeenCalledTimes(2);
		expect(noteBox()).toBeNull();
		expect(screen.queryByRole('alert')).toBeNull();
		await waitFor(() => expect(document.activeElement).toBe(message));
	});

	it('timeout, then the status still says none: form and note kept, amber alert, focus on the button', async () => {
		statusMock.mockResolvedValue(closed('ai_disabled', 'none'));
		requestMock.mockRejectedValue(new DOMException('signal timed out', 'TimeoutError'));
		await renderPanel();
		await fireEvent.input(noteBox() as HTMLElement, { target: { value: 'my note' } });
		await fireEvent.click(requestButton() as HTMLElement);
		const alert = await screen.findByRole('alert');
		expect(alert.textContent).toContain(tr('ask.access_unconfirmed_resend'));
		expect(alert.className).toContain('amber');
		expect(alert.className).not.toContain('red');
		expect((noteBox() as HTMLTextAreaElement).value).toBe('my note');
		expect(statusMock).toHaveBeenCalledTimes(2);
		await waitFor(() => expect(document.activeElement).toBe(requestButton()));
	});

	it('timeout, then the status cannot be read: the panel stays (never "Temporarily unavailable")', async () => {
		statusMock
			.mockResolvedValueOnce(closed('ai_not_entitled', 'none'))
			.mockRejectedValueOnce(new Error('network'));
		requestMock.mockRejectedValue(new ApiError('bad gateway', 502, null));
		await renderPanel();
		await fireEvent.input(noteBox() as HTMLElement, { target: { value: 'kept' } });
		await fireEvent.click(requestButton() as HTMLElement);
		const alert = await screen.findByRole('alert');
		expect(alert.textContent).toContain(tr('ask.access_unconfirmed_reload'));
		expect(screen.getByRole('heading', { name: tr('ask.access_title') })).toBeTruthy();
		expect(screen.queryByRole('heading', { name: tr('ask.unavailable_title') })).toBeNull();
		expect((noteBox() as HTMLTextAreaElement).value).toBe('kept');
	});

	it('timeout, then the status has no access value: nothing confirmed, the form stays', async () => {
		statusMock
			.mockResolvedValueOnce(closed('ai_disabled', 'none'))
			.mockResolvedValueOnce(closed('ai_disabled', null));
		requestMock.mockRejectedValue(new TypeError('Failed to fetch'));
		await renderPanel();
		await fireEvent.click(requestButton() as HTMLElement);
		const alert = await screen.findByRole('alert');
		expect(alert.textContent).toContain(tr('ask.access_unconfirmed_reload'));
		expect(noteBox()).toBeTruthy();
	});

	it('401: the sign-in gate', async () => {
		statusMock.mockResolvedValue(closed('ai_disabled', 'none'));
		requestMock.mockRejectedValue(new ApiError('expired', 401, null));
		await renderPanel();
		await fireEvent.click(requestButton() as HTMLElement);
		await screen.findByRole('heading', { name: tr('ask.signin_title') });
		expect(noteBox()).toBeNull();
	});

	it('429: the rate-limit alert, form and note kept, focus back on the button', async () => {
		statusMock.mockResolvedValue(closed('ai_disabled', 'none'));
		requestMock.mockRejectedValue(new ApiError('Rate limit exceeded', 429, null));
		await renderPanel();
		await fireEvent.input(noteBox() as HTMLElement, { target: { value: 'still here' } });
		await fireEvent.click(requestButton() as HTMLElement);
		const alert = await screen.findByRole('alert');
		expect(alert.textContent).toContain(tr('error.rate_limited'));
		expect(alert.textContent).not.toContain('Rate limit exceeded');
		expect((noteBox() as HTMLTextAreaElement).value).toBe('still here');
		expect(statusMock).toHaveBeenCalledTimes(1);
		await waitFor(() => expect(document.activeElement).toBe(requestButton()));
	});

	it('another 4xx: "could not be sent", form kept, no status reload', async () => {
		statusMock.mockResolvedValue(closed('ai_disabled', 'none'));
		requestMock.mockRejectedValue(new ApiError('raw 422 text', 422, null));
		await renderPanel();
		await fireEvent.click(requestButton() as HTMLElement);
		const alert = await screen.findByRole('alert');
		expect(alert.textContent).toContain(tr('ask.access_request_failed'));
		expect(alert.textContent).not.toContain('raw 422 text');
		expect(noteBox()).toBeTruthy();
		expect(statusMock).toHaveBeenCalledTimes(1);
	});

	it('the POST answers entitled: the status is reloaded', async () => {
		statusMock
			.mockResolvedValueOnce(closed('ai_disabled', 'none'))
			.mockResolvedValueOnce(closed('ai_disabled', 'entitled'));
		requestMock.mockResolvedValue({ state: 'entitled', requested_at: null, retry_after: null });
		const heading = await renderPanel();
		await fireEvent.click(requestButton() as HTMLElement);
		await waitFor(() => expect(statusMock).toHaveBeenCalledTimes(2));
		const panel = heading.closest('#ask-gate-message') as HTMLElement;
		await waitFor(() => expect(panel.textContent).toContain(tr('ask.access_entitled')));
		expect(noteBox()).toBeNull();
	});
});

describe('/ask open states (control)', () => {
	it('available: the composer is there and no access panel', async () => {
		statusMock.mockResolvedValue(
			status(true, null, { daily_limit: 20, used_today: 3, remaining_today: 17 })
		);
		render(AskPage);
		await waitFor(() => expect(composer()).toBeTruthy());
		expect(screen.queryByRole('heading', { name: tr('ask.access_title') })).toBeNull();
		expect(noteBox()).toBeNull();
	});

	it('daily quota: the composer stays, disabled and described by the message', async () => {
		statusMock.mockResolvedValue(
			status(false, 'ai_daily_quota', { daily_limit: 20, used_today: 20, remaining_today: 0 })
		);
		render(AskPage);
		await waitFor(() => expect(composer()).toBeTruthy());
		const input = composer() as HTMLInputElement;
		expect(input.disabled).toBe(true);
		expect(input.getAttribute('aria-describedby')).toBe('ask-gate-message');
	});
});
