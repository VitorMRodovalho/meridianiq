import { describe, it, expect } from 'vitest';
import {
	generateTimeTicks,
	formatDateShort,
	formatDateCompact,
	applyClientGrouping,
	defaultGroupLabel,
	computeDefaultCollapse,
	presetCollapse,
	buildFlatRows,
	computeWBSAggregates,
} from './utils';
import type { ActivityView, WBSNode, ScheduleViewData } from './types';

// ── fixtures ─────────────────────────────────────────────────────────────────
function act(partial: Partial<ActivityView> & { task_id: string }): ActivityView {
	return {
		task_code: partial.task_id,
		task_name: partial.task_id,
		wbs_id: 'W1',
		wbs_path: 'Root / W1',
		indent_level: 1,
		task_type: 'task',
		status: 'not_started',
		early_start: '2026-01-01',
		early_finish: '2026-01-10',
		late_start: '2026-01-01',
		late_finish: '2026-01-10',
		actual_start: null,
		actual_finish: null,
		baseline_start: null,
		baseline_finish: null,
		duration_days: 9,
		remaining_days: 9,
		total_float_days: 0,
		free_float_days: 0,
		progress_pct: 0,
		is_critical: false,
		is_driving: false,
		calendar_id: 'CAL-A',
		constraint_type: '',
		constraint_date: null,
		start_variance_days: null,
		finish_variance_days: null,
		alerts: [],
		...partial,
	};
}

function viewData(activities: ActivityView[], wbs_tree: WBSNode[] = []): ScheduleViewData {
	return {
		project_name: 'Test',
		data_date: '2026-01-01',
		project_start: '2026-01-01',
		project_finish: '2026-12-31',
		wbs_tree,
		activities,
		relationships: [],
		summary: {
			total_activities: activities.length,
			critical_count: 0,
			near_critical_count: 0,
			complete_pct: 0,
			negative_float_count: 0,
			milestones_count: 0,
			relationship_count: 0,
			calendar_count: 1,
		},
	};
}

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

describe('applyClientGrouping — W3 instant client-side regroup', () => {
	it("dimension 'wbs' returns the input object unchanged (identity)", () => {
		const d = viewData([act({ task_id: 'A' })]);
		expect(applyClientGrouping(d, 'wbs')).toBe(d);
	});

	it('groups by status into deterministic _grp ids in semantic order (active, not_started, complete)', () => {
		const d = viewData([
			act({ task_id: 'A', status: 'complete' }),
			act({ task_id: 'B', status: 'active' }),
			act({ task_id: 'C', status: 'not_started' }),
			act({ task_id: 'D', status: 'active' }),
		]);
		const g = applyClientGrouping(d, 'status');
		expect(g.wbs_tree.map((n) => n.wbs_id)).toEqual(['_grp_000', '_grp_001', '_grp_002']);
		expect(g.wbs_tree.map((n) => n.name)).toEqual(['Active', 'Not started', 'Complete']);
		expect(g.wbs_tree.map((n) => n.activity_count)).toEqual([2, 1, 1]);
		// every node is a flat single-level root
		expect(g.wbs_tree.every((n) => n.children.length === 0 && n.depth === 0)).toBe(true);
	});

	it('re-parents activities to bucket ids but PRESERVES the real wbs_path', () => {
		const d = viewData([act({ task_id: 'A', status: 'active', wbs_path: 'Root / Foundations' })]);
		const g = applyClientGrouping(d, 'status');
		expect(g.activities[0].wbs_id).toBe('_grp_000');
		expect(g.activities[0].wbs_path).toBe('Root / Foundations');
	});

	it('critical grouping orders Critical before Non-Critical', () => {
		const d = viewData([
			act({ task_id: 'A', is_critical: false }),
			act({ task_id: 'B', is_critical: true }),
		]);
		const g = applyClientGrouping(d, 'critical');
		expect(g.wbs_tree.map((n) => n.name)).toEqual(['Critical', 'Non-Critical']);
	});

	it('float_bucket bins on total_float_days with backend boundaries and severity order', () => {
		const d = viewData([
			act({ task_id: 'A', total_float_days: -2 }), // neg
			act({ task_id: 'B', total_float_days: 0 }), // 0_5
			act({ task_id: 'C', total_float_days: 5 }), // 0_5 (<=5 inclusive)
			act({ task_id: 'D', total_float_days: 12 }), // 5_20
			act({ task_id: 'E', total_float_days: 20 }), // 5_20 (<=20 inclusive)
			act({ task_id: 'F', total_float_days: 25 }), // gt20
		]);
		const g = applyClientGrouping(d, 'float_bucket');
		expect(g.wbs_tree.map((n) => n.name)).toEqual([
			'Negative float',
			'0–5 days',
			'5–20 days',
			'>20 days',
		]);
		expect(g.wbs_tree.map((n) => n.activity_count)).toEqual([1, 2, 2, 1]);
	});

	it('uses the injected getLabel for node display names (i18n hook)', () => {
		const d = viewData([act({ task_id: 'A', status: 'active' })]);
		const g = applyClientGrouping(d, 'status', (_dim, key) => `<${key}>`);
		expect(g.wbs_tree[0].name).toBe('<active>');
		expect(g.wbs_tree[0].short_name).toBe('<active>');
	});

	it('calendar grouping falls back to "Default" for blank calendar ids', () => {
		const d = viewData([act({ task_id: 'A', calendar_id: '' })]);
		const g = applyClientGrouping(d, 'calendar');
		expect(g.wbs_tree[0].name).toBe('Default');
	});

	it('a synthetic grouped tree feeds buildFlatRows + computeWBSAggregates correctly', () => {
		const d = viewData([
			act({ task_id: 'A', status: 'active', duration_days: 4, total_float_days: 3 }),
			act({ task_id: 'B', status: 'active', duration_days: 6, total_float_days: 1 }),
			act({ task_id: 'C', status: 'complete', duration_days: 2 }),
		]);
		const g = applyClientGrouping(d, 'status');
		const rows = buildFlatRows(g.wbs_tree, g.activities, new Set());
		// 2 group rows + 3 activity rows
		expect(rows.filter((r) => r.type === 'wbs').length).toBe(2);
		expect(rows.filter((r) => r.type === 'activity').length).toBe(3);
		// first row is the Active group, immediately followed by its two activities
		expect(rows[0].type).toBe('wbs');
		expect(rows[0].wbsNode?.name).toBe('Active');
		expect(rows.slice(1, 3).map((r) => r.activity?.task_id)).toEqual(['A', 'B']);

		const agg = computeWBSAggregates(g.activities, g.wbs_tree);
		expect(agg.get('_grp_000')?.count).toBe(2); // Active bucket rolls up A + B
		expect(agg.get('_grp_000')?.min_float).toBe(1);
		expect(agg.get('_grp_001')?.count).toBe(1); // Complete bucket
	});

	it('defaultGroupLabel matches the documented bucket labels', () => {
		expect(defaultGroupLabel('status', 'not_started')).toBe('Not started');
		expect(defaultGroupLabel('critical', 'non_critical')).toBe('Non-Critical');
		expect(defaultGroupLabel('task_type', 'loe')).toBe('LOE');
		expect(defaultGroupLabel('float_bucket', 'neg')).toBe('Negative float');
	});

	it('handles an empty schedule under every dimension without throwing', () => {
		for (const dim of ['status', 'critical', 'task_type', 'calendar', 'float_bucket'] as const) {
			const g = applyClientGrouping(viewData([]), dim);
			expect(g.wbs_tree).toEqual([]);
			expect(g.activities).toEqual([]);
		}
	});
});

describe('computeDefaultCollapse', () => {
	const tree: WBSNode[] = [
		{
			wbs_id: 'R',
			name: 'Root',
			short_name: 'R',
			depth: 0,
			parent_id: '',
			activity_count: 0,
			children: [
				{
					wbs_id: 'C1',
					name: 'C1',
					short_name: 'C1',
					depth: 1,
					parent_id: 'R',
					activity_count: 0,
					children: [],
				},
			],
		},
	];

	it('returns an empty set for small schedules (<=100 activities)', () => {
		expect(computeDefaultCollapse(tree, 50).size).toBe(0);
	});

	it('auto-collapses only PARENT nodes for large schedules (>100 activities)', () => {
		const c = computeDefaultCollapse(tree, 250);
		expect(c.has('R')).toBe(true); // R has children -> collapsed
		expect(c.has('C1')).toBe(false); // leaf -> stays expanded
	});

	it('yields an empty set for a flat (synthetic) tree even when large', () => {
		const flat: WBSNode[] = [
			{ wbs_id: '_grp_000', name: 'Active', short_name: 'Active', depth: 0, parent_id: '', activity_count: 200, children: [] },
		];
		expect(computeDefaultCollapse(flat, 200).size).toBe(0);
	});
});

describe('presetCollapse — shared collapse preset for load + dimension/roll-up reset', () => {
	const tree: WBSNode[] = [
		{
			wbs_id: 'R',
			name: 'Root',
			short_name: 'R',
			depth: 0,
			parent_id: '',
			activity_count: 0,
			children: [
				{ wbs_id: 'C1', name: 'C1', short_name: 'C1', depth: 1, parent_id: 'R', activity_count: 0, children: [] },
			],
		},
	];

	it('returns an empty set for ANY non-WBS dimension (depth is ignored when flattened)', () => {
		expect(presetCollapse('status', 0, tree, 250).size).toBe(0);
		// the key regression guard: switching to a flat dim while a roll-up level was set must NOT
		// carry that level over — a flat synthetic tree has nothing to collapse.
		expect(presetCollapse('status', 3, tree, 250).size).toBe(0);
		expect(presetCollapse('float_bucket', 2, tree, 250).size).toBe(0);
	});

	it('WBS + level 0 yields the large-schedule auto-collapse default', () => {
		expect(presetCollapse('wbs', 0, tree, 50).size).toBe(0); // small → expanded
		expect(presetCollapse('wbs', 0, tree, 250).has('R')).toBe(true); // large → parents collapsed
	});

	it('WBS + level N collapses at/below that depth (roll-up-to-level)', () => {
		const c = presetCollapse('wbs', 2, tree, 50);
		expect(c.has('C1')).toBe(true); // depth 2 collapsed
		expect(c.has('R')).toBe(false); // depth 1 stays expanded
	});
});

describe('date formatters — locale threading (#176)', () => {
	it('formatDateShort defaults to en-US (byte-compat for untouched callers)', () => {
		expect(formatDateShort('2026-01-15')).toBe('Jan 15');
	});

	// Locale assertions are TOKEN-based (not exact-string) on purpose: Intl
	// short-month/weekday output is ICU/CLDR-version-dependent (connector words,
	// casing, and the space character have all drifted across CLDR releases).
	// Pinning tokens + forbidden characters survives a Node/ICU bump; pinning
	// the full string does not.
	const FORBIDDEN = /[.\u202F\u00A0]/; // abbrev dots + NNBSP/NBSP must be normalized out

	it('formatDateShort localizes month tokens, dotless and NNBSP-free', () => {
		const pt = formatDateShort('2026-01-15', 'pt-BR');
		const es = formatDateShort('2026-01-15', 'es');
		expect(pt.toLowerCase()).toContain('jan'); // pt-BR Intl yields "15 de jan." pre-normalization
		expect(pt).toContain('15');
		expect(es.toLowerCase()).toContain('ene');
		expect(es).toContain('15');
		expect(pt).not.toMatch(FORBIDDEN);
		expect(es).not.toMatch(FORBIDDEN);
	});

	it('formatDateCompact keeps the P6 d-MMM-yy skeleton across locales, dotless', () => {
		expect(formatDateCompact('2026-01-15')).toBe('15-Jan-26');
		// case-normalized: es/pt month-abbrev casing has shifted across CLDR versions
		expect(formatDateCompact('2026-01-15', 'pt-BR').toLowerCase()).toBe('15-jan-26');
		expect(formatDateCompact('2026-01-15', 'es').toLowerCase()).toBe('15-ene-26');
		expect(formatDateCompact('2026-01-15', 'pt-BR')).not.toMatch(FORBIDDEN);
		expect(formatDateCompact('2026-01-15', 'es')).not.toMatch(FORBIDDEN);
	});

	it('empty input still returns empty string regardless of locale', () => {
		expect(formatDateShort('', 'pt-BR')).toBe('');
		expect(formatDateCompact('', 'es')).toBe('');
	});

	it('generateTimeTicks localizes minor + major labels without trailing dots', () => {
		const axis = generateTimeTicks('2026-01-01', '2026-03-31', 'week', 1200, 'pt-BR');
		expect(axis.minor[0].label.toLowerCase()).toContain('jan');
		expect(axis.major[0].label.toLowerCase()).toContain('jan');
		for (const label of [...axis.minor.map((m) => m.label), ...axis.major.map((m) => m.label)]) {
			expect(label).not.toContain('.');
		}
	});

	it('generateTimeTicks day-zoom weekday labels are localized and dotless (pt-BR "seg." → "seg")', () => {
		const axis = generateTimeTicks('2026-01-05', '2026-01-16', 'day', 1200, 'pt-BR');
		for (const tick of axis.minor) {
			expect(tick.label).not.toContain('.');
		}
		// 2026-01-05 is a Monday → "seg" in pt-BR
		expect(axis.minor[0].label.toLowerCase()).toContain('seg');
	});

	it('generateTimeTicks default stays en-US (existing pins remain valid)', () => {
		const axis = generateTimeTicks('2026-01-01', '2026-03-31', 'week');
		expect(axis.major[0].label).toMatch(/Jan/);
	});
});
