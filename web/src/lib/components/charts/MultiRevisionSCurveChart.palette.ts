// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// MultiRevisionSCurveChart palette + per-revision encoding helpers.
//
// Issue #108 — replaces the prior HSL hue-cycling palette (which failed
// WCAG 1.4.11 at hue~80° around `hsl(80°,60%,45%)` per DA P3 #15 PR #95)
// with 11 hand-selected hex values whose properties were verified
// algorithmically before commit:
//
//   1. Each swatch's relative luminance Y satisfies Y ∈ [0.128, 0.300].
//      That band is the closed-form feasibility region where contrast
//      against both `bg-white` (Y=1.0) and `bg-gray-900` (`#111827`,
//      Y≈0.0092) clears the WCAG 1.4.11 Non-text Contrast AA threshold
//      of 3:1. Derivation:
//        vs white: (1.0+0.05)/(Y+0.05) ≥ 3 ⟹ Y ≤ 0.30
//        vs g-900: (Y+0.05)/(0.0092+0.05) ≥ 3 ⟹ Y ≥ 0.128
//      Both must hold ⟹ Y ∈ [0.128, 0.30].
//
//   2. Pairwise sRGB-Euclidean ΔE > 20 within the palette, AND > 20
//      against the chart's reserved colors: executed-overlay blue
//      `#3b82f6` (Tailwind blue-500); slip-marker amber `#b45309`
//      (amber-700); improvement-marker emerald `#047857` (emerald-700);
//      flat-marker gray `#4b5563` (gray-600).
//
//   3. CVD-distinguishability under Viénot 1999 dichromat simulation
//      matrices for deuteranopia AND protanopia: minimum simulated
//      pairwise ΔE was 23.9 (deutan) / 27.0 (protan), comfortably
//      above the ΔE>15 perceivability threshold typically cited for
//      CVD-safe palette construction.
//
// The palette was selected by exhaustive search over the 14-element
// candidate set of Tailwind 600/700 stops that individually satisfied
// constraint (1) + (2); the chosen 11 maximize min(deutan_ΔE, protan_ΔE).
//
// All measurements are reproducible from `wcagContrast.ts` + the
// inlined Viénot matrices in the palette unit test below.
//
// Text-vs-curve discipline (WCAG 1.4.3, AA, 4.5:1 for normal text):
// the [0.128, 0.30] band is INCOMPATIBLE with a single-palette 4.5:1
// dual-background guarantee (the inequalities Y ≤ 0.183 [vs white] and
// Y ≥ 0.216 [vs gray-900] have empty intersection). Endpoint labels
// and any other text rendered ON TOP of these colors MUST therefore
// decouple their fill from the curve color and use a fixed
// `text-gray-700 dark:text-gray-300` (#374151 / #d1d5db) pair that
// clears 10:1 in each mode. Curve identification is preserved by
// spatial proximity (label adjacent to curve endpoint) + the legend
// chip swatch.
//
// Age encoding (revision oldest→newest) is routed to STROKE WIDTH, not
// opacity. Opacity weighting + alpha-compositing makes the rendered
// contrast a function of α: at α=0.55 the composited stroke vs white
// can no longer clear 3:1 for any palette swatch in [0.128, 0.30].
// `getCurveStrokeWidth` returns 1.0..2.5 px linearly across revision
// index; the legend chip height is scaled to mirror the encoding so
// chart and legend are channel-congruent.
//
// Selection script and reasoning trail are recorded in PR #108 body.

/**
 * 11 ordered swatches. Order is by hue position (red → rose around the
 * color wheel, skipping the blue band reserved for executed-overlay).
 */
export const PALETTE_11: readonly string[] = Object.freeze([
	'#dc2626', // 0  red-600
	'#c2410c', // 1  orange-700
	'#ea580c', // 2  orange-600
	'#65a30d', // 3  lime-600
	'#0f766e', // 4  teal-700
	'#0d9488', // 5  teal-600
	'#0e7490', // 6  cyan-700
	'#7c3aed', // 7  violet-600
	'#c026d3', // 8  fuchsia-600
	'#db2777', // 9  pink-600
	'#e11d48', // 10 rose-600
]);

/** Fallback color when only one revision is rendered. Matches gray-500. */
export const SINGLE_CURVE_COLOR = '#6b7280';

/** Stroke-width range encoding revision age. */
export const STROKE_WIDTH_MIN = 1.0;
export const STROKE_WIDTH_MAX = 2.5;

/** Legend chip height range (px) — mirrors stroke-width encoding. */
export const LEGEND_CHIP_HEIGHT_MIN = 2;
export const LEGEND_CHIP_HEIGHT_MAX = 5;

/**
 * Pick the palette color for revision `index` out of `total` revisions.
 *
 * For total=1, returns `SINGLE_CURVE_COLOR` (no need for palette diversity).
 * For total≥2, distributes indices evenly across the 11-slot palette so
 * that small N gets maximum hue separation (e.g. total=2 → palette[0] and
 * palette[10], not palette[0] and palette[1]).
 */
export function getCurveColor(index: number, total: number): string {
	if (total <= 1) return SINGLE_CURVE_COLOR;
	const slot = Math.round((index / (total - 1)) * (PALETTE_11.length - 1));
	return PALETTE_11[slot];
}

/** Stroke width for revision `index` of `total` — oldest thinnest, newest thickest. */
export function getCurveStrokeWidth(index: number, total: number): number {
	if (total <= 1) return STROKE_WIDTH_MAX;
	const t = index / (total - 1);
	return STROKE_WIDTH_MIN + (STROKE_WIDTH_MAX - STROKE_WIDTH_MIN) * t;
}

/** Legend chip height (px) for revision `index` of `total` — congruent with stroke-width. */
export function getLegendChipHeight(index: number, total: number): number {
	if (total <= 1) return LEGEND_CHIP_HEIGHT_MAX;
	const t = index / (total - 1);
	return LEGEND_CHIP_HEIGHT_MIN + (LEGEND_CHIP_HEIGHT_MAX - LEGEND_CHIP_HEIGHT_MIN) * t;
}
