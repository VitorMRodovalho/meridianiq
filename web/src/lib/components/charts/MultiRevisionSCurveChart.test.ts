// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// Direction-aware change-point marker encoding (issue #105). Vitest +
// @testing-library/svelte. Three tests per frontend-ux-reviewer entry-
// council P2-4 cap — one per direction, each asserting BOTH the color
// (color channel) AND the stroke-dasharray (non-color channel required
// by WCAG 1.4.1 — P1-1). The flat-at-last-revision edge case (P1-4)
// folds into the flat test by placing the change point on the executed
// revision.
//
// Out of scope: full chart-rendering snapshots, single-revision empty
// state, legend collapse, calendar-alignment fallback, endpoint labels.
// Each could merit its own test in a future hardening PR.

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';
import MultiRevisionSCurveChart from './MultiRevisionSCurveChart.svelte';
import type { RevisionCurveSchema, ChangePointMarkerSchema } from '$lib/types';

// jsdom does not implement window.matchMedia; the chart's mobile-legend
// $effect at MultiRevisionSCurveChart.svelte:48 calls it unconditionally.
// Stub once before tests with matches=false (desktop layout) — these tests
// do NOT exercise the mobile-legend-collapse branch, so a flat stub is
// sufficient.
beforeAll(() => {
	Object.defineProperty(window, 'matchMedia', {
		writable: true,
		value: vi.fn().mockImplementation((query: string) => ({
			matches: false,
			media: query,
			onchange: null,
			addEventListener: vi.fn(),
			removeEventListener: vi.fn(),
			addListener: vi.fn(),
			removeListener: vi.fn(),
			dispatchEvent: vi.fn(),
		})),
	});
});

afterEach(() => cleanup());

function curve(rev: number, dataDate: string, isExecuted = false): RevisionCurveSchema {
	return {
		project_id: 'proj-test',
		revision_id: `rev-${rev}`,
		revision_number: rev,
		data_date: dataDate,
		points: [
			{
				day_offset: 0,
				planned_cumulative_pct: 0,
				actual_cumulative_pct: isExecuted ? 0 : null,
			},
			{
				day_offset: 60,
				planned_cumulative_pct: 1,
				actual_cumulative_pct: isExecuted ? 0.5 : null,
			},
		],
		is_executed: isExecuted,
	};
}

function changePoint(
	revIdx: number,
	direction: 'slip' | 'improvement' | 'flat',
	delta: number,
): ChangePointMarkerSchema {
	return {
		revision_index: revIdx,
		revision_id: `rev-${revIdx + 1}`,
		delta_days: delta,
		cusum_value: 0,
		direction,
		description: `shift of ${delta} days vs prior revision`,
	};
}

function markerLines(container: HTMLElement): SVGLineElement[] {
	return Array.from(
		container.querySelectorAll<SVGLineElement>('line[stroke-dasharray]'),
	);
}

describe('MultiRevisionSCurveChart change-point direction encoding (issue #105)', () => {
	it('renders slip markers with amber color (#b45309) and dasharray "4 3"', () => {
		const { container } = render(MultiRevisionSCurveChart, {
			props: {
				curves: [curve(1, '2026-01-01'), curve(2, '2026-02-01')],
				changePoints: [changePoint(1, 'slip', 40)],
				directionLabels: { slip: 'Slip', improvement: 'Improvement', flat: 'Flat' },
			},
		});
		const lines = markerLines(container);
		expect(lines.length).toBe(1);
		const marker = lines[0];
		expect(marker.getAttribute('stroke')).toBe('#b45309');
		expect(marker.getAttribute('stroke-dasharray')).toBe('4 3');
		expect(marker.getAttribute('class')).toContain('dark:stroke-amber-400');
		const title = marker.querySelector('title');
		expect(title?.textContent).toContain('Slip');
	});

	it('renders improvement markers with emerald color (#047857) and dasharray "2 2 6 2"', () => {
		const { container } = render(MultiRevisionSCurveChart, {
			props: {
				curves: [curve(1, '2026-01-01'), curve(2, '2026-02-01')],
				changePoints: [changePoint(1, 'improvement', -20)],
				directionLabels: { slip: 'Slip', improvement: 'Improvement', flat: 'Flat' },
			},
		});
		const lines = markerLines(container);
		expect(lines.length).toBe(1);
		const marker = lines[0];
		expect(marker.getAttribute('stroke')).toBe('#047857');
		expect(marker.getAttribute('stroke-dasharray')).toBe('2 2 6 2');
		expect(marker.getAttribute('class')).toContain('dark:stroke-emerald-400');
		const title = marker.querySelector('title');
		expect(title?.textContent).toContain('Improvement');
	});

	it('renders flat markers with gray color (#4b5563) and dotted dasharray "1 3" even on the executed revision (P1-4 fixture)', () => {
		// Flat-at-last-revision edge case (frontend-ux-reviewer entry-council
		// P1-4). Change point on the executed revision (R2). Two things to pin:
		// (a) the marker attributes (color + dasharray + a11y title) so a
		//     future refactor cannot silently drop the encoding; and
		// (b) DOM source order — the marker `<line>` must appear AFTER the
		//     executed-curve `<path stroke="#3b82f6">` so SVG painter-order
		//     puts the marker on top. A swap of these two render blocks
		//     would silently regress visibility.
		const { container } = render(MultiRevisionSCurveChart, {
			props: {
				curves: [curve(1, '2026-01-01'), curve(2, '2026-02-01', true)],
				changePoints: [changePoint(1, 'flat', 0)],
				directionLabels: { slip: 'Slip', improvement: 'Improvement', flat: 'Flat' },
			},
		});
		const lines = markerLines(container);
		expect(lines.length).toBe(1);
		const marker = lines[0];
		expect(marker.getAttribute('stroke')).toBe('#4b5563');
		expect(marker.getAttribute('stroke-dasharray')).toBe('1 3');
		expect(marker.getAttribute('class')).toContain('dark:stroke-gray-400');
		const title = marker.querySelector('title');
		expect(title?.textContent).toContain('Flat');

		// z-order pin: executed-curve path precedes marker in source order.
		const executedPath = container.querySelector('path[stroke="#3b82f6"]');
		expect(executedPath).not.toBeNull();
		const cmp = marker.compareDocumentPosition(executedPath!);
		// DOCUMENT_POSITION_PRECEDING bit set on the result of A.compare(B)
		// means B precedes A in document order — i.e., the executed path
		// renders BEFORE the marker, so the marker paints on top.
		expect(cmp & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
	});
});

// WCAG palette + stroke-width-as-age + decoupled endpoint-text-fill
// rendering checks (issue #108). Light chart-level smoke tests; the
// heavy palette/contrast/CVD verification lives in
// `MultiRevisionSCurveChart.palette.test.ts`.

import { PALETTE_11 } from './MultiRevisionSCurveChart.palette';

function plannedPaths(container: HTMLElement): SVGPathElement[] {
	// Planned-curve paths are the <path> elements with stroke attribute
	// pointing at a palette swatch and NO is-actual marker. Selecting
	// any path with a fill="none" stroke that's not the executed-blue
	// hex catches them.
	return Array.from(
		container.querySelectorAll<SVGPathElement>('path[fill="none"]'),
	).filter((p) => p.getAttribute('stroke') !== '#3b82f6');
}

describe('MultiRevisionSCurveChart palette + stroke-width-as-age (issue #108)', () => {
	it('renders planned curves using palette hex values, not HSL', () => {
		const { container } = render(MultiRevisionSCurveChart, {
			props: {
				curves: [
					curve(1, '2026-01-01'),
					curve(2, '2026-02-01'),
					curve(3, '2026-03-01'),
				],
				changePoints: [],
				directionLabels: { slip: 'Slip', improvement: 'Improvement', flat: 'Flat' },
			},
		});
		const paths = plannedPaths(container);
		expect(paths.length).toBe(3);
		for (const p of paths) {
			const stroke = p.getAttribute('stroke') ?? '';
			// Must be a 6-char hex from PALETTE_11 — the prior HSL palette
			// rendered as `hsl(...)` strings which start with 'hsl'.
			expect(stroke.startsWith('hsl(')).toBe(false);
			expect(PALETTE_11).toContain(stroke);
		}
	});

	it('assigns monotone-increasing stroke-width across revision order', () => {
		const { container } = render(MultiRevisionSCurveChart, {
			props: {
				curves: [
					curve(1, '2026-01-01'),
					curve(2, '2026-02-01'),
					curve(3, '2026-03-01'),
					curve(4, '2026-04-01'),
				],
				changePoints: [],
				directionLabels: { slip: 'Slip', improvement: 'Improvement', flat: 'Flat' },
			},
		});
		const paths = plannedPaths(container);
		expect(paths.length).toBe(4);
		const widths = paths.map((p) => Number(p.getAttribute('stroke-width')));
		// Strictly increasing — encoding revision age via stroke-width-as-
		// pre-attentive channel per council option (γ) on issue #108. A
		// silent revert to opacity-as-age or constant width would trip this.
		for (let i = 1; i < widths.length; i++) {
			expect(widths[i]).toBeGreaterThan(widths[i - 1]);
		}
	});

	it('omits any opacity attribute on planned curves (age routed to stroke-width, not alpha)', () => {
		const { container } = render(MultiRevisionSCurveChart, {
			props: {
				curves: [curve(1, '2026-01-01'), curve(2, '2026-02-01')],
				changePoints: [],
				directionLabels: { slip: 'Slip', improvement: 'Improvement', flat: 'Flat' },
			},
		});
		const paths = plannedPaths(container);
		for (const p of paths) {
			// Pre-#108 the chart set opacity=0.55..1.0 here; alpha-
			// compositing made composited contrast fall below WCAG 3:1
			// at low α. The current chart removes the attribute entirely.
			expect(p.hasAttribute('opacity')).toBe(false);
		}
	});

	it('renders endpoint label text with decoupled gray fill (not curve hex)', () => {
		// Endpoint labels are visible when curves.length <= 8.
		const { container } = render(MultiRevisionSCurveChart, {
			props: {
				curves: [curve(1, '2026-01-01'), curve(2, '2026-02-01')],
				changePoints: [],
				directionLabels: { slip: 'Slip', improvement: 'Improvement', flat: 'Flat' },
			},
		});
		// The endpoint text labels carry font-weight="500" — that's the
		// most discriminating attribute on them, given the chart also has
		// axis-label and change-point-label text nodes.
		const endpointTexts = Array.from(
			container.querySelectorAll<SVGTextElement>('text[font-weight="500"]'),
		);
		expect(endpointTexts.length).toBe(2);
		for (const t of endpointTexts) {
			// Decoupled fill: light-mode #374151, dark-mode-class fall-through.
			// WCAG 1.4.3 (4.5:1 text) requires the fixed gray pair because
			// the palette swatches sit in Y∈[0.128,0.30] which cannot clear
			// 4.5:1 against both backgrounds simultaneously.
			expect(t.getAttribute('fill')).toBe('#374151');
			expect(t.getAttribute('class')).toContain('dark:fill-gray-300');
		}
	});
});
