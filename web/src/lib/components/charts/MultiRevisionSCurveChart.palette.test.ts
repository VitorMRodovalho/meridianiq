// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// Palette + per-revision encoding tests for MultiRevisionSCurveChart.
//
// Layered assertions:
//   1. PALETTE_10 frozen-array regression pin — silent swatch swaps
//      must trip a test, not slip through.
//   2. WCAG 1.4.11 contrast ≥3:1 against both `bg-white` (#ffffff) and
//      `bg-gray-900` (#111827). Uses the `wcagContrast` util.
//   3. ΔE distinctness — pairwise sRGB-Euclidean ΔE>20 within PALETTE_10
//      AND against the four reserved chart colors (executed-overlay
//      blue, slip amber, improvement emerald, flat gray). sRGB-
//      Euclidean is a crude approximation; CIEDE2000-in-LAB is the
//      perceptually-uniform alternative and would be stricter on some
//      pairs. The threshold is a lower bar, not a perceptual guarantee.
//   4. Dichromacy distinctness (intra-palette AND vs RESERVED) under
//      Viénot 1999 simulation for deuteranopia and protanopia. ΔE>15
//      in simulated space. Two most common dichromacies only —
//      anomalous trichromacies (deuteranomaly + protanomaly ~5%
//      prevalence combined) and tritanopia are NOT simulated; the
//      stroke-width-as-age + legend-chip + endpoint-label channels
//      provide non-color reinforcement for those users.
//   5. Helper-shape tests assert evenly-spaced indexing (so total=2
//      picks palette[0] and palette[9] not palette[0] and palette[1])
//      and the monotone-increasing stroke-width / legend-chip-height
//      schedule, plus RangeError guards on out-of-spec inputs.
//
// All Viénot matrices and the sRGB-Euclidean ΔE formula are inlined
// here. The application deliberately does NOT carry a CVD-simulation
// runtime dependency.

import { describe, it, expect } from 'vitest';
import { contrastRatio, srgbToLinear } from '$lib/utils/wcagContrast';
import {
	PALETTE_10,
	SINGLE_CURVE_COLOR,
	STROKE_WIDTH_MIN,
	STROKE_WIDTH_MAX,
	LEGEND_CHIP_HEIGHT_MIN,
	LEGEND_CHIP_HEIGHT_MAX,
	getCurveColor,
	getCurveStrokeWidth,
	getLegendChipHeight,
} from './MultiRevisionSCurveChart.palette';

const WHITE = '#ffffff';
const DARK_BG = '#111827';

const RESERVED: ReadonlyArray<readonly [string, string]> = [
	['executed-overlay-blue', '#3b82f6'],
	['slip-marker-amber', '#b45309'],
	['improvement-marker-emerald', '#047857'],
	['flat-marker-gray', '#4b5563'],
];

// Viénot 1999 linear-RGB dichromat-simulation matrices.
const PROTAN_M: ReadonlyArray<ReadonlyArray<number>> = [
	[0.152286, 1.052583, -0.204868],
	[0.114503, 0.786281, 0.099216],
	[-0.003882, -0.048116, 1.051998],
];
const DEUTAN_M: ReadonlyArray<ReadonlyArray<number>> = [
	[0.367322, 0.860646, -0.227968],
	[0.280085, 0.672501, 0.047413],
	[-0.011820, 0.042940, 0.968881],
];

function parseHex(hex: string): readonly [number, number, number] {
	const m = /^#([0-9a-f]{6})$/i.exec(hex);
	if (!m) throw new Error(`bad hex ${hex}`);
	const v = parseInt(m[1], 16);
	return [(v >> 16) & 0xff, (v >> 8) & 0xff, v & 0xff];
}

function linearToSrgb(x: number): number {
	const c = x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055;
	return Math.round(Math.max(0, Math.min(1, c)) * 255);
}

function simulateCvd(hex: string, m: ReadonlyArray<ReadonlyArray<number>>): string {
	const [r, g, b] = parseHex(hex);
	const rl = srgbToLinear(r);
	const gl = srgbToLinear(g);
	const bl = srgbToLinear(b);
	const r2 = m[0][0] * rl + m[0][1] * gl + m[0][2] * bl;
	const g2 = m[1][0] * rl + m[1][1] * gl + m[1][2] * bl;
	const b2 = m[2][0] * rl + m[2][1] * gl + m[2][2] * bl;
	return (
		'#' +
		[linearToSrgb(r2), linearToSrgb(g2), linearToSrgb(b2)]
			.map((c) => c.toString(16).padStart(2, '0'))
			.join('')
	);
}

function deltaE(hex1: string, hex2: string): number {
	const [r1, g1, b1] = parseHex(hex1);
	const [r2, g2, b2] = parseHex(hex2);
	return Math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2);
}

describe('PALETTE_10 — regression pin', () => {
	it('is frozen to the council-approved 10 hex values', () => {
		// Order is hue-progression (red → rose around the color wheel,
		// skipping the blue band reserved for executed-overlay #3b82f6).
		// A silent swap here would silently change every chart rendering
		// — keep this list stable across PRs and re-justify in a new
		// council if you must change it. See palette file header for the
		// reason size=10 not 11 (no feasible 11-element solution under
		// the full Y + ΔE + CVD-vs-RESERVED constraint stack).
		expect(PALETTE_10).toEqual([
			'#dc2626', // 0 red-600
			'#ea580c', // 1 orange-600
			'#65a30d', // 2 lime-600
			'#15803d', // 3 green-700
			'#0f766e', // 4 teal-700
			'#0891b2', // 5 cyan-600
			'#7c3aed', // 6 violet-600
			'#c026d3', // 7 fuchsia-600
			'#db2777', // 8 pink-600
			'#e11d48', // 9 rose-600
		]);
	});

	it('has exactly 10 swatches', () => {
		expect(PALETTE_10).toHaveLength(10);
	});

	it('SINGLE_CURVE_COLOR is the documented gray-500 fallback', () => {
		expect(SINGLE_CURVE_COLOR).toBe('#6b7280');
	});
});

describe('PALETTE_10 — WCAG 1.4.11 contrast (≥3:1 vs both backgrounds)', () => {
	it.each(PALETTE_10)('swatch %s clears 3:1 vs #ffffff', (hex) => {
		expect(contrastRatio(hex, WHITE)).toBeGreaterThanOrEqual(3.0);
	});

	it.each(PALETTE_10)('swatch %s clears 3:1 vs #111827 (dark-mode bg)', (hex) => {
		expect(contrastRatio(hex, DARK_BG)).toBeGreaterThanOrEqual(3.0);
	});

	it('SINGLE_CURVE_COLOR also clears 3:1 vs both backgrounds', () => {
		expect(contrastRatio(SINGLE_CURVE_COLOR, WHITE)).toBeGreaterThanOrEqual(3.0);
		expect(contrastRatio(SINGLE_CURVE_COLOR, DARK_BG)).toBeGreaterThanOrEqual(3.0);
	});
});

describe('PALETTE_10 — ΔE distinctness (normal vision)', () => {
	it('every pair within PALETTE_10 has ΔE > 20', () => {
		for (let i = 0; i < PALETTE_10.length; i++) {
			for (let j = i + 1; j < PALETTE_10.length; j++) {
				const d = deltaE(PALETTE_10[i], PALETTE_10[j]);
				expect(d, `palette[${i}] (${PALETTE_10[i]}) vs palette[${j}] (${PALETTE_10[j]})`).toBeGreaterThan(20);
			}
		}
	});

	it('every palette swatch has ΔE > 20 against every reserved chart color', () => {
		for (const hex of PALETTE_10) {
			for (const [name, reserved] of RESERVED) {
				const d = deltaE(hex, reserved);
				expect(d, `${hex} vs ${name} (${reserved})`).toBeGreaterThan(20);
			}
		}
	});
});

describe('PALETTE_10 — CVD distinctness (Viénot 1999 simulation, ΔE>15 perceivability)', () => {
	it('every pair has simulated-deuteranopia ΔE > 15', () => {
		const sim = PALETTE_10.map((h) => simulateCvd(h, DEUTAN_M));
		for (let i = 0; i < sim.length; i++) {
			for (let j = i + 1; j < sim.length; j++) {
				expect(
					deltaE(sim[i], sim[j]),
					`deutan: palette[${i}] (${PALETTE_10[i]}) vs palette[${j}] (${PALETTE_10[j]})`,
				).toBeGreaterThan(15);
			}
		}
	});

	it('every pair has simulated-protanopia ΔE > 15', () => {
		const sim = PALETTE_10.map((h) => simulateCvd(h, PROTAN_M));
		for (let i = 0; i < sim.length; i++) {
			for (let j = i + 1; j < sim.length; j++) {
				expect(
					deltaE(sim[i], sim[j]),
					`protan: palette[${i}] (${PALETTE_10[i]}) vs palette[${j}] (${PALETTE_10[j]})`,
				).toBeGreaterThan(15);
			}
		}
	});

	// DA exit-council finding 12c on PR #108: ΔE-vs-RESERVED was previously
	// only checked in normal vision. Under CVD simulation a palette swatch
	// could still collide with a change-point marker color (e.g. teal-vs-
	// emerald is the canonical practitioner failure case for deuteranopia).
	it('every palette swatch is distinguishable from every RESERVED color under deuteranopia (ΔE>15)', () => {
		for (const hex of PALETTE_10) {
			const simHex = simulateCvd(hex, DEUTAN_M);
			for (const [name, reserved] of RESERVED) {
				const simRes = simulateCvd(reserved, DEUTAN_M);
				expect(
					deltaE(simHex, simRes),
					`deutan: ${hex} vs ${name} (${reserved})`,
				).toBeGreaterThan(15);
			}
		}
	});

	it('every palette swatch is distinguishable from every RESERVED color under protanopia (ΔE>15)', () => {
		for (const hex of PALETTE_10) {
			const simHex = simulateCvd(hex, PROTAN_M);
			for (const [name, reserved] of RESERVED) {
				const simRes = simulateCvd(reserved, PROTAN_M);
				expect(
					deltaE(simHex, simRes),
					`protan: ${hex} vs ${name} (${reserved})`,
				).toBeGreaterThan(15);
			}
		}
	});
});

describe('getCurveColor — evenly-spaced indexing into PALETTE_10', () => {
	it('returns SINGLE_CURVE_COLOR when total=1', () => {
		expect(getCurveColor(0, 1)).toBe(SINGLE_CURVE_COLOR);
	});

	it('spreads N=2 across opposite palette ends (palette[0] and palette[9])', () => {
		expect(getCurveColor(0, 2)).toBe(PALETTE_10[0]);
		expect(getCurveColor(1, 2)).toBe(PALETTE_10[9]);
	});

	it('places N=10 one-to-one into palette slots', () => {
		for (let i = 0; i < 10; i++) {
			expect(getCurveColor(i, 10)).toBe(PALETTE_10[i]);
		}
	});

	it('N=3 picks palette[0], palette[5], palette[9] (evenly spaced)', () => {
		// Indexing formula: round(i * (10-1) / (3-1)) = round(i * 4.5)
		// i=0 → 0, i=1 → round(4.5)=5 (.5 rounds to even per IEEE; JS Math.round always rounds .5 up), i=2 → 9.
		expect(getCurveColor(0, 3)).toBe(PALETTE_10[0]);
		expect(getCurveColor(1, 3)).toBe(PALETTE_10[5]);
		expect(getCurveColor(2, 3)).toBe(PALETTE_10[9]);
	});

	// DA exit-council findings 6 + 7 on PR #108: silent N>palette-size
	// collisions would have been a P1 bug; total=0 would have rendered
	// stroke="undefined". All three helpers now hard-fail with RangeError.
	it('throws when total ≤ 0', () => {
		expect(() => getCurveColor(0, 0)).toThrow(RangeError);
		expect(() => getCurveColor(0, -1)).toThrow(RangeError);
	});

	it('throws when total > PALETTE_10.length', () => {
		expect(() => getCurveColor(0, 11)).toThrow(RangeError);
		expect(() => getCurveColor(0, 50)).toThrow(RangeError);
	});

	it('throws when index is out of [0, total)', () => {
		expect(() => getCurveColor(-1, 5)).toThrow(RangeError);
		expect(() => getCurveColor(5, 5)).toThrow(RangeError);
	});
});

describe('getCurveStrokeWidth — monotone-increasing age encoding', () => {
	it('returns STROKE_WIDTH_MAX for total=1', () => {
		expect(getCurveStrokeWidth(0, 1)).toBe(STROKE_WIDTH_MAX);
	});

	it('returns STROKE_WIDTH_MIN at index 0 of total≥2', () => {
		expect(getCurveStrokeWidth(0, 5)).toBeCloseTo(STROKE_WIDTH_MIN, 6);
		expect(getCurveStrokeWidth(0, 10)).toBeCloseTo(STROKE_WIDTH_MIN, 6);
	});

	it('returns STROKE_WIDTH_MAX at index total-1', () => {
		expect(getCurveStrokeWidth(4, 5)).toBeCloseTo(STROKE_WIDTH_MAX, 6);
		expect(getCurveStrokeWidth(9, 10)).toBeCloseTo(STROKE_WIDTH_MAX, 6);
	});

	it('is strictly increasing across revision index', () => {
		const total = 7;
		let prev = -Infinity;
		for (let i = 0; i < total; i++) {
			const w = getCurveStrokeWidth(i, total);
			expect(w).toBeGreaterThan(prev);
			prev = w;
		}
	});

	it('throws on the same out-of-range conditions as getCurveColor', () => {
		expect(() => getCurveStrokeWidth(0, 0)).toThrow(RangeError);
		expect(() => getCurveStrokeWidth(0, 11)).toThrow(RangeError);
		expect(() => getCurveStrokeWidth(5, 5)).toThrow(RangeError);
	});
});

describe('getLegendChipHeight — mirrors stroke-width encoding', () => {
	it('returns LEGEND_CHIP_HEIGHT_MAX for total=1', () => {
		expect(getLegendChipHeight(0, 1)).toBe(LEGEND_CHIP_HEIGHT_MAX);
	});

	it('clamps to the documented [MIN, MAX] range across N=10', () => {
		for (let i = 0; i < 10; i++) {
			const h = getLegendChipHeight(i, 10);
			expect(h).toBeGreaterThanOrEqual(LEGEND_CHIP_HEIGHT_MIN);
			expect(h).toBeLessThanOrEqual(LEGEND_CHIP_HEIGHT_MAX);
		}
	});

	it('is strictly increasing across revision index', () => {
		const total = 7;
		let prev = -Infinity;
		for (let i = 0; i < total; i++) {
			const h = getLegendChipHeight(i, total);
			expect(h).toBeGreaterThan(prev);
			prev = h;
		}
	});

	it('throws on the same out-of-range conditions as getCurveColor', () => {
		expect(() => getLegendChipHeight(0, 0)).toThrow(RangeError);
		expect(() => getLegendChipHeight(0, 11)).toThrow(RangeError);
		expect(() => getLegendChipHeight(5, 5)).toThrow(RangeError);
	});
});
