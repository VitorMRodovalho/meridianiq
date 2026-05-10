// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// Locale-aware formatting helpers — Cycle 5 W2 batch 2-A (numbers) +
// W3-C (dates).
//
// Usage MUST be markup-side (inside `{}` expression in template), NOT
// script-side: the function does not subscribe to the `locale` store; the
// reactivity comes from the markup re-rendering when `$locale` changes.
// See frontend-ux-reviewer entry-council BLOCKING #1 on PR #109.
//
// Issue #96 part 1 (DA P2 #8 from PR #95): `.toFixed(1)` always emits
// decimal POINT. pt-BR/es users expect decimal COMMA (`1,5` not `1.5`).
// `Intl.NumberFormat` honors locale conventions automatically.
//
// Issue #85 (DA P3-2 from PR #83): `iso.slice(0, 10)` returns
// `YYYY-MM-DD`. Acceptable for v1 unambiguous display, but operators
// across en/pt-BR/es prefer locale-formatted dates. `Intl.DateTimeFormat`
// honors locale conventions; data_date semantics are P6-domain
// timezone-NAIVE so we force `timeZone: 'UTC'` to avoid the slice's
// implicit-UTC-cut becoming day-shifted in local TZs (frontend-ux-reviewer
// entry-council BLOCKING #5 on PR #115).

import type { Locale } from './index';

/**
 * Format a numeric value per the active locale's conventions.
 *
 * Defensive: returns `'—'` for `NaN` and `±Infinity` to avoid rendering
 * invalid math state.
 *
 * @param value - the numeric value to format
 * @param locale - the active locale (`'en'` | `'pt-BR'` | `'es'`)
 * @param options - `Intl.NumberFormatOptions` overrides (default
 *   `{ maximumFractionDigits: 1 }`)
 */
export function formatNumber(
	value: number,
	locale: Locale | string = 'en',
	options: Intl.NumberFormatOptions = { maximumFractionDigits: 1 },
): string {
	if (!Number.isFinite(value)) return '—';
	try {
		return new Intl.NumberFormat(locale, options).format(value);
	} catch {
		// Fallback if Intl rejects the locale string for any reason.
		return value.toFixed(options.maximumFractionDigits ?? 1);
	}
}

/**
 * Format an ISO-8601 datetime string per the active locale's date
 * conventions. The output drops the time-of-day; data_date semantics
 * are calendar-day-only.
 *
 * **Timezone discipline**: data_date in P6 is timezone-naive by domain
 * convention. We force `timeZone: 'UTC'` so an ISO string ending in
 * `Z` (or any explicit offset) is interpreted as the calendar day at
 * UTC, NOT shifted to the viewer's local TZ. Without this, a viewer
 * in UTC-3 looking at `2026-04-15T00:00:00Z` would see "Apr 14" — the
 * exact bug the legacy `iso.slice(0, 10)` shortcut also avoided.
 *
 * Defensive:
 * - `null` / `undefined` / `''` → `'—'`
 * - Unparseable strings → `'—'`
 * - Intl rejection → fallback to the legacy `iso.slice(0, 10)` shape
 *
 * @param iso - ISO-8601 datetime string (`'2026-04-15T00:00:00Z'`)
 *   or `null` / `undefined`
 * @param locale - the active locale (`'en'` | `'pt-BR'` | `'es'`)
 * @param options - `Intl.DateTimeFormatOptions` overrides (default
 *   `{ year: 'numeric', month: 'short', day: 'numeric' }`)
 */
export function formatDate(
	iso: string | null | undefined,
	locale: Locale | string = 'en',
	options: Intl.DateTimeFormatOptions = {
		year: 'numeric',
		month: 'short',
		day: 'numeric',
	},
): string {
	if (!iso) return '—';
	const parsed = new Date(iso);
	if (Number.isNaN(parsed.getTime())) return '—';
	try {
		return new Intl.DateTimeFormat(locale, { ...options, timeZone: 'UTC' }).format(parsed);
	} catch {
		// Fallback if Intl rejects the locale string for any reason —
		// preserves the legacy `YYYY-MM-DD` shape so consumers don't
		// suddenly get an empty string in failure modes.
		return iso.slice(0, 10);
	}
}
