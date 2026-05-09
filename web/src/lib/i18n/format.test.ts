// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// Vitest unit tests for `formatNumber` helper — Cycle 5 W2 batch 2-A.
// Issue #96 part 1 (DA P2 #8 from PR #95).

import { describe, expect, it } from 'vitest';
import { formatNumber } from './format';

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
