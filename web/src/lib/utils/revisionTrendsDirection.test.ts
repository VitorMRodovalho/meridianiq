// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// Unit test for the page list-row color helper. DA P0 #2 on Cycle 6
// W3 wave 4: pinning the slip/improvement/flat → text-class mapping
// here means a future PR that changes the chart marker hex set
// without updating the list helper (or vice versa) will surface as
// a test failure rather than a silent visual divergence.

import { describe, expect, it } from 'vitest';
import { directionTextClass } from './revisionTrendsDirection';

describe('directionTextClass', () => {
	it('maps slip to amber tokens', () => {
		const cls = directionTextClass('slip');
		expect(cls).toContain('text-amber-700');
		expect(cls).toContain('dark:text-amber-400');
	});

	it('maps improvement to emerald tokens', () => {
		const cls = directionTextClass('improvement');
		expect(cls).toContain('text-emerald-700');
		expect(cls).toContain('dark:text-emerald-400');
	});

	it('maps flat (and unknown values) to neutral gray', () => {
		expect(directionTextClass('flat')).toContain('text-gray-600');
		// Unknown direction string falls through to gray rather than
		// erroring out — same defense the chart's directionVisual uses.
		expect(directionTextClass('partial_recovery')).toContain('text-gray-600');
	});
});
