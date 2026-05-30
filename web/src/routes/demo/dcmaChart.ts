// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// Pure transform behind the /demo DCMA margin chart (W2 chart-completeness).
// Kept out of the .svelte file so the margin math is unit-testable.

import type { DemoDCMAMetric } from '$lib/api';

export interface DcmaMarginBar extends DemoDCMAMetric {
	/**
	 * Percentage-points of headroom to the DCMA threshold, as a MAGNITUDE with a
	 * display-derived sign. `|margin|` is the distance from the threshold.
	 *
	 * The sign is computed from `value`, which the backend rounds to 1 decimal
	 * (upload.py), whereas the authoritative `passed` flag is computed on the
	 * unrounded percentage. Within ±0.05pp of a threshold the two can therefore
	 * disagree, so consumers MUST drive pass/fail (colour AND which side of the
	 * zero baseline) from `passed` — never from `Math.sign(margin)` — and use
	 * `|margin|` only for bar length.
	 */
	margin: number;
}

/**
 * Percentage-based DCMA 14-Point checks (`unit === '%'`) expressed as
 * margin-to-threshold:
 *
 *   margin = direction === 'max' ? value - threshold : threshold - value
 *
 * This makes bar LENGTH monotonic (larger = healthier) and sign-encoded
 * (pass/fail), so a diverging bar from a zero baseline reads consistently
 * regardless of whether an individual check is "lower-is-better" (min) or
 * "higher-is-better" (max) — avoiding the mixed-direction length-channel
 * ambiguity of plotting raw percentages on one axis. It is subtraction-only,
 * so it is well-defined for the three threshold=0 checks (Leads, Negative
 * Float, Invalid Dates) where a value/threshold ratio would divide by zero.
 *
 * The three ratio/index checks (CPLI, BEI, Critical Path Test; `unit === ''`)
 * are excluded — they live on a different scale and remain in the 14-card grid.
 *
 * Returns worst-first (most-negative margin at the top).
 */
export function dcmaMarginBars(metrics: DemoDCMAMetric[]): DcmaMarginBar[] {
	return metrics
		.filter((m) => m.unit === '%')
		.map((m) => ({
			...m,
			margin: m.direction === 'max' ? m.value - m.threshold : m.threshold - m.value,
		}))
		.sort((a, b) => a.margin - b.margin);
}

/** Comparator glyph for the threshold given the check's pass direction. */
export function thresholdComparator(direction: string): string {
	return direction === 'max' ? '≥' : '≤';
}
