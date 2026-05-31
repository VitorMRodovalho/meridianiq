// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// dcmaMarginBars — margin-to-threshold transform for the /demo chart (W2).
// Pins the entry-council decisions: monotonic signed margin, subtraction-only
// (well-defined at threshold=0), %-only filter, worst-first ordering.

import { describe, expect, it } from 'vitest';
import { dcmaMarginBars, thresholdComparator } from './dcmaChart';
import type { DemoDCMAMetric } from '$lib/api';

function metric(p: Partial<DemoDCMAMetric>): DemoDCMAMetric {
	return {
		number: 1,
		name: 'X',
		value: 0,
		threshold: 0,
		unit: '%',
		passed: true,
		direction: 'min',
		...p,
	};
}

describe('dcmaMarginBars (W2)', () => {
	it('max-direction margin = value - threshold (Logic 92% vs ≥90% ⇒ +2)', () => {
		const [bar] = dcmaMarginBars([metric({ name: 'Logic', value: 92, threshold: 90, direction: 'max' })]);
		expect(bar.margin).toBe(2);
	});

	it('min-direction margin = threshold - value (Hard Constraints 8% vs ≤5% ⇒ -3)', () => {
		const [bar] = dcmaMarginBars([
			metric({ name: 'Hard Constraints', value: 8, threshold: 5, direction: 'min', passed: false }),
		]);
		expect(bar.margin).toBe(-3);
	});

	it('is well-defined for threshold=0 checks (Negative Float 3% vs ≤0% ⇒ -3, no division)', () => {
		const [bar] = dcmaMarginBars([
			metric({ name: 'Negative Float', value: 3, threshold: 0, direction: 'min', passed: false }),
		]);
		expect(bar.margin).toBe(-3);
		expect(Number.isFinite(bar.margin)).toBe(true);
	});

	it('a check exactly at a zero threshold has margin 0 (Negative Float 0% ⇒ pass)', () => {
		const [bar] = dcmaMarginBars([
			metric({ name: 'Negative Float', value: 0, threshold: 0, direction: 'min', passed: true }),
		]);
		expect(bar.margin).toBe(0);
	});

	it('excludes non-percentage (ratio/index) checks (CPLI/BEI/Critical Path Test, unit="")', () => {
		const bars = dcmaMarginBars([
			metric({ name: 'CPLI', unit: '', value: 0.98, threshold: 0.95, direction: 'max' }),
			metric({ name: 'Logic', unit: '%', value: 95, threshold: 90, direction: 'max' }),
		]);
		expect(bars.map((b) => b.name)).toEqual(['Logic']);
	});

	it('orders worst (most negative margin) first', () => {
		const bars = dcmaMarginBars([
			metric({ name: 'Pass', value: 95, threshold: 90, direction: 'max', passed: true }),
			metric({ name: 'BigFail', value: 30, threshold: 5, direction: 'min', passed: false }),
			metric({ name: 'SmallFail', value: 7, threshold: 5, direction: 'min', passed: false }),
		]);
		expect(bars.map((b) => b.name)).toEqual(['BigFail', 'SmallFail', 'Pass']);
		expect(bars[0].margin).toBeLessThan(bars[1].margin);
	});

	it('preserves the authoritative passed flag from the backend', () => {
		const [bar] = dcmaMarginBars([metric({ value: 95, threshold: 90, direction: 'max', passed: true })]);
		expect(bar.passed).toBe(true);
	});

	it('margin sign can disagree with passed at a rounding boundary — so the chart drives side/colour from passed, not Math.sign(margin)', () => {
		// True 5.04% (FAILS ≤5%) is rounded to 5.0 by the backend, so the
		// display-derived margin is 0 (non-negative) while passed=false. The
		// component must put this bar on the FAIL side using `passed`.
		const [bar] = dcmaMarginBars([
			metric({ name: 'Hard Constraints', value: 5.0, threshold: 5, direction: 'min', passed: false }),
		]);
		expect(bar.margin).toBe(0); // non-negative…
		expect(bar.passed).toBe(false); // …yet authoritatively failing
	});
});

describe('thresholdComparator (W2)', () => {
	it('renders ≥ for max-direction and ≤ for min-direction', () => {
		expect(thresholdComparator('max')).toBe('≥');
		expect(thresholdComparator('min')).toBe('≤');
	});
});
