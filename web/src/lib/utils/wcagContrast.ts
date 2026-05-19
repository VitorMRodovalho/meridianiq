// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// WCAG 2.2 contrast computation primitives.
//
// Pure functions for sRGB→linear conversion, relative luminance, and
// contrast ratio per W3C "Understanding SC 1.4.3" and "Relative luminance".
// Used by chart components to verify palette swatches clear WCAG AA
// thresholds:
//   - 1.4.11 Non-text Contrast (AA): ≥3:1 for graphical objects vs adjacent color
//   - 1.4.3  Contrast Minimum  (AA): ≥4.5:1 for normal text
//
// References:
//   - https://www.w3.org/TR/WCAG22/#dfn-relative-luminance
//   - https://www.w3.org/TR/WCAG22/#dfn-contrast-ratio
//
// Scope discipline: this file COMPUTES only — no palette decisions, no
// component-specific helpers. Adding decide-functions (recommendedColor,
// getAccessiblePaletteFor, etc.) belongs to a future a11y-pattern ADR.

function parseHex(hex: string): [number, number, number] {
	const m = /^#([0-9a-f]{6})$/i.exec(hex);
	if (!m) throw new Error(`wcagContrast: invalid hex "${hex}" (expected #rrggbb)`);
	const v = parseInt(m[1], 16);
	return [(v >> 16) & 0xff, (v >> 8) & 0xff, v & 0xff];
}

export function srgbToLinear(channel: number): number {
	const c = channel / 255;
	return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

export function relativeLuminance(hex: string): number {
	const [r, g, b] = parseHex(hex);
	return (
		0.2126 * srgbToLinear(r) +
		0.7152 * srgbToLinear(g) +
		0.0722 * srgbToLinear(b)
	);
}

export function contrastRatio(hex1: string, hex2: string): number {
	const l1 = relativeLuminance(hex1);
	const l2 = relativeLuminance(hex2);
	const [lo, hi] = l1 < l2 ? [l1, l2] : [l2, l1];
	return (hi + 0.05) / (lo + 0.05);
}
