// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// Unit tests for WCAG 2.2 contrast primitives. Values cross-checked
// against W3C "Understanding SC 1.4.3" worked examples and Tailwind
// CSS design-token contrast pairs.

import { describe, it, expect } from 'vitest';
import { srgbToLinear, relativeLuminance, contrastRatio } from './wcagContrast';

describe('srgbToLinear', () => {
	it('returns 0 for channel=0', () => {
		expect(srgbToLinear(0)).toBe(0);
	});

	it('returns ~1 for channel=255 (sRGB max)', () => {
		expect(srgbToLinear(255)).toBeCloseTo(1, 6);
	});

	it('uses linear branch below the 0.04045 threshold (channel=10)', () => {
		// 10/255 ≈ 0.0392 < 0.04045 → linear branch /12.92.
		expect(srgbToLinear(10)).toBeCloseTo(10 / 255 / 12.92, 6);
	});

	it('uses gamma branch at channel=128 (mid sRGB)', () => {
		// 128/255 ≈ 0.502 → ((0.502+0.055)/1.055)^2.4 ≈ 0.2159.
		expect(srgbToLinear(128)).toBeCloseTo(0.2159, 3);
	});
});

describe('relativeLuminance', () => {
	it('returns 1.0 for white', () => {
		expect(relativeLuminance('#ffffff')).toBeCloseTo(1.0, 6);
	});

	it('returns 0.0 for black', () => {
		expect(relativeLuminance('#000000')).toBe(0);
	});

	it('returns ~0.0092 for tailwind bg-gray-900 (#111827)', () => {
		// Spot-checked in PR #108 council math thread; load-bearing for the
		// dual-bg contrast budget at 3:1 (Y_color ∈ [0.128, 0.300] feasible).
		expect(relativeLuminance('#111827')).toBeCloseTo(0.0092, 3);
	});

	it('throws on malformed hex (no leading #)', () => {
		expect(() => relativeLuminance('aabbcc')).toThrow();
	});

	it('throws on 3-char hex (we require #rrggbb)', () => {
		expect(() => relativeLuminance('#abc')).toThrow();
	});

	it('throws on non-hex chars', () => {
		expect(() => relativeLuminance('#gghhii')).toThrow();
	});
});

describe('contrastRatio', () => {
	it('returns 21:1 for black vs white (W3C reference maximum)', () => {
		expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 4);
	});

	it('returns 1:1 for identical colors', () => {
		expect(contrastRatio('#3b82f6', '#3b82f6')).toBeCloseTo(1, 6);
	});

	it('is symmetric in argument order', () => {
		const ab = contrastRatio('#374151', '#ffffff');
		const ba = contrastRatio('#ffffff', '#374151');
		expect(ab).toBe(ba);
	});

	it('returns ≥10:1 for tailwind text-gray-700 (#374151) vs white (design-token sanity)', () => {
		expect(contrastRatio('#374151', '#ffffff')).toBeGreaterThanOrEqual(10);
	});

	it('returns ≥10:1 for tailwind text-gray-300 (#d1d5db) vs bg-gray-900 (dark-mode design-token sanity)', () => {
		expect(contrastRatio('#d1d5db', '#111827')).toBeGreaterThanOrEqual(10);
	});
});
