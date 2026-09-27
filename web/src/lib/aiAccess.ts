// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// "Request access" on the /ask closed panel: turns the `access` fields of
// `GET /api/v1/ai/status` and the outcome of `POST /api/v1/ai/access-request`
// into what the panel shows.
//
// Fail-safe to the plain panel: the access block renders only for the two
// reasons an operator's approval can change (`ai_disabled`, `ai_not_entitled`)
// and only for an access value this build knows. A missing field (an API that
// predates it), a null (the lookup failed) or anything else shows the panel
// without a form, never a guess.
//
// Server text (`ApiError.message`, response bodies) is never returned.
//
// Pure: no stores, no fetch, and no import of `api.ts` (which creates the
// Supabase client at import). Errors are read structurally, which the tests
// check against the real `ApiError` / `TimeoutError` classes.

import { interpolate } from './aiGate';

/** What the account's access request looks like to the /ask panel. */
export type AiAccessState = 'entitled' | 'pending' | 'dismissed' | 'none';

const ACCESS_STATES: Record<string, AiAccessState> = {
	entitled: 'entitled',
	pending: 'pending',
	dismissed: 'dismissed',
	none: 'none'
};

/** The only reasons for which asking the administrators can change anything. */
const ACCESS_REASONS: Record<string, true> = {
	ai_disabled: true,
	ai_not_entitled: true
};

/** What each successful POST outcome means for the panel. */
const REQUEST_OUTCOMES: Record<string, AiAccessState> = {
	created: 'pending',
	pending: 'pending',
	entitled: 'entitled',
	dismissed: 'dismissed'
};

function own<T>(map: Record<string, T>, key: unknown): T | null {
	return typeof key === 'string' && Object.prototype.hasOwnProperty.call(map, key) ? map[key] : null;
}

/** True for the reasons that carry an access block. */
export function isAccessReason(reason: unknown): boolean {
	return own(ACCESS_REASONS, reason) !== null;
}

/**
 * The access block for a status, or null for the plain panel.
 *
 * Null when the status is missing or available, when the reason is not one an
 * approval can change, and when `access` is missing, null or not one of the
 * four known values (including inherited names such as `__proto__`).
 */
export function accessView(
	status: { available?: unknown; reason?: unknown; access?: unknown } | null | undefined
): AiAccessState | null {
	if (!status || status.available === true) return null;
	if (!isAccessReason(status.reason)) return null;
	return own(ACCESS_STATES, status.access);
}

/**
 * True when the status is one that carries an access block but the access
 * value is missing or unknown (the lookup failed, or the API predates it).
 * Reading such a status confirms nothing about a request just sent, so the
 * page keeps what it shows instead of replacing it with the plain panel.
 */
export function accessLookupFailed(
	status: { available?: unknown; reason?: unknown; access?: unknown } | null | undefined
): boolean {
	return (
		!!status && status.available !== true && isAccessReason(status.reason) && accessView(status) === null
	);
}

/**
 * The state a successful `POST /ai/access-request` moves the panel to
 * (`created` is a new pending request), or null for an outcome this build
 * does not know, which the page resolves by reloading the status.
 */
export function accessFromRequestOutcome(state: unknown): AiAccessState | null {
	return own(REQUEST_OUTCOMES, state);
}

/**
 * A date in the viewer's own time zone ("September 27, 2026"), or null when
 * missing or unreadable. `formatDate` in i18n/format.ts is not used here on
 * purpose: it forces UTC, and the day a request was made must read in local time.
 */
export function formatAccessDate(iso: string | null | undefined, locale: string): string | null {
	if (!iso) return null;
	const parsed = new Date(iso);
	if (Number.isNaN(parsed.getTime())) return null;
	try {
		return parsed.toLocaleDateString(locale, { dateStyle: 'long' });
	} catch {
		return null;
	}
}

const MESSAGE_KEYS = {
	pending: 'ask.access_pending',
	pendingNoDate: 'ask.access_pending_no_date',
	sent: 'ask.access_sent',
	dismissed: 'ask.access_dismissed',
	dismissedNoDate: 'ask.access_dismissed_no_date',
	entitled: 'ask.access_entitled'
} as const;

/** i18n keys of the request form (label, hint, button and its busy label). */
export const ACCESS_FORM_KEYS = {
	label: 'ask.access_note_label',
	hint: 'ask.access_note_hint',
	submit: 'ask.access_request',
	submitting: 'ask.access_requesting'
} as const;

/** i18n keys of the outcomes of a request that did not end in a new state. */
export const ACCESS_ALERT_KEYS = {
	/** A 4xx other than 401 and 429: the request was refused as sent. */
	failed: 'ask.access_request_failed',
	rateLimited: 'error.rate_limited',
	/** The outcome was unknown and the reloaded status still says `none`. */
	unconfirmedResend: 'ask.access_unconfirmed_resend',
	/** The outcome was unknown and the status could not be reloaded. */
	unconfirmedReload: 'ask.access_unconfirmed_reload'
} as const;

/** Every i18n key this module or the access block can show (tested against the locales). */
export const AI_ACCESS_MESSAGE_KEYS: readonly string[] = [
	...Object.values(MESSAGE_KEYS),
	...Object.values(ACCESS_FORM_KEYS),
	...Object.values(ACCESS_ALERT_KEYS)
];

type Translate = (key: string) => string;

/**
 * The sentence for a non-form state: when the request was made (pending),
 * from when a new one can be sent (dismissed, from `retry_after`), or that the
 * account is already approved. Empty for `none` and for no block.
 * `justSent` prefixes "Request sent." right after a submit that recorded one.
 */
export function accessMessage(
	t: Translate,
	state: AiAccessState | null,
	requestedAt: string | null | undefined,
	retryAfter: string | null | undefined,
	locale: string,
	justSent = false
): string {
	if (state === 'pending') {
		const date = formatAccessDate(requestedAt, locale);
		const body = date
			? interpolate(t(MESSAGE_KEYS.pending), { date })
			: t(MESSAGE_KEYS.pendingNoDate);
		return justSent ? `${t(MESSAGE_KEYS.sent)} ${body}` : body;
	}
	if (state === 'dismissed') {
		const date = formatAccessDate(retryAfter, locale);
		return date
			? interpolate(t(MESSAGE_KEYS.dismissed), { date })
			: t(MESSAGE_KEYS.dismissedNoDate);
	}
	if (state === 'entitled') return t(MESSAGE_KEYS.entitled);
	return '';
}

/** What a failed `POST /ai/access-request` means for the panel. */
export type AccessRequestFailure =
	/** The session is gone: show the sign-in gate. */
	| { kind: 'signin' }
	/** Refused as sent (nothing was recorded): keep the form and the note, show `key`. */
	| { kind: 'refused'; key: string }
	/**
	 * Timeout, network error or 5xx: the request may have been recorded. The
	 * page reloads the status to find out instead of guessing.
	 */
	| { kind: 'unknown' };

interface ErrorLike {
	name?: unknown;
	status?: unknown;
}

/**
 * Classify an error thrown by `requestAiAccess()`. Reads only the status and
 * the error name, never the message.
 */
export function classifyAccessRequestError(err: unknown): AccessRequestFailure {
	const e: ErrorLike = err !== null && typeof err === 'object' ? (err as ErrorLike) : {};
	// Both api.ts's TimeoutError and the DOMException from AbortSignal.timeout
	// carry this name.
	if (e.name === 'TimeoutError') return { kind: 'unknown' };
	const status = typeof e.status === 'number' ? e.status : null;
	if (status === 401) return { kind: 'signin' };
	// The per-address rate limiter answers before the route runs.
	if (status === 429) return { kind: 'refused', key: ACCESS_ALERT_KEYS.rateLimited };
	if (status !== null && status >= 400 && status < 500) {
		return { kind: 'refused', key: ACCESS_ALERT_KEYS.failed };
	}
	// 5xx, a network error (TypeError, no status), or anything unrecognised.
	return { kind: 'unknown' };
}
