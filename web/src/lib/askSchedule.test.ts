// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// askSchedule() makes exactly one fetch. `request()` retries 502/503, network
// errors and timeouts, and each retry of POST /ask could be another billed
// model call, so this helper must not inherit that loop.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./supabase', () => ({
	supabase: {
		auth: {
			getSession: async () => ({ data: { session: { access_token: 'test-token' } } })
		}
	}
}));

import { ApiError, askSchedule, getAiStatus } from './api';

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
