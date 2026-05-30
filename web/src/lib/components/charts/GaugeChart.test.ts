// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// GaugeChart valueFormat + non-finite/degenerate guards (W2 chart-completeness).
// Entry-council mandatories pinned here:
//   1. the default integer formatter keeps the eleven 0-100 score callers
//      byte-identical to the legacy {Math.round(value)} readout;
//   2. EVM SPI/CPI callers opt into toFixed(2) so 1.05 reads "1.05", not "1";
//   3. a NaN / undefined value renders "--", a neutral arc, NO needle, and
//      NEVER leaks "NaN"/"undefined" into SVG attributes nor the aria-label;
//   4. max === min does not divide-by-zero.
// GaugeChart uses no window.matchMedia, so (unlike MultiRevisionSCurveChart)
// these tests need no matchMedia stub.

import { afterEach, describe, expect, it } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';
import GaugeChart from './GaugeChart.svelte';

afterEach(() => cleanup());

/** The centre readout is the single 26px bold <text>. */
function centerText(container: HTMLElement): string {
	const texts = Array.from(container.querySelectorAll('text'));
	const big = texts.find((t) => t.getAttribute('font-size') === '26');
	return big?.textContent?.trim() ?? '';
}

describe('GaugeChart valueFormat (W2)', () => {
	it('defaults to integer rounding — byte-identical to the legacy {Math.round(value)} readout', () => {
		const { container } = render(GaugeChart, { props: { value: 84.6, max: 100 } });
		expect(centerText(container)).toBe('85');
	});

	it('honours a toFixed(2) formatter for EVM SPI/CPI (1.05 → "1.05", not "1")', () => {
		const { container } = render(GaugeChart, {
			props: { value: 1.05, min: 0, max: 1.5, valueFormat: (v: number) => v.toFixed(2) },
		});
		expect(centerText(container)).toBe('1.05');
	});

	it('renders a value above max truthfully via the formatter (SPI 1.8 on a max=1.5 gauge)', () => {
		const { container } = render(GaugeChart, {
			props: { value: 1.8, min: 0, max: 1.5, valueFormat: (v: number) => v.toFixed(2) },
		});
		expect(centerText(container)).toBe('1.80');
	});
});

describe('GaugeChart non-finite / degenerate guards (W2)', () => {
	it('renders "--" for NaN and never leaks NaN/undefined into the SVG or aria-label', () => {
		const { container } = render(GaugeChart, { props: { value: NaN, max: 100, title: 'Health' } });
		expect(centerText(container)).toBe('--');
		const svg = container.querySelector('svg')!;
		expect(svg.innerHTML).not.toContain('NaN');
		expect(svg.innerHTML).not.toContain('undefined');
		// aria-label degrades to "Health: --" (not "Health: NaN") for screen readers.
		expect(svg.getAttribute('aria-label')).toBe('Health: --');
		// No needle dot for non-finite input (the only <circle> in the chart).
		expect(svg.querySelector('circle')).toBeNull();
	});

	it('does not divide-by-zero when max === min', () => {
		const { container } = render(GaugeChart, { props: { value: 50, min: 50, max: 50 } });
		const svg = container.querySelector('svg')!;
		expect(svg.innerHTML).not.toContain('NaN');
		expect(centerText(container)).toBe('50');
	});
});
