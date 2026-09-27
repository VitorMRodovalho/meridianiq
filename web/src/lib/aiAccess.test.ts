// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// The "request access" mapping: the block shows only for the two reasons an
// approval can change and the four access values the contract lists; anything
// else is the plain panel. Dates read in the viewer's local time, a failed
// request is classified without ever returning server text, and every key the
// block can show exists in every locale.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// api.ts creates the Supabase client at import; the error classes do not need it.
vi.mock('./supabase', () => ({ supabase: {} }));

import { ApiError, TimeoutError } from './api';
import {
	ACCESS_ALERT_KEYS,
	ACCESS_FORM_KEYS,
	AI_ACCESS_MESSAGE_KEYS,
	accessFromRequestOutcome,
	accessLookupFailed,
	accessMessage,
	accessView,
	classifyAccessRequestError,
	formatAccessDate,
	isAccessReason
} from './aiAccess';
import en from './i18n/en';
import ptBR from './i18n/pt-BR';
import es from './i18n/es';

const tEn = (key: string): string => en[key] ?? key;

const SERVER_TEXT = 'raw server text that must never be shown';

const STATES = ['entitled', 'pending', 'dismissed', 'none'] as const;
const ACCESS_REASONS = ['ai_disabled', 'ai_not_entitled'];
const OTHER_REASONS = [
	'ai_global_budget',
	'ai_session_required',
	'ai_daily_quota',
	'ai_account_budget',
	'ai_something_new',
	'__proto__',
	'constructor',
	null
];

describe('accessView', () => {
	for (const reason of ACCESS_REASONS) {
		for (const access of STATES) {
			it(`${reason} + ${access} → ${access}`, () => {
				expect(accessView({ available: false, reason, access })).toBe(access);
			});
		}
	}

	it('is ignored for every other reason', () => {
		for (const reason of OTHER_REASONS) {
			for (const access of STATES) {
				expect({ reason, access, got: accessView({ available: false, reason, access }) }).toEqual({
					reason,
					access,
					got: null
				});
			}
		}
	});

	it('is ignored when the feature is available', () => {
		for (const access of STATES) {
			expect(accessView({ available: true, reason: null, access })).toBeNull();
			// Even a contradictory body never shows a request form next to the composer.
			expect(accessView({ available: true, reason: 'ai_disabled', access })).toBeNull();
		}
	});

	it('unknown, null, missing and inherited values are the plain panel', () => {
		for (const access of [
			null,
			undefined,
			'',
			'approved',
			'NONE',
			'Pending',
			'__proto__',
			'constructor',
			'toString',
			'hasOwnProperty',
			1,
			true,
			{},
			['none']
		]) {
			expect(accessView({ available: false, reason: 'ai_disabled', access })).toBeNull();
		}
		// An API that predates the field sends no `access` at all.
		expect(accessView({ available: false, reason: 'ai_not_entitled' })).toBeNull();
		expect(accessView(null)).toBeNull();
		expect(accessView(undefined)).toBeNull();
	});

	it('isAccessReason ignores inherited names', () => {
		expect(isAccessReason('ai_disabled')).toBe(true);
		expect(isAccessReason('ai_not_entitled')).toBe(true);
		for (const r of ['__proto__', 'constructor', 'toString', '', null, undefined, 1]) {
			expect(isAccessReason(r)).toBe(false);
		}
	});
});

describe('accessLookupFailed', () => {
	it('is true when a status that carries the block has no usable access value', () => {
		for (const access of [null, undefined, 'weird', '__proto__']) {
			expect(accessLookupFailed({ available: false, reason: 'ai_disabled', access })).toBe(true);
		}
		expect(accessLookupFailed({ available: false, reason: 'ai_not_entitled' })).toBe(true);
	});

	it('is false for a known value, another reason, an available status and no status', () => {
		for (const access of STATES) {
			expect(accessLookupFailed({ available: false, reason: 'ai_disabled', access })).toBe(false);
		}
		expect(accessLookupFailed({ available: false, reason: 'ai_global_budget', access: null })).toBe(false);
		expect(accessLookupFailed({ available: true, reason: null, access: null })).toBe(false);
		expect(accessLookupFailed(null)).toBe(false);
	});
});

describe('accessFromRequestOutcome', () => {
	it('maps the four outcomes of the contract; created is a new pending request', () => {
		expect(accessFromRequestOutcome('created')).toBe('pending');
		expect(accessFromRequestOutcome('pending')).toBe('pending');
		expect(accessFromRequestOutcome('entitled')).toBe('entitled');
		expect(accessFromRequestOutcome('dismissed')).toBe('dismissed');
	});

	it('anything else is unknown (the page reloads the status)', () => {
		for (const s of ['none', 'approved', '__proto__', 'constructor', '', null, undefined, 1]) {
			expect(accessFromRequestOutcome(s)).toBeNull();
		}
	});
});

describe('formatAccessDate', () => {
	it('adds the local time of day when asked (a block ends at an exact moment)', () => {
		const withTime = formatAccessDate('2026-10-27T17:05:00Z', 'pt-BR', true);
		expect(withTime).not.toBeNull();
		expect(withTime).toContain('2026');
		expect(withTime).toMatch(/\d{1,2}:\d{2}/);
		expect(formatAccessDate('2026-10-27T17:05:00Z', 'pt-BR')).not.toMatch(/\d{1,2}:\d{2}/);
	});

	// Near midnight UTC, so the local day and the UTC day differ.
	const iso = '2026-09-27T01:30:00Z';
	let previousTz: string | undefined;

	beforeEach(() => {
		previousTz = process.env.TZ;
		process.env.TZ = 'America/Sao_Paulo';
	});
	afterEach(() => {
		if (previousTz === undefined) delete process.env.TZ;
		else process.env.TZ = previousTz;
	});

	it('uses the viewer local time zone, not UTC', () => {
		// Precondition: the runtime honoured the zone change, so the assertion below discriminates.
		expect(Intl.DateTimeFormat().resolvedOptions().timeZone).toBe('America/Sao_Paulo');
		const utc = new Date(iso).toLocaleDateString('en-US', { dateStyle: 'long', timeZone: 'UTC' });
		expect(utc).toBe('September 27, 2026');
		expect(formatAccessDate(iso, 'en-US')).toBe('September 26, 2026');
	});

	it('follows the locale', () => {
		expect(formatAccessDate('2026-09-27T15:00:00Z', 'pt-BR')).toBe('27 de setembro de 2026');
		expect(formatAccessDate('2026-09-27T15:00:00Z', 'es')).toBe('27 de septiembre de 2026');
	});

	it('is null when missing or unreadable', () => {
		for (const v of [null, undefined, '', 'not a date', '2026-13-45']) {
			expect(formatAccessDate(v, 'en-US')).toBeNull();
		}
	});
});

describe('accessMessage', () => {
	const requested = '2026-09-20T15:00:00Z';
	const retry = '2026-10-20T15:00:00Z';
	const long = (iso: string) => new Date(iso).toLocaleDateString('en-US', { dateStyle: 'long' });

	it('pending: the day it was requested, with "Request sent." only right after a submit', () => {
		const msg = accessMessage(tEn, 'pending', requested, null, 'en-US');
		expect(msg).toContain(long(requested));
		expect(msg).not.toContain('{date}');
		expect(msg).toMatch(/waiting for review/);
		expect(msg.startsWith(en['ask.access_sent'])).toBe(false);
		const sent = accessMessage(tEn, 'pending', requested, null, 'en-US', true);
		expect(sent.startsWith(`${en['ask.access_sent']} `)).toBe(true);
	});

	it('pending without a readable date uses the no-date text', () => {
		expect(accessMessage(tEn, 'pending', null, null, 'en-US')).toBe(en['ask.access_pending_no_date']);
		expect(accessMessage(tEn, 'pending', 'garbage', null, 'en-US')).toBe(en['ask.access_pending_no_date']);
	});

	it('dismissed: the day a new request can be sent, from retry_after (not requested_at)', () => {
		const msg = accessMessage(tEn, 'dismissed', requested, retry, 'en-US');
		expect(msg).toContain(long(retry));
		expect(msg).not.toContain(long(requested));
		expect(accessMessage(tEn, 'dismissed', requested, null, 'en-US')).toBe(
			en['ask.access_dismissed_no_date']
		);
	});

	it('entitled, none and no block', () => {
		expect(accessMessage(tEn, 'entitled', null, null, 'en-US')).toBe(en['ask.access_entitled']);
		expect(accessMessage(tEn, 'none', requested, retry, 'en-US')).toBe('');
		expect(accessMessage(tEn, null, requested, retry, 'en-US')).toBe('');
	});
});

describe('classifyAccessRequestError', () => {
	const apiError = (status: number, code: string | null) => new ApiError(SERVER_TEXT, status, code);

	it('401 is the sign-in gate, whatever the body says', () => {
		expect(classifyAccessRequestError(apiError(401, null))).toEqual({ kind: 'signin' });
		expect(classifyAccessRequestError(apiError(401, 'ai_session_required'))).toEqual({ kind: 'signin' });
	});

	it('429 keeps the form with the rate-limit message', () => {
		expect(classifyAccessRequestError(apiError(429, null))).toEqual({
			kind: 'refused',
			key: ACCESS_ALERT_KEYS.rateLimited
		});
		expect(ACCESS_ALERT_KEYS.rateLimited).toBe('error.rate_limited');
	});

	it('any other 4xx keeps the form with "could not be sent"', () => {
		for (const [status, code] of [
			[400, null],
			[403, 'ai_session_required'],
			[404, null],
			[409, null],
			[422, null]
		] as const) {
			expect(classifyAccessRequestError(apiError(status, code))).toEqual({
				kind: 'refused',
				key: ACCESS_ALERT_KEYS.failed
			});
		}
	});

	it('a timeout (both TimeoutError kinds), a network error and a 5xx are an unknown outcome', () => {
		for (const err of [
			new TimeoutError(),
			new DOMException('signal timed out', 'TimeoutError'),
			new TypeError('Failed to fetch'),
			apiError(500, 'ai_request_unavailable'),
			apiError(502, null),
			apiError(503, null),
			'a string',
			null,
			undefined
		]) {
			expect(classifyAccessRequestError(err)).toEqual({ kind: 'unknown' });
		}
	});

	it('never returns the server message', () => {
		const all = [400, 401, 403, 404, 422, 429, 500, 502, 503].flatMap((s) =>
			[null, 'ai_session_required', 'ai_request_unavailable', 'x'].map((c) =>
				classifyAccessRequestError(apiError(s, c))
			)
		);
		expect(JSON.stringify(all)).not.toContain(SERVER_TEXT);
	});
});

describe('AI_ACCESS_MESSAGE_KEYS', () => {
	it('every key exists in every locale', () => {
		for (const [name, dict] of Object.entries({ en, 'pt-BR': ptBR, es })) {
			const missing = AI_ACCESS_MESSAGE_KEYS.filter((key) => !(key in dict));
			expect({ locale: name, missing }).toEqual({ locale: name, missing: [] });
		}
	});

	it('lists the form, the states and every alert the page can show', () => {
		for (const key of [
			...Object.values(ACCESS_FORM_KEYS),
			...Object.values(ACCESS_ALERT_KEYS),
			'ask.access_pending',
			'ask.access_pending_no_date',
			'ask.access_sent',
			'ask.access_dismissed',
			'ask.access_dismissed_no_date',
			'ask.access_entitled'
		]) {
			expect(AI_ACCESS_MESSAGE_KEYS).toContain(key);
		}
		const produced = new Set<string>();
		for (const s of [400, 401, 403, 422, 429, 500]) {
			const out = classifyAccessRequestError(new ApiError('x', s, null));
			if (out.kind === 'refused') produced.add(out.key);
		}
		for (const key of produced) expect(AI_ACCESS_MESSAGE_KEYS).toContain(key);
	});

	it('the dated templates carry {date} in every locale, and no other key has a placeholder', () => {
		const dated = new Set(['ask.access_pending', 'ask.access_dismissed']);
		for (const dict of [en, ptBR, es]) {
			for (const key of AI_ACCESS_MESSAGE_KEYS) {
				const slots = [...dict[key].matchAll(/\{(\w+)\}/g)].map((m) => m[1]);
				expect({ key, slots }).toEqual({ key, slots: dated.has(key) ? ['date'] : [] });
			}
		}
	});
});
