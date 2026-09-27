// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// /admin/ai helpers: the grant form's limit check, money formatting and the
// label that names an approved account.
//
// Pure: no stores, no fetch, and no import of `api.ts` (which creates the
// Supabase client at import), so the tests exercise exactly what the page runs.

import { formatNumber } from './i18n/format';

/** Largest per-account daily question limit the API accepts. */
export const AI_GRANT_MAX_DAILY_QUESTIONS = 10_000;
/** Largest per-account monthly budget, in USD, the API accepts. */
export const AI_GRANT_MAX_MONTHLY_USD = 100_000;
/** Most decimal places the API accepts in a monthly budget. */
export const AI_GRANT_MONTHLY_MAX_DECIMALS = 6;

/**
 * Decimal places in the shortest form of `value` (the same text
 * `JSON.stringify` sends), including the exponent form JavaScript uses below
 * 1e-6: `1e-7` has 7 places.
 */
function decimalPlaces(value: number): number {
	const match = /^\d+(?:\.(\d+))?(?:e([+-]\d+))?$/i.exec(String(Math.abs(value)));
	if (!match) return Number.POSITIVE_INFINITY;
	const fraction = match[1]?.length ?? 0;
	const exponent = match[2] ? Number(match[2]) : 0;
	return Math.max(0, fraction - exponent);
}

/**
 * Whether a grant's optional limits are inside what the API accepts, so that a
 * 422 from the grant can only be about the address. Null means "use the default".
 */
export function grantLimitsValid(daily: number | null, monthly: number | null): boolean {
	if (daily !== null) {
		if (!Number.isInteger(daily) || daily < 0 || daily > AI_GRANT_MAX_DAILY_QUESTIONS) return false;
	}
	if (monthly !== null) {
		if (!Number.isFinite(monthly) || monthly < 0 || monthly > AI_GRANT_MAX_MONTHLY_USD) return false;
		if (decimalPlaces(monthly) > AI_GRANT_MONTHLY_MAX_DECIMALS) return false;
	}
	return true;
}

/**
 * Money spent or reserved: one question can cost a fraction of a cent, so up
 * to 4 fraction digits (0.004 reads as $0.004, not $0.00).
 */
export const SPEND_FORMAT: Intl.NumberFormatOptions = {
	style: 'currency',
	currency: 'USD',
	minimumFractionDigits: 2,
	maximumFractionDigits: 4
};

/** Budgets keep the currency's 2 digits. */
export const BUDGET_FORMAT: Intl.NumberFormatOptions = { style: 'currency', currency: 'USD' };

/** A decimal-string amount in the given format, or '—' when missing or unreadable. */
export function formatUsd(
	value: string | null | undefined,
	locale: string,
	options: Intl.NumberFormatOptions
): string {
	if (value === null || value === undefined || value.trim() === '') return '—';
	return formatNumber(Number(value), locale, options);
}

/**
 * True when the summary came back 200 but the usage ledger could not be read.
 * Its ledger fields (spend, call counts, stale reservations, the last failure,
 * the approved accounts) are then zeros or empty that were not measured.
 */
export function ledgerUnavailable(summary: { reason: string | null } | null | undefined): boolean {
	return summary?.reason === 'ai_ledger_unavailable';
}

/** How an approved account is named on the page: its address, else its user id. */
export function accountLabel(ent: { email: string | null; user_id: string }): string {
	return ent.email || ent.user_id;
}
