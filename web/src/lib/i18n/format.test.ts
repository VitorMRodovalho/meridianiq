// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// Vitest unit tests for `formatNumber` helper — Cycle 5 W2 batch 2-A
// (issue #96 part 1 / DA P2 #8 from PR #95) — and `formatDate` helper
// — Cycle 5 W3-C (issue #85 / DA P3-2 from PR #83).

import { describe, expect, it } from 'vitest';
import { formatDate, formatNumber } from './format';

describe('formatNumber', () => {
	describe('locale-specific decimal separators', () => {
		it('en-US uses decimal POINT', () => {
			expect(formatNumber(1.5, 'en')).toBe('1.5');
			expect(formatNumber(-3.42, 'en', { maximumFractionDigits: 2 })).toBe('-3.42');
		});

		it('pt-BR uses decimal COMMA', () => {
			expect(formatNumber(1.5, 'pt-BR')).toBe('1,5');
			// Use ASCII hyphen-minus for negative values; Intl in pt-BR also uses '-'
			expect(formatNumber(-3.42, 'pt-BR', { maximumFractionDigits: 2 })).toBe('-3,42');
		});

		it('es uses decimal COMMA', () => {
			expect(formatNumber(1.5, 'es')).toBe('1,5');
			expect(formatNumber(-3.42, 'es', { maximumFractionDigits: 2 })).toBe('-3,42');
		});
	});

	describe('signDisplay: always (slope sign preservation)', () => {
		it('en positive slope keeps + sign', () => {
			expect(formatNumber(2.3, 'en', { maximumFractionDigits: 1, signDisplay: 'always' })).toBe(
				'+2.3',
			);
		});

		it('pt-BR positive slope keeps + sign with COMMA decimal', () => {
			expect(formatNumber(2.3, 'pt-BR', { maximumFractionDigits: 1, signDisplay: 'always' })).toBe(
				'+2,3',
			);
		});

		it('zero with signDisplay always — frontend-ux-reviewer P0 #8 edge case', () => {
			// Verify behavior is documented; users may dislike +0 but this is
			// what Intl.NumberFormat produces. Documented for future preference change.
			const result = formatNumber(0, 'en', { maximumFractionDigits: 1, signDisplay: 'always' });
			expect(result).toBe('+0');
		});
	});

	describe('non-finite value safety', () => {
		it('NaN returns em-dash', () => {
			expect(formatNumber(Number.NaN, 'en')).toBe('—');
			expect(formatNumber(Number.NaN, 'pt-BR')).toBe('—');
		});

		it('positive Infinity returns em-dash', () => {
			expect(formatNumber(Number.POSITIVE_INFINITY, 'en')).toBe('—');
		});

		it('negative Infinity returns em-dash', () => {
			expect(formatNumber(Number.NEGATIVE_INFINITY, 'en')).toBe('—');
		});

		it('negative zero formats as "-0" per Intl.NumberFormat behavior', () => {
			// -0 is finite per Number.isFinite. Intl.NumberFormat emits "-0"
			// (preserving the negative-zero IEEE-754 distinction). Document
			// the actual behavior: callers who want "+0" canonicalization
			// should pass a normalized value (e.g., `value || 0`).
			expect(formatNumber(-0, 'en')).toBe('-0');
			expect(formatNumber(-0, 'pt-BR')).toBe('-0');
		});
	});

	describe('default options', () => {
		it('omitted options defaults to maximumFractionDigits: 1', () => {
			expect(formatNumber(1.234567, 'en')).toBe('1.2');
		});

		it('multiple decimals truncate per maxFractionDigits', () => {
			expect(formatNumber(1.234567, 'en', { maximumFractionDigits: 3 })).toBe('1.235');
		});
	});

	describe('fallback path (invalid locale)', () => {
		it('unknown locale string falls back to .toFixed', () => {
			// Some Intl impls accept any tag; use a syntactically-invalid one
			// to force the catch branch.
			const result = formatNumber(2.5, '??invalid?', { maximumFractionDigits: 1 });
			expect(result).toMatch(/2[.,]5/);
		});
	});
});

describe('formatDate', () => {
	const ISO_2026_04_15 = '2026-04-15T00:00:00Z';

	describe('locale-specific date conventions', () => {
		it('en formats month-name short + numeric day + numeric year', () => {
			// "Apr 15, 2026" with non-breaking space conventions.
			const result = formatDate(ISO_2026_04_15, 'en');
			expect(result).toMatch(/Apr/);
			expect(result).toContain('15');
			expect(result).toContain('2026');
		});

		it('pt-BR formats with day-month-year ordering + Portuguese month abbrev', () => {
			// "15 de abr. de 2026" or similar; assert components rather than
			// exact form because Intl behavior varies by ICU version.
			const result = formatDate(ISO_2026_04_15, 'pt-BR');
			expect(result).toMatch(/abr/i);
			expect(result).toContain('15');
			expect(result).toContain('2026');
		});

		it('es formats with day-month-year ordering + Spanish month abbrev', () => {
			const result = formatDate(ISO_2026_04_15, 'es');
			expect(result).toMatch(/abr/i);
			expect(result).toContain('15');
			expect(result).toContain('2026');
		});
	});

	describe('timezone discipline (data_date is TZ-naive per P6 domain)', () => {
		it('UTC midnight ISO renders as the same calendar day across runner TZs', () => {
			// Without timeZone: 'UTC', this would shift to "Apr 14" in
			// western-hemisphere runner TZs. The forced UTC clamps to the
			// calendar day the ISO timestamp represents.
			const result = formatDate('2026-04-15T00:00:00Z', 'en');
			expect(result).toContain('15');
			expect(result).not.toContain('14');
		});

		it('explicit positive offset still parses to the UTC calendar day', () => {
			// 2026-04-15T01:00:00+01:00 == 2026-04-15T00:00:00Z → "Apr 15".
			const result = formatDate('2026-04-15T01:00:00+01:00', 'en');
			expect(result).toContain('15');
		});
	});

	describe('null / invalid input safety', () => {
		it('null returns em-dash', () => {
			expect(formatDate(null, 'en')).toBe('—');
		});

		it('undefined returns em-dash', () => {
			expect(formatDate(undefined, 'en')).toBe('—');
		});

		it('empty string returns em-dash', () => {
			expect(formatDate('', 'en')).toBe('—');
		});

		it('unparseable string returns em-dash', () => {
			expect(formatDate('not-a-date', 'en')).toBe('—');
			expect(formatDate('garbage', 'pt-BR')).toBe('—');
		});
	});

	describe('options override', () => {
		it('numeric/numeric/numeric format respects override', () => {
			const result = formatDate(ISO_2026_04_15, 'en', {
				year: 'numeric',
				month: '2-digit',
				day: '2-digit',
			});
			expect(result).toContain('04');
			expect(result).toContain('15');
			expect(result).toContain('2026');
		});
	});

	describe('fallback path (invalid locale)', () => {
		it('unknown locale string falls back to YYYY-MM-DD slice', () => {
			// Force the catch branch with a syntactically-invalid locale tag.
			const result = formatDate(ISO_2026_04_15, '??invalid?');
			expect(result).toBe('2026-04-15');
		});
	});
});
