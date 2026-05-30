import { describe, it, expect } from 'vitest';
import { generateTimeTicks } from './utils';

describe('generateTimeTicks — two-tier time axis', () => {
	it('returns both a minor and a major tier', () => {
		const axis = generateTimeTicks('2026-01-01', '2026-12-31', 'month');
		expect(Array.isArray(axis.minor)).toBe(true);
		expect(Array.isArray(axis.major)).toBe(true);
		expect(axis.minor.length).toBeGreaterThan(0);
		expect(axis.major.length).toBeGreaterThan(0);
	});

	it('major bands are contiguous and span the whole chart (first x=0, last xEnd=1)', () => {
		const axis = generateTimeTicks('2026-03-15', '2028-06-30', 'month');
		expect(axis.major[0].x).toBe(0);
		expect(axis.major[axis.major.length - 1].xEnd).toBe(1);
		for (let i = 0; i < axis.major.length - 1; i++) {
			// each band's right edge is the next band's left edge — no gaps
			expect(axis.major[i].xEnd).toBeCloseTo(axis.major[i + 1].x, 6);
		}
	});

	it('month zoom uses YEAR major bands', () => {
		const axis = generateTimeTicks('2026-01-01', '2028-12-31', 'month');
		expect(axis.major.map((m) => m.label)).toEqual(['2026', '2027', '2028']);
	});

	it('week zoom uses MONTH major bands', () => {
		const axis = generateTimeTicks('2026-01-01', '2026-03-31', 'week');
		expect(axis.major[0].label).toMatch(/Jan/);
		expect(axis.major.length).toBeGreaterThanOrEqual(3); // Jan, Feb, Mar
	});

	it('minor tick fractions are within [0,1] and strictly ascending', () => {
		const axis = generateTimeTicks('2026-01-01', '2026-06-30', 'week');
		const xs = axis.minor.map((t) => t.x);
		expect(Math.min(...xs)).toBeGreaterThanOrEqual(0);
		expect(Math.max(...xs)).toBeLessThanOrEqual(1.0001);
		for (let i = 1; i < xs.length; i++) {
			expect(xs[i]).toBeGreaterThan(xs[i - 1]);
		}
	});

	it('long schedules keep full coverage (gridlines are no longer capped at 100 days)', () => {
		// A 3-year month-zoom schedule. The old Array(min(totalDays, 100)) loop
		// stopped gridding past day 100; the major tier must still reach xEnd=1.
		const axis = generateTimeTicks('2026-01-01', '2029-01-01', 'month');
		expect(axis.major[axis.major.length - 1].xEnd).toBe(1);
		expect(axis.major.length).toBeGreaterThanOrEqual(3);
	});
});
