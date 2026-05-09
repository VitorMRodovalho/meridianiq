// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// Locale-aware number formatting helpers — Cycle 5 W2 batch 2-A.
//
// Usage MUST be markup-side (inside `{}` expression in template), NOT
// script-side: the function does not subscribe to the `locale` store; the
// reactivity comes from the markup re-rendering when `$locale` changes.
// See frontend-ux-reviewer entry-council BLOCKING #1 on PR #109.
//
// Issue #96 part 1 (DA P2 #8 from PR #95): `.toFixed(1)` always emits
// decimal POINT. pt-BR/es users expect decimal COMMA (`1,5` not `1.5`).
// `Intl.NumberFormat` honors locale conventions automatically.

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
