// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// Ask Your Schedule access gate: turns the `reason` from `GET /api/v1/ai/status`
// or a failed `POST /api/v1/projects/{id}/ask` into the i18n key the page shows.
//
// Fail-closed: a reason or an error this module does not recognise becomes the
// generic "unavailable" message, and an unrecognised status reason closes the
// composer. Server text (`ApiError.message`, response bodies) is never returned,
// so no raw error can reach the user through this path.
//
// Pure: no stores, no fetch, and no import of `api.ts` (which creates the
// Supabase client at import). Errors are read structurally, which the tests
// check against the real `ApiError` / `TimeoutError` classes.

/**
 * How the /ask page presents the current state.
 * - `available`: the composer is usable.
 * - `closed`: nothing on this page can change it (not approved, not open,
 *   paused): the project selector, the input and the suggestions are removed.
 * - `exhausted`: a quota ran out: the conversation stays, the composer is disabled.
 */
export type AiGateMode = 'available' | 'closed' | 'exhausted';

export interface GateView {
	mode: AiGateMode;
	/** The recognised reason code, or null (available, or not recognised). */
	reason: string | null;
	/** i18n key of the message, or null when available. */
	key: string | null;
}

/** The generic message for anything not recognised. */
export const AI_UNAVAILABLE_KEY = 'ask.unavailable';

const CLOSED_REASONS: Record<string, string> = {
	ai_not_entitled: 'ask.reason_not_entitled',
	ai_disabled: 'ask.reason_disabled',
	ai_global_budget: 'ask.reason_global_budget',
	ai_session_required: 'ask.reason_session_required'
};

const EXHAUSTED_REASONS: Record<string, string> = {
	ai_daily_quota: 'ask.reason_daily_quota',
	ai_account_budget: 'ask.reason_account_budget'
};

/** The daily-quota message when the reset time is unknown or unreadable. */
const DAILY_QUOTA_NO_TIME_KEY = 'ask.reason_daily_quota_no_time';

const ERROR_KEYS = {
	promptTooLarge: 'ask.error_prompt_too_large',
	upstreamFailed: 'ask.error_upstream_failed',
	projectUnavailable: 'ask.error_project_unavailable',
	invalidQuestion: 'ask.error_invalid_question',
	rateLimited: 'error.rate_limited',
	// Not the generic 'error.request_timeout' ("please retry"): the server may
	// still be answering, and the call may count toward today's limit.
	timeout: 'ask.error_timeout'
} as const;

/** Every i18n key this module can hand to a page (tested against the locales). */
export const AI_GATE_MESSAGE_KEYS: readonly string[] = [
	AI_UNAVAILABLE_KEY,
	...Object.values(CLOSED_REASONS),
	...Object.values(EXHAUSTED_REASONS),
	DAILY_QUOTA_NO_TIME_KEY,
	...Object.values(ERROR_KEYS),
	'ask.remaining'
];

function own(map: Record<string, string>, key: string): string | null {
	return Object.prototype.hasOwnProperty.call(map, key) ? map[key] : null;
}

/** True for the codes that describe the account's access rather than one question. */
export function isGateReason(code: string | null | undefined): boolean {
	return !!code && (own(CLOSED_REASONS, code) !== null || own(EXHAUSTED_REASONS, code) !== null);
}

/** The view for a reason code; anything unrecognised is closed with the generic message. */
export function reasonView(reason: string | null | undefined): GateView {
	if (reason) {
		const closed = own(CLOSED_REASONS, reason);
		if (closed) return { mode: 'closed', reason, key: closed };
		const exhausted = own(EXHAUSTED_REASONS, reason);
		if (exhausted) return { mode: 'exhausted', reason, key: exhausted };
	}
	return { mode: 'closed', reason: null, key: AI_UNAVAILABLE_KEY };
}

/**
 * The view for a status response. A missing status (it failed to load) is
 * closed, and only an explicit `available: true` opens the composer.
 */
export function gateView(
	status: { available: boolean; reason: string | null } | null | undefined
): GateView {
	if (!status) return reasonView(null);
	if (status.available === true) return { mode: 'available', reason: null, key: null };
	return reasonView(status.reason);
}

/** What a failed ask means for the page. */
export type AskFailure =
	/** The account's access changed: apply `view`, then reload the status. */
	| { kind: 'gate'; view: GateView }
	/** The session is gone: show the sign-in gate. */
	| { kind: 'signin' }
	/** This question failed; the composer state still comes from the status. */
	| { kind: 'error'; key: string };

interface ErrorLike {
	name?: unknown;
	status?: unknown;
	errorCode?: unknown;
}

/**
 * Classify an error thrown by `askSchedule()`. Reads only the status, the
 * machine code and the error name, never the message.
 */
export function classifyAskError(err: unknown): AskFailure {
	const e: ErrorLike = err !== null && typeof err === 'object' ? (err as ErrorLike) : {};
	// Both api.ts's TimeoutError and the DOMException from AbortSignal.timeout
	// carry this name.
	if (e.name === 'TimeoutError') return { kind: 'error', key: ERROR_KEYS.timeout };

	const status = typeof e.status === 'number' ? e.status : null;
	const code = typeof e.errorCode === 'string' ? e.errorCode : null;

	// Whatever the body says, a 401 means the session is gone.
	if (status === 401) return { kind: 'signin' };

	if (code !== null) {
		if (isGateReason(code)) return { kind: 'gate', view: reasonView(code) };
		if (code === 'ai_prompt_too_large') return { kind: 'error', key: ERROR_KEYS.promptTooLarge };
		if (code === 'ai_upstream_failed') return { kind: 'error', key: ERROR_KEYS.upstreamFailed };
		// ai_ledger_unavailable and any code this build does not know.
		return { kind: 'error', key: AI_UNAVAILABLE_KEY };
	}

	if (status === 404) return { kind: 'error', key: ERROR_KEYS.projectUnavailable };
	if (status === 422) return { kind: 'error', key: ERROR_KEYS.invalidQuestion };
	// The per-address rate limiter answers without a code.
	if (status === 429) return { kind: 'error', key: ERROR_KEYS.rateLimited };
	// A bare 502 comes from the proxy in front of the API: the answer failed.
	if (status === 502) return { kind: 'error', key: ERROR_KEYS.upstreamFailed };
	return { kind: 'error', key: AI_UNAVAILABLE_KEY };
}

/**
 * Single-pass `{name}` substitution. A value that itself contains `{x}` stays
 * literal instead of being substituted again (same rule as
 * RevisionConfirmCard's interpolate).
 */
export function interpolate(template: string, values: Record<string, string>): string {
	return template.replace(/\{(\w+)\}/g, (match, key: string) =>
		Object.prototype.hasOwnProperty.call(values, key) ? values[key] : match
	);
}

/**
 * The reset instant in the viewer's own time zone (hours and minutes), or null
 * when missing or unreadable. `formatDate` in i18n/format.ts is not used here
 * on purpose: it forces UTC, and a reset time must read in local time.
 */
export function formatResetTime(iso: string | null | undefined, locale: string): string | null {
	if (!iso) return null;
	const parsed = new Date(iso);
	if (Number.isNaN(parsed.getTime())) return null;
	try {
		return parsed.toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit' });
	} catch {
		return null;
	}
}

type Translate = (key: string) => string;

/** The message for a gate view, with the reset time for the daily quota when known. */
export function gateMessage(
	t: Translate,
	view: GateView,
	resetsAt: string | null | undefined,
	locale: string
): string {
	if (view.key === null) return '';
	if (view.reason === 'ai_daily_quota') {
		const time = formatResetTime(resetsAt, locale);
		return time ? interpolate(t(view.key), { time }) : t(DAILY_QUOTA_NO_TIME_KEY);
	}
	return t(view.key);
}

/** "{remaining} of {limit} questions left today", or '' when either is unknown. */
export function remainingMessage(
	t: Translate,
	remaining: number | null | undefined,
	limit: number | null | undefined
): string {
	if (typeof remaining !== 'number' || typeof limit !== 'number') return '';
	if (!Number.isFinite(remaining) || !Number.isFinite(limit)) return '';
	return interpolate(t('ask.remaining'), { remaining: String(remaining), limit: String(limit) });
}
