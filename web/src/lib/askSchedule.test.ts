// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// askSchedule(), grantAiAccess() and revokeAiAccess() make exactly one fetch.
// `request()` retries 502/503, network errors and timeouts: each retry of
// POST /ask could be another billed model call, and a revoke repeated after the
// first one took effect answers 404 ("no active AI access") for an account that
// had it. None of the three may inherit that loop.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./supabase', () => ({
	supabase: {
		auth: {
			getSession: async () => ({ data: { session: { access_token: 'test-token' } } })
		}
	}
}));

import { ApiError, askSchedule, getAiStatus, grantAiAccess, revokeAiAccess } from './api';

function jsonResponse(status: number, body: unknown): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

describe('askSchedule', () => {
	let fetchMock: ReturnType<typeof vi.fn>;

	beforeEach(() => {
		fetchMock = vi.fn();
		vi.stubGlobal('fetch', fetchMock);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('does exactly one fetch on a 502 and surfaces the error code', async () => {
		fetchMock.mockResolvedValue(
			jsonResponse(502, { detail: { error_code: 'ai_upstream_failed', message: 'upstream' } })
		);
		const err = await askSchedule('p1', 'What is the critical path?').catch((e: unknown) => e);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(err).toBeInstanceOf(ApiError);
		expect((err as ApiError).status).toBe(502);
		expect((err as ApiError).errorCode).toBe('ai_upstream_failed');
	});

	it('does exactly one fetch on a bare 503', async () => {
		fetchMock.mockResolvedValue(new Response('', { status: 503 }));
		await expect(askSchedule('p1', 'q')).rejects.toBeInstanceOf(ApiError);
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	it('does exactly one fetch on a network error', async () => {
		fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
		await expect(askSchedule('p1', 'q')).rejects.toBeInstanceOf(TypeError);
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	it('turns the abort timeout into TimeoutError, with one fetch', async () => {
		fetchMock.mockRejectedValue(new DOMException('signal timed out', 'TimeoutError'));
		const err = await askSchedule('p1', 'q').catch((e: unknown) => e);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect((err as Error).name).toBe('TimeoutError');
		expect(err).toBeInstanceOf(ApiError);
	});

	it('waits 90 s, above the server budget for one answer (45 s call + 5 s connect + load and ledger)', async () => {
		const timeoutSpy = vi.spyOn(AbortSignal, 'timeout');
		try {
			fetchMock.mockResolvedValue(
				jsonResponse(200, { question: 'q', answer: 'a', model: 'm', tokens_used: 1, remaining_today: 1 })
			);
			await askSchedule('p1', 'q');
			expect(timeoutSpy).toHaveBeenCalledTimes(1);
			expect(timeoutSpy).toHaveBeenCalledWith(90_000);
		} finally {
			timeoutSpy.mockRestore();
		}
	});

	it('posts the question with the session token and a timeout signal', async () => {
		fetchMock.mockResolvedValue(
			jsonResponse(200, {
				question: 'q',
				answer: 'a',
				model: 'm',
				tokens_used: 10,
				remaining_today: 4
			})
		);
		const res = await askSchedule('p/1', 'q');
		expect(res.remaining_today).toBe(4);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(url).toBe('/api/v1/projects/p%2F1/ask');
		expect(init.method).toBe('POST');
		expect(JSON.parse(init.body as string)).toEqual({ question: 'q' });
		const headers = init.headers as Record<string, string>;
		expect(headers.Authorization).toBe('Bearer test-token');
		expect(headers['Content-Type']).toBe('application/json');
		expect(init.signal).toBeInstanceOf(AbortSignal);
	});

	// Negative control: the shared helper does retry a 502, so the single-fetch
	// assertions above are measuring a difference, not a mocked fetch that could
	// never be called twice.
	it('control: getAiStatus goes through request() and retries a 502', async () => {
		vi.useFakeTimers();
		try {
			fetchMock
				.mockResolvedValueOnce(new Response('', { status: 502 }))
				.mockResolvedValueOnce(
					jsonResponse(200, {
						available: true,
						reason: null,
						daily_limit: 20,
						used_today: 0,
						remaining_today: 20,
						resets_at: null
					})
				);
			const pending = getAiStatus();
			await vi.runAllTimersAsync();
			const status = await pending;
			expect(status.available).toBe(true);
			expect(fetchMock).toHaveBeenCalledTimes(2);
		} finally {
			vi.useRealTimers();
		}
	});
});

describe('grantAiAccess / revokeAiAccess', () => {
	let fetchMock: ReturnType<typeof vi.fn>;

	beforeEach(() => {
		fetchMock = vi.fn();
		vi.stubGlobal('fetch', fetchMock);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	const grantBody = { email: 'a@example.com', daily_questions: null, monthly_budget_usd: null, note: null };

	it('grant: exactly one fetch on a bare 502', async () => {
		fetchMock.mockResolvedValue(new Response('', { status: 502 }));
		const err = await grantAiAccess(grantBody).catch((e: unknown) => e);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(err).toBeInstanceOf(ApiError);
		expect((err as ApiError).status).toBe(502);
	});

	it('revoke: exactly one fetch on a bare 502', async () => {
		fetchMock.mockResolvedValue(new Response('', { status: 502 }));
		const err = await revokeAiAccess('u-1').catch((e: unknown) => e);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(err).toBeInstanceOf(ApiError);
		expect((err as ApiError).status).toBe(502);
	});

	it('grant and revoke: exactly one fetch on a 503, a network error and a timeout', async () => {
		const failures: (() => void)[] = [
			() => fetchMock.mockResolvedValue(new Response('', { status: 503 })),
			() => fetchMock.mockRejectedValue(new TypeError('Failed to fetch')),
			() => fetchMock.mockRejectedValue(new DOMException('signal timed out', 'TimeoutError'))
		];
		for (const arrange of failures) {
			for (const call of [() => grantAiAccess(grantBody), () => revokeAiAccess('u-1')]) {
				fetchMock.mockReset();
				arrange();
				await call().catch(() => undefined);
				expect(fetchMock).toHaveBeenCalledTimes(1);
			}
		}
	});

	it('a timed-out revoke throws TimeoutError', async () => {
		fetchMock.mockRejectedValue(new DOMException('signal timed out', 'TimeoutError'));
		const err = await revokeAiAccess('u-1').catch((e: unknown) => e);
		expect((err as Error).name).toBe('TimeoutError');
		expect(err).toBeInstanceOf(ApiError);
	});

	it('grant posts JSON with the session token; revoke sends DELETE to the encoded id', async () => {
		fetchMock.mockResolvedValueOnce(
			jsonResponse(200, {
				user_id: 'u-1',
				email: null,
				active: true,
				granted_at: null,
				revoked_at: null,
				daily_questions: null,
				monthly_budget_usd: null,
				note: null,
				used_today: 0,
				spent_month_usd: '0.00'
			})
		);
		const granted = await grantAiAccess(grantBody);
		expect(granted.email).toBeNull();
		const [grantUrl, grantInit] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(grantUrl).toBe('/api/v1/superadmin/ai/entitlements');
		expect(grantInit.method).toBe('POST');
		expect(JSON.parse(grantInit.body as string)).toEqual(grantBody);
		const grantHeaders = grantInit.headers as Record<string, string>;
		expect(grantHeaders.Authorization).toBe('Bearer test-token');
		expect(grantHeaders['Content-Type']).toBe('application/json');
		expect(grantInit.signal).toBeInstanceOf(AbortSignal);

		fetchMock.mockResolvedValueOnce(jsonResponse(200, { revoked: true }));
		await expect(revokeAiAccess('u/1')).resolves.toEqual({ revoked: true });
		const [revokeUrl, revokeInit] = fetchMock.mock.calls[1] as [string, RequestInit];
		expect(revokeUrl).toBe('/api/v1/superadmin/ai/entitlements/u%2F1');
		expect(revokeInit.method).toBe('DELETE');
		expect((revokeInit.headers as Record<string, string>).Authorization).toBe('Bearer test-token');
	});

	it('a 404 revoke surfaces its error code', async () => {
		fetchMock.mockResolvedValue(
			jsonResponse(404, { detail: { error_code: 'ai_entitlement_not_found', message: 'x' } })
		);
		const err = await revokeAiAccess('u-1').catch((e: unknown) => e);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect((err as ApiError).errorCode).toBe('ai_entitlement_not_found');
	});
});
