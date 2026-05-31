// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// ResourceChart empty-state + optional axis titles (W2 chart-completeness).
// Entry-council mandatories: (1) an empty demand series renders a "No data"
// affordance instead of a blank axis box with Infinity/NaN coordinates
// (barW = chartW/0 today); (2) the optional axis titles are additive — the
// default render emits NO extra <text> nodes, keeping the two existing
// callers byte-identical.

import { afterEach, describe, expect, it } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';
import ResourceChart from './ResourceChart.svelte';

afterEach(() => cleanup());

describe('ResourceChart empty state (W2)', () => {
	it('renders the empty label and no <svg> when there is no demand series', () => {
		const { container } = render(ResourceChart, { props: { demandByDay: [], maxUnits: 10 } });
		expect(container.querySelector('svg')).toBeNull();
		expect(container.textContent).toContain('No data');
	});

	it('honours a custom emptyLabel', () => {
		const { container } = render(ResourceChart, {
			props: { demandByDay: [], maxUnits: 10, emptyLabel: 'No resource assignments' },
		});
		expect(container.textContent).toContain('No resource assignments');
	});

	it('never emits Infinity/NaN coordinates for an empty series', () => {
		const { container } = render(ResourceChart, { props: { demandByDay: [], maxUnits: 10 } });
		expect(container.innerHTML).not.toContain('NaN');
		expect(container.innerHTML).not.toContain('Infinity');
	});
});

describe('ResourceChart axis titles (W2)', () => {
	it('emits no axis-title <text> by default (callers byte-identical)', () => {
		const { container } = render(ResourceChart, { props: { demandByDay: [1, 2, 3], maxUnits: 5 } });
		const svg = container.querySelector('svg')!;
		// The base `fill-gray-500` class is used only by the optional axis titles
		// (tick labels use fill-gray-400, capacity uses fill-red-500).
		expect(svg.querySelector('text.fill-gray-500')).toBeNull();
	});

	it('renders x and y axis titles when provided', () => {
		const { container } = render(ResourceChart, {
			props: { demandByDay: [1, 2, 3], maxUnits: 5, xAxisLabel: 'Day', yAxisLabel: 'units' },
		});
		const titles = Array.from(container.querySelectorAll('svg text')).map((t) =>
			t.textContent?.trim()
		);
		expect(titles).toContain('Day');
		expect(titles).toContain('units');
	});
});
