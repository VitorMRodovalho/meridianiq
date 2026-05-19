// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// MultiRevisionSCurveChart palette + per-revision encoding helpers.
//
// Issue #108 — replaces the prior HSL hue-cycling palette (which failed
// WCAG 1.4.11 at hue~80° around `hsl(80°,60%,45%)` per DA P3 #15 PR #95)
// with 10 hand-selected hex values whose properties were verified
// algorithmically before commit. Verification assumes the chart's
// immediate container is `bg-white` (light mode) or `bg-gray-900`
// `#111827` (dark mode); the chart wrapper sets exactly that pair, so
// the verification covers the rendered context. Embedding the chart
// against a different background (e.g., `bg-gray-950` `#030712`) is
// not in scope — re-verify if you change the wrapper.
//
// Property 1 — Light-mode AND dark-mode WCAG 1.4.11 (≥3:1 graphical):
//   Each swatch's relative luminance Y satisfies Y ∈ [0.128, 0.300].
//   That band is the closed-form feasibility region for a stroke
//   rendered at opacity α=1.0 (the only opacity this chart uses for
//   planned curves, see Property 4):
//     vs white  (Y_bg=1.0):    (1.0+0.05)/(Y+0.05) ≥ 3 ⟹ Y ≤ 0.30
//     vs g-900 (Y_bg≈0.0092): (Y+0.05)/(0.0092+0.05) ≥ 3 ⟹ Y ≥ 0.128
//   Both must hold ⟹ Y ∈ [0.128, 0.30].
//
// Property 2 — sRGB-Euclidean ΔE > 20 within the palette AND > 20
//   against the chart's reserved colors: executed-overlay blue
//   `#3b82f6` (Tailwind blue-500); slip-marker amber `#b45309`
//   (amber-700); improvement-marker emerald `#047857` (emerald-700);
//   flat-marker gray `#4b5563` (gray-600). sRGB-Euclidean is a crude
//   approximation of color difference — a CIEDE2000-in-LAB metric is
//   stricter and may collapse some of our intra-palette pairs. The
//   tightest pair within the chosen 10 is sRGB-ΔE ≈ 35 (still well
//   above the >20 threshold), but the ΔE budget would shrink under
//   CIEDE2000. Treat the threshold as defensible-not-overpromising.
//
// Property 3 — Dichromacy distinguishability under Viénot 1999 linear-
//   RGB simulation for deuteranopia AND protanopia (the two most
//   common dichromacies, ~2-3% of male population combined): minimum
//   simulated pairwise ΔE was 23.9 (deutan) / 27.0 (protan), above
//   the >15 perceivability threshold cited in CVD-palette literature.
//   NOT simulated: tritanopia (~0.01%) and anomalous trichromacies
//   (deuteranomaly + protanomaly, the latter ~5% of male population —
//   the modal CVD condition). For users with anomalous trichromacy,
//   distinguishability is reinforced by (a) stroke-width-as-age
//   (Property 4) — a non-color channel; (b) legend-chip-height
//   mirroring; (c) endpoint R-number text labels. Color is the
//   primary identifier but not the only one.
//
// Property 4 — Stroke-width-as-age, NOT opacity-as-age.
//   `getCurveStrokeWidth` returns 1.0..2.5 px linearly across revision
//   index. Opacity weighting (the prior chart's approach) was
//   abandoned because alpha-compositing the stroke onto the page
//   background reduces rendered contrast monotonically as α drops.
//   In sRGB-encoded compositing (the SVG/CSS default), the rendered
//   pixel is `α·sRGB_color + (1−α)·sRGB_bg` and contrast vs the
//   background is computed against the resulting linearized Y. A
//   numerical sweep at α=0.55 for every swatch in Property 1's band
//   gives a worst-of-band composited contrast of ~2.0:1 (red-600 the
//   only swatch reaching ~2.3:1), all failing the 3:1 threshold. The
//   simpler linear-luminance approximation
//     Y_composite ≈ α·Y_color + (1-α)·Y_bg
//   is convenient but biased — it underestimates composited luminance
//   vs the gamma-encoded calculation. The directional conclusion (α
//   weighting kills the contrast claim) is the same in both spaces;
//   only the magnitude differs. The choice was: drop α weighting.
//
//   To preserve the visual age signal that opacity used to carry,
//   stroke-width is monotonically increased oldest→newest, and the
//   legend chip height is scaled to mirror it (Property 6).
//
// Property 5 — Text-vs-curve decoupling for WCAG 1.4.3 (4.5:1 text):
//   The Y ∈ [0.128, 0.30] band CANNOT clear 4.5:1 against both
//   backgrounds simultaneously — Y ≤ 0.183 (vs white) and Y ≥ 0.216
//   (vs gray-900) have empty intersection. Endpoint labels and any
//   text rendered on top of these colors MUST therefore decouple
//   their fill from the curve color. The chart uses a fixed
//   `text-gray-700 dark:text-gray-300` (`#374151` / `#d1d5db`) pair
//   that clears ≥10:1 in each mode (see `wcagContrast.test.ts`).
//   Curve identification is preserved by spatial proximity (label
//   adjacent to curve endpoint) plus the legend chip swatch.
//
// Property 6 — Legend chip height mirrors stroke-width.
//   `getLegendChipHeight` returns 2..5 px so the legend and the chart
//   encode revision age via the same channel (oldest = thinnest,
//   newest = thickest). Chip background uses the palette swatch
//   (verified at Property 1); chip-adjacent text uses Tailwind's
//   `text-gray-600 dark:text-gray-400` already 1.4.3-compliant.
//
// Selection process — exhaustive search over an 18-element Tailwind
// 600/700 candidate set that individually satisfied Property 1 +
// Property 2 + the Viénot-vs-RESERVED constraints; the chosen 10
// maximize min(deutan_ΔE, protan_ΔE) intra-palette. An 11-element
// solution does not exist under the full constraint stack (DA exit-
// council on PR #108 caught two CVD-vs-RESERVED collisions —
// orange-700↔slip-amber and yellow-700↔slip-amber — plus intra-
// palette protan collisions for {orange-600, lime-700} and
// {violet-600, purple-600}; eliminating each conflict drops one
// candidate, and the remaining feasible set has size 10).
// The selection script is in PR #108's description (not committed
// to `tools/` because the palette is intended to be static;
// re-running requires re-justifying every property above).
//
// All Property 1-3 measurements are reproducible from `wcagContrast.ts`
// and the Viénot matrices inlined in `MultiRevisionSCurveChart.palette.test.ts`.

/**
 * 10 ordered swatches. Order is by hue position (red → rose around the
 * color wheel, skipping the blue band reserved for executed-overlay).
 *
 * The palette size is 10 rather than 11 because the constraint stack
 * (Y∈[0.128,0.300] ∩ ΔE>20 vs RESERVED ∩ Viénot-ΔE>15 vs RESERVED ∩
 * Viénot-ΔE>15 intra-palette) has no feasible 11-element solution
 * across the Tailwind 600/700 candidate space — orange-700 collides
 * with slip-marker amber under deuteranopia (sim_ΔE≈3.2), and
 * orange-600+lime-700 plus violet-600+purple-600 collide under
 * protanopia. The exhaustive-search step at PR #108 verified that
 * 10 is the largest feasible palette size; the chart's max revision
 * count is capped accordingly via runtime RangeError in the helpers.
 */
export const PALETTE_10: readonly string[] = Object.freeze([
	'#dc2626', // 0  red-600
	'#ea580c', // 1  orange-600
	'#65a30d', // 2  lime-600
	'#15803d', // 3  green-700
	'#0f766e', // 4  teal-700
	'#0891b2', // 5  cyan-600
	'#7c3aed', // 6  violet-600
	'#c026d3', // 7  fuchsia-600
	'#db2777', // 8  pink-600
	'#e11d48', // 9  rose-600
]);

/** Fallback color when only one revision is rendered. Matches gray-500. */
export const SINGLE_CURVE_COLOR = '#6b7280';

/** Stroke-width range encoding revision age. */
export const STROKE_WIDTH_MIN = 1.0;
export const STROKE_WIDTH_MAX = 2.5;

/** Legend chip height range (px) — mirrors stroke-width encoding. */
export const LEGEND_CHIP_HEIGHT_MIN = 2;
export const LEGEND_CHIP_HEIGHT_MAX = 5;

function assertCallable(index: number, total: number): void {
	if (total <= 0) {
		throw new RangeError(
			`MultiRevisionSCurveChart palette: total must be ≥ 1, got ${total}`,
		);
	}
	if (total > PALETTE_10.length) {
		// PR #108 ships a 10-slot palette; the backend has no documented
		// hard cap on revision count. If a project ever produces >10
		// revisions, fall back to a runtime error so the chart's caller
		// is forced to either truncate, paginate, or accept that the
		// chart's color-identity guarantee no longer holds. Silent
		// modulo wrap-around would collide colors invisibly.
		throw new RangeError(
			`MultiRevisionSCurveChart palette: total must be ≤ ${PALETTE_10.length}, got ${total}. ` +
				`Cap revision count at the caller or extend PALETTE_10 with re-verified swatches.`,
		);
	}
	if (index < 0 || index >= total) {
		throw new RangeError(
			`MultiRevisionSCurveChart palette: index must be in [0, ${total}), got ${index}`,
		);
	}
}

/**
 * Pick the palette color for revision `index` out of `total` revisions.
 *
 * For total=1, returns `SINGLE_CURVE_COLOR` (no need for palette diversity).
 * For total≥2, distributes indices evenly across the 10-slot palette so
 * that small N gets maximum hue separation (e.g. total=2 → palette[0] and
 * palette[9], not palette[0] and palette[1]).
 *
 * Throws `RangeError` if total < 1, total > 10, or index out of [0, total).
 */
export function getCurveColor(index: number, total: number): string {
	assertCallable(index, total);
	if (total === 1) return SINGLE_CURVE_COLOR;
	const slot = Math.round((index / (total - 1)) * (PALETTE_10.length - 1));
	return PALETTE_10[slot];
}

/**
 * Stroke width for revision `index` of `total` — oldest thinnest, newest thickest.
 *
 * Throws `RangeError` if total < 1, total > 10, or index out of [0, total).
 */
export function getCurveStrokeWidth(index: number, total: number): number {
	assertCallable(index, total);
	if (total === 1) return STROKE_WIDTH_MAX;
	const t = index / (total - 1);
	return STROKE_WIDTH_MIN + (STROKE_WIDTH_MAX - STROKE_WIDTH_MIN) * t;
}

/**
 * Legend chip height (px) for revision `index` of `total` — congruent with stroke-width.
 *
 * Throws `RangeError` if total < 1, total > 10, or index out of [0, total).
 */
export function getLegendChipHeight(index: number, total: number): number {
	assertCallable(index, total);
	if (total === 1) return LEGEND_CHIP_HEIGHT_MAX;
	const t = index / (total - 1);
	return LEGEND_CHIP_HEIGHT_MIN + (LEGEND_CHIP_HEIGHT_MAX - LEGEND_CHIP_HEIGHT_MIN) * t;
}
