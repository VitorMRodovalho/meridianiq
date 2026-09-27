// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// The AI gate mapping: every reason and every /ask failure the API contract
// lists becomes a translated message, anything else fails closed to the
// generic one, and no server text is ever returned.

import { describe, expect, it, vi } from 'vitest';

// api.ts creates the Supabase client at import; the error classes do not need it.
vi.mock('./supabase', () => ({ supabase: {} }));

import { ApiError, TimeoutError } from './api';
import {
	AI_GATE_MESSAGE_KEYS,
	AI_UNAVAILABLE_KEY,
	classifyAskError,
	formatResetTime,
	gateMessage,
	gateView,
	interpolate,
	reasonView,
	remainingMessage
} from './aiGate';
import en from './i18n/en';
import ptBR from './i18n/pt-BR';
import es from './i18n/es';

const tEn = (key: string): string => en[key] ?? key;

const SERVER_TEXT = 'raw server text that must never be shown';

function apiError(status: number, errorCode: string | null): ApiError {
	return new ApiError(SERVER_TEXT, status, errorCode);
}

describe('reasonView / gateView', () => {
	const cases: [string, 'closed' | 'exhausted', string, string | null][] = [
		['ai_not_entitled', 'closed', 'ask.reason_not_entitled', 'ask.access_title'],
		['ai_disabled', 'closed', 'ask.reason_disabled', 'ask.access_title'],
		['ai_global_budget', 'closed', 'ask.reason_global_budget', 'ask.paused_title'],
		['ai_session_required', 'closed', 'ask.reason_session_required', 'ask.signin_title'],
		['ai_daily_quota', 'exhausted', 'ask.reason_daily_quota', null],
		['ai_account_budget', 'exhausted', 'ask.reason_account_budget', null]
	];

	for (const [reason, mode, key, titleKey] of cases) {
		it(`${reason} → ${mode} with ${key}`, () => {
			expect(reasonView(reason)).toEqual({ mode, reason, key, titleKey });
			expect(gateView({ available: false, reason })).toEqual({ mode, reason, key, titleKey });
		});
	}

	it('not approved and not open yet read the same to the user: early access', () => {
		expect(reasonView('ai_not_entitled').titleKey).toBe(reasonView('ai_disabled').titleKey);
	});

	it('fails closed on an unknown reason', () => {
		expect(reasonView('ai_something_new')).toEqual({
			mode: 'closed',
			reason: null,
			key: AI_UNAVAILABLE_KEY,
			titleKey: 'ask.unavailable_title'
		});
	});

	it('fails closed on inherited object keys', () => {
		expect(reasonView('constructor').key).toBe(AI_UNAVAILABLE_KEY);
		expect(reasonView('__proto__').key).toBe(AI_UNAVAILABLE_KEY);
	});

	it('fails closed when unavailable without a reason', () => {
		expect(gateView({ available: false, reason: null }).mode).toBe('closed');
	});

	it('fails closed when the status could not be loaded', () => {
		expect(gateView(null)).toEqual({
			mode: 'closed',
			reason: null,
			key: AI_UNAVAILABLE_KEY,
			titleKey: 'ask.unavailable_title'
		});
		expect(gateView(undefined).mode).toBe('closed');
	});

	it('opens only on an explicit available: true', () => {
		expect(gateView({ available: true, reason: null })).toEqual({
			mode: 'available',
			reason: null,
			key: null,
			titleKey: null
		});
		// A truthy non-boolean is not a yes.
		const loose = { available: 'yes' as unknown as boolean, reason: null };
		expect(gateView(loose).mode).toBe('closed');
	});
});

describe('classifyAskError', () => {
	const gateCodes: [number, string, 'closed' | 'exhausted'][] = [
		[403, 'ai_disabled', 'closed'],
		[403, 'ai_not_entitled', 'closed'],
		[403, 'ai_session_required', 'closed'],
		[429, 'ai_daily_quota', 'exhausted'],
		[429, 'ai_account_budget', 'exhausted'],
		[429, 'ai_global_budget', 'closed']
	];

	for (const [status, code, mode] of gateCodes) {
		it(`${status} ${code} → gate (${mode})`, () => {
			const out = classifyAskError(apiError(status, code));
			expect(out).toEqual({ kind: 'gate', view: reasonView(code) });
			if (out.kind === 'gate') expect(out.view.mode).toBe(mode);
		});
	}

	it('400 ai_prompt_too_large → prompt too large', () => {
		expect(classifyAskError(apiError(400, 'ai_prompt_too_large'))).toEqual({
			kind: 'error',
			key: 'ask.error_prompt_too_large'
		});
	});

	it('502 ai_upstream_failed → upstream failed', () => {
		expect(classifyAskError(apiError(502, 'ai_upstream_failed'))).toEqual({
			kind: 'error',
			key: 'ask.error_upstream_failed'
		});
	});

	it('502 without a code (proxy) → upstream failed', () => {
		expect(classifyAskError(apiError(502, null))).toEqual({
			kind: 'error',
			key: 'ask.error_upstream_failed'
		});
	});

	it('500 ai_ledger_unavailable → generic unavailable', () => {
		expect(classifyAskError(apiError(500, 'ai_ledger_unavailable'))).toEqual({
			kind: 'error',
			key: AI_UNAVAILABLE_KEY
		});
	});

	it('429 without a code (per-address limiter) → rate limited', () => {
		expect(classifyAskError(apiError(429, null))).toEqual({ kind: 'error', key: 'error.rate_limited' });
	});

	it('401 → sign in, even with a code in the body', () => {
		expect(classifyAskError(apiError(401, null))).toEqual({ kind: 'signin' });
		expect(classifyAskError(apiError(401, 'ai_not_entitled'))).toEqual({ kind: 'signin' });
	});

	it('404 → project unavailable', () => {
		expect(classifyAskError(apiError(404, null))).toEqual({
			kind: 'error',
			key: 'ask.error_project_unavailable'
		});
	});

	it('422 → invalid question', () => {
		expect(classifyAskError(apiError(422, null))).toEqual({
			kind: 'error',
			key: 'ask.error_invalid_question'
		});
	});

	it('TimeoutError (api.ts class and the AbortSignal DOMException) → ask timeout, not the generic retry', () => {
		expect(classifyAskError(new TimeoutError())).toEqual({ kind: 'error', key: 'ask.error_timeout' });
		const dom = new DOMException('signal timed out', 'TimeoutError');
		expect(classifyAskError(dom)).toEqual({ kind: 'error', key: 'ask.error_timeout' });
		// The generic message says "Please retry", which a call that may still be
		// billed must not say.
		expect(AI_GATE_MESSAGE_KEYS).toContain('ask.error_timeout');
		expect(AI_GATE_MESSAGE_KEYS).not.toContain('error.request_timeout');
	});

	it('fails closed on an unknown code, an unknown status, a network error and non-errors', () => {
		for (const err of [
			apiError(403, 'ai_something_new'),
			apiError(429, 'ai_something_new'),
			apiError(418, null),
			apiError(503, null),
			new TypeError('Failed to fetch'),
			'a string',
			null,
			undefined
		]) {
			expect(classifyAskError(err)).toEqual({ kind: 'error', key: AI_UNAVAILABLE_KEY });
		}
	});

	it('never returns the server message', () => {
		const all = [400, 401, 403, 404, 422, 429, 500, 502, 503].flatMap((s) =>
			[null, 'ai_disabled', 'ai_daily_quota', 'ai_upstream_failed', 'x'].map((c) =>
				classifyAskError(apiError(s, c))
			)
		);
		expect(JSON.stringify(all)).not.toContain(SERVER_TEXT);
	});
});

describe('messages', () => {
	it('every key the module can return exists in every locale', () => {
		for (const [name, dict] of Object.entries({ en, 'pt-BR': ptBR, es })) {
			const missing = AI_GATE_MESSAGE_KEYS.filter((key) => !(key in dict));
			expect({ locale: name, missing }).toEqual({ locale: name, missing: [] });
		}
	});

	it('every key produced by the views and the classifier is in the declared list', () => {
		const produced = new Set<string>();
		for (const r of [
			'ai_not_entitled',
			'ai_disabled',
			'ai_global_budget',
			'ai_session_required',
			'ai_daily_quota',
			'ai_account_budget',
			'unknown'
		]) {
			const key = reasonView(r).key;
			if (key) produced.add(key);
		}
		for (const s of [400, 401, 403, 404, 422, 429, 500, 502, 503]) {
			for (const c of [null, 'ai_prompt_too_large', 'ai_upstream_failed', 'ai_ledger_unavailable', 'x']) {
				const out = classifyAskError(apiError(s, c));
				if (out.kind === 'error') produced.add(out.key);
			}
		}
		const out = classifyAskError(new TimeoutError());
		if (out.kind === 'error') produced.add(out.key);
		for (const key of produced) expect(AI_GATE_MESSAGE_KEYS).toContain(key);
	});

	it('shows the daily reset time in local time, and a fallback without one', () => {
		const view = reasonView('ai_daily_quota');
		const iso = '2026-09-28T00:00:00Z';
		const expected = new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
		const msg = gateMessage(tEn, view, iso, 'en-US');
		expect(msg).toContain(expected);
		expect(msg).not.toContain('{time}');
		expect(gateMessage(tEn, view, null, 'en-US')).toBe(en['ask.reason_daily_quota_no_time']);
		expect(gateMessage(tEn, view, 'not a date', 'en-US')).toBe(en['ask.reason_daily_quota_no_time']);
	});

	it('renders other reasons as their plain message, and nothing when available', () => {
		expect(gateMessage(tEn, reasonView('ai_disabled'), null, 'en-US')).toBe(en['ask.reason_disabled']);
		expect(gateMessage(tEn, gateView({ available: true, reason: null }), null, 'en-US')).toBe('');
	});

	it('formatResetTime rejects missing and invalid instants', () => {
		expect(formatResetTime(null, 'en-US')).toBeNull();
		expect(formatResetTime('', 'en-US')).toBeNull();
		expect(formatResetTime('garbage', 'en-US')).toBeNull();
	});

	it('remainingMessage fills both placeholders, or is empty when a number is missing', () => {
		expect(remainingMessage(tEn, 3, 20)).toBe('3 of 20 questions left today');
		expect(remainingMessage(tEn, null, 20)).toBe('');
		expect(remainingMessage(tEn, 3, null)).toBe('');
	});

	it('interpolate is single-pass: a value containing a placeholder stays literal', () => {
		expect(interpolate('{a} and {b}', { a: '{b}', b: 'x' })).toBe('{b} and x');
		expect(interpolate('{a} {missing}', { a: '1' })).toBe('1 {missing}');
	});
});
