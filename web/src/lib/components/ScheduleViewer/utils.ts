/** Convert ISO date string to Date object. */
export function parseDate(iso: string): Date {
	return new Date(iso + 'T00:00:00');
}

/** Days between two ISO date strings. */
export function daysBetween(start: string, end: string): number {
	const s = parseDate(start);
	const e = parseDate(end);
	return Math.round((e.getTime() - s.getTime()) / 86_400_000);
}

/** Format date as short label (e.g. "Jan 15"). */
export function formatDateShort(iso: string): string {
	if (!iso) return '';
	const d = parseDate(iso);
	return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Format date as full (e.g. "2026-01-15"). */
export function formatDateFull(iso: string): string {
	return iso?.slice(0, 10) || '';
}

export interface TimeTick {
	date: string;
	label: string;
	x: number; // fraction 0..1 of the chart width
}

export interface MajorTick {
	label: string;
	x: number; // fraction 0..1 — left edge of the band
	xEnd: number; // fraction 0..1 — right edge of the band
}

export interface TimeAxis {
	minor: TimeTick[];
	major: MajorTick[];
}

/** Build the coarse "major" tier: contiguous year (or month) bands for context. */
function buildMajorTier(
	start: Date,
	end: Date,
	startIso: string,
	totalDays: number,
	unit: 'year' | 'month',
): MajorTick[] {
	// Boundary dates: the chart start, then each first-of-next-unit up to end.
	const boundaries: Date[] = [new Date(start)];
	const cursor = new Date(start);
	if (unit === 'year') {
		cursor.setMonth(0, 1);
		cursor.setFullYear(cursor.getFullYear() + 1);
	} else {
		cursor.setDate(1);
		cursor.setMonth(cursor.getMonth() + 1);
	}
	while (cursor <= end) {
		boundaries.push(new Date(cursor));
		if (unit === 'year') cursor.setFullYear(cursor.getFullYear() + 1);
		else cursor.setMonth(cursor.getMonth() + 1);
	}

	const major: MajorTick[] = [];
	for (let i = 0; i < boundaries.length; i++) {
		const b = boundaries[i];
		// First band starts at the chart's left edge regardless of where the
		// start date falls within its unit.
		const x = i === 0 ? 0 : daysBetween(startIso, b.toISOString().slice(0, 10)) / totalDays;
		const next = boundaries[i + 1];
		const xEnd = next ? daysBetween(startIso, next.toISOString().slice(0, 10)) / totalDays : 1;
		const label =
			unit === 'year'
				? String(b.getFullYear())
				: b.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
		major.push({ label, x, xEnd });
	}
	return major;
}

/** Generate a TWO-TIER time axis: a coarse `major` tier (year over month, or
 *  month over week/day) for context, plus a fine `minor` tier with adaptive
 *  density. A single flat tier is the most-cited reason a Gantt "looks off".
 */
export function generateTimeTicks(
	startDate: string,
	endDate: string,
	zoomLevel: 'day' | 'week' | 'month',
	svgWidth: number = 1200,
): TimeAxis {
	const start = parseDate(startDate);
	const end = parseDate(endDate);
	const totalDays = Math.max(1, daysBetween(startDate, endDate));
	const minor: TimeTick[] = [];

	// Minimum pixel distance between labels (prevents overlap)
	const MIN_PX = 48;
	const maxLabels = Math.min(25, Math.floor(svgWidth / MIN_PX));

	let stepDays: number;
	if (zoomLevel === 'month') {
		stepDays = Math.max(30, Math.ceil(totalDays / maxLabels / 30) * 30);
	} else if (zoomLevel === 'week') {
		stepDays = Math.max(7, Math.ceil(totalDays / maxLabels / 7) * 7);
	} else {
		stepDays = Math.max(1, Math.ceil(totalDays / maxLabels));
	}

	const current = new Date(start);
	while (current <= end) {
		const iso = current.toISOString().slice(0, 10);
		const x = daysBetween(startDate, iso) / totalDays;

		// The year/long context now lives in the major tier, so the minor label
		// stays compact (month name, or month+day at finer zooms).
		let label: string;
		if (stepDays >= 28 || zoomLevel === 'month') {
			label = current.toLocaleDateString('en-US', { month: 'short' });
		} else if (stepDays >= 5) {
			label = current.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
		} else {
			label = current.toLocaleDateString('en-US', { weekday: 'short', day: 'numeric' });
		}

		minor.push({ date: iso, label, x });
		current.setDate(current.getDate() + stepDays);
	}

	const majorUnit: 'year' | 'month' = zoomLevel === 'month' ? 'year' : 'month';
	return { minor, major: buildMajorTier(start, end, startDate, totalDays, majorUnit) };
}

/** Format date as compact column label (e.g. "15-Jan-26"). */
export function formatDateCompact(iso: string): string {
	if (!iso) return '';
	const d = parseDate(iso);
	const day = d.getDate();
	const mon = d.toLocaleDateString('en-US', { month: 'short' });
	const yr = d.getFullYear().toString().slice(-2);
	return `${day}-${mon}-${yr}`;
}

import type { ActivityView, WBSNode, WBSAggregate, FlatRow, GroupDimension, ScheduleViewData } from './types';

/** Build a map of wbs_id -> set of all descendant wbs_ids (including self). */
function collectDescendantIds(nodes: WBSNode[]): Map<string, Set<string>> {
	const result = new Map<string, Set<string>>();

	function walk(node: WBSNode): Set<string> {
		const ids = new Set<string>([node.wbs_id]);
		for (const child of node.children) {
			for (const id of walk(child)) {
				ids.add(id);
			}
		}
		result.set(node.wbs_id, ids);
		return ids;
	}

	for (const root of nodes) {
		walk(root);
	}
	return result;
}

/** Compute WBS aggregates for all nodes (recursive rollup). */
export function computeWBSAggregates(
	activities: ActivityView[],
	wbsTree: WBSNode[],
): Map<string, WBSAggregate> {
	const descendantMap = collectDescendantIds(wbsTree);
	const result = new Map<string, WBSAggregate>();

	for (const [wbsId, descendantIds] of descendantMap) {
		let start = '';
		let finish = '';
		let count = 0;
		let totalDuration = 0;
		let minFloat = Infinity;
		let weightedProgress = 0;
		let totalWeight = 0;
		let criticalCount = 0;
		let blStart: string | null = null;
		let blFinish: string | null = null;

		for (const act of activities) {
			if (!descendantIds.has(act.wbs_id)) continue;
			if (!act.early_start || !act.early_finish) continue;

			count++;
			if (!start || act.early_start < start) start = act.early_start;
			if (!finish || act.early_finish > finish) finish = act.early_finish;

			totalDuration += act.duration_days;
			if (act.total_float_days < minFloat) minFloat = act.total_float_days;

			const weight = Math.max(act.duration_days, 0.1);
			weightedProgress += act.progress_pct * weight;
			totalWeight += weight;

			if (act.is_critical) criticalCount++;

			if (act.baseline_start && (!blStart || act.baseline_start < blStart)) blStart = act.baseline_start;
			if (act.baseline_finish && (!blFinish || act.baseline_finish > blFinish)) blFinish = act.baseline_finish;
		}

		if (count > 0) {
			result.set(wbsId, {
				start,
				finish,
				count,
				total_duration: totalDuration,
				min_float: minFloat === Infinity ? 0 : minFloat,
				weighted_progress: weightedProgress,
				total_weight: totalWeight,
				critical_count: criticalCount,
				baseline_start: blStart,
				baseline_finish: blFinish,
			});
		}
	}

	return result;
}

/** Status to color mapping. */
export const STATUS_COLORS: Record<string, string> = {
	complete: '#10b981',
	active: '#3b82f6',
	not_started: '#9ca3af',
};

/** Get bar color for an activity. */
export function getBarColor(status: string, isCritical: boolean): string {
	if (isCritical && status !== 'complete') return '#ef4444';
	return STATUS_COLORS[status] || '#9ca3af';
}

/**
 * Build flat row list from WBS tree + activities.
 * Single source of truth — shared by WBSTree and GanttCanvas.
 * When pruneEmpty=true, skips WBS nodes with 0 matching descendant activities.
 */
export function buildFlatRows(
	wbsTree: WBSNode[],
	activities: ActivityView[],
	collapsedWbs: Set<string>,
	pruneEmpty: boolean = false,
): FlatRow[] {
	// Pre-compute which WBS IDs have matching activities (including via descendants)
	let activeWbs: Set<string> | null = null;
	if (pruneEmpty) {
		activeWbs = new Set<string>();
		for (const act of activities) {
			activeWbs.add(act.wbs_id);
		}
		// Walk tree bottom-up: mark parents that have descendants with activities
		function markParents(nodes: WBSNode[]): boolean {
			let hasAny = false;
			for (const node of nodes) {
				const childrenHave = markParents(node.children);
				if (childrenHave || activeWbs!.has(node.wbs_id)) {
					activeWbs!.add(node.wbs_id);
					hasAny = true;
				}
			}
			return hasAny;
		}
		markParents(wbsTree);
	}

	const rows: FlatRow[] = [];

	function addNode(node: WBSNode, indent: number, parentPath: string) {
		if (activeWbs && !activeWbs.has(node.wbs_id)) return;

		const path = parentPath ? `${parentPath} / ${node.name}` : node.name;
		rows.push({ type: 'wbs', wbsNode: node, indent, wbsPath: path });

		if (!collapsedWbs.has(node.wbs_id)) {
			for (const act of activities) {
				if (act.wbs_id === node.wbs_id) {
					rows.push({ type: 'activity', activity: act, indent: indent + 1 });
				}
			}
			for (const child of node.children) {
				addNode(child, indent + 1, path);
			}
		}
	}

	for (const root of wbsTree) {
		addNode(root, 0, '');
	}

	return rows;
}

/** Get max WBS depth in the tree. */
export function getMaxWBSDepth(nodes: WBSNode[]): number {
	let max = 0;
	function walk(nodes: WBSNode[], depth: number) {
		for (const node of nodes) {
			if (depth > max) max = depth;
			walk(node.children, depth + 1);
		}
	}
	walk(nodes, 1);
	return max;
}

/** Collect every ActivityView whose wbs_id falls under the given WBS node —
 *  including activities in all descendant WBS nodes. Order matches the
 *  supplied ``activities`` list. Used by per-WBS print export. */
export function collectActivitiesByWbs(
	node: WBSNode,
	activities: ActivityView[],
): ActivityView[] {
	const ids = new Set<string>();
	function walk(n: WBSNode) {
		ids.add(n.wbs_id);
		for (const child of n.children) walk(child);
	}
	walk(node);
	return activities.filter((a) => ids.has(a.wbs_id));
}

/** Collect all WBS IDs at depth > maxDepth (for auto-collapse). */
export function getWbsIdsBeyondDepth(nodes: WBSNode[], maxDepth: number): Set<string> {
	const ids = new Set<string>();
	function walk(nodes: WBSNode[], depth: number) {
		for (const node of nodes) {
			if (depth >= maxDepth) {
				ids.add(node.wbs_id);
			}
			walk(node.children, depth + 1);
		}
	}
	walk(nodes, 1);
	return ids;
}

/** Default collapse preset for a given tree + activity count.
 *  Auto-collapses parent nodes on large WBS hierarchies (>100 activities) so the initial
 *  render is navigable. A flat (synthetic) grouping tree has no children, so this naturally
 *  yields an all-expanded view there. Shared by initial load AND dimension-switch reset. */
export function computeDefaultCollapse(tree: WBSNode[], totalActivities: number): Set<string> {
	const ids = new Set<string>();
	if (totalActivities <= 100) return ids;
	function walk(nodes: WBSNode[]) {
		for (const n of nodes) {
			if (n.children.length > 0) ids.add(n.wbs_id);
			walk(n.children);
		}
	}
	walk(tree);
	return ids;
}

/** The collapse PRESET for a given view state — the single source of truth for "what should be
 *  collapsed by default" shared by the initial load and the dimension/roll-up reset effect.
 *  Pure (testable) so the effect that calls it stays a thin, deterministic wrapper.
 *  - A non-WBS grouping produces a flat synthetic tree → nothing to collapse.
 *  - WBS + level 0 → the large-schedule auto-collapse default.
 *  - WBS + level N → collapse everything at/below depth N (roll-up-to-level). */
export function presetCollapse(
	dim: GroupDimension,
	depth: number,
	realTree: WBSNode[],
	totalActivities: number,
): Set<string> {
	if (dim !== 'wbs') return new Set<string>();
	return depth === 0
		? computeDefaultCollapse(realTree, totalActivities)
		: getWbsIdsBeyondDepth(realTree, depth);
}

// ── W3: instant client-side regrouping ──────────────────────────────────────
// The viewer always fetches the schedule with the real WBS hierarchy (group_by=wbs)
// and regroups by any other dimension PURELY client-side — no server round-trip. The
// transform mirrors the SHAPE the backend's schedule_view.py::_apply_grouping produces
// (synthetic single-level WBS roots, activities re-parented to a bucket node) so the
// existing buildFlatRows / computeWBSAggregates pipeline renders it unchanged.

const STATUS_BUCKET_ORDER: Record<string, number> = { active: 0, not_started: 1, complete: 2 };
const TASK_TYPE_BUCKET_ORDER: Record<string, number> = { task: 0, milestone: 1, loe: 2 };

interface BucketRef {
	key: string; // stable, i18n-mappable bucket key (NOT a display string)
	order: number; // semantic sort order within the dimension
}

/** Stable bucket key + semantic sort order for one activity under a non-WBS dimension.
 *
 *  status / critical / task_type / calendar read ALREADY-MAPPED ActivityView fields — the
 *  server's P6-code mappers (_status_label / _task_type_label) ran at build time, so the
 *  client never re-implements P6 enum mapping (no second source of truth for those four).
 *
 *  float_bucket is the ONE intentional divergence from the server: the backend bins
 *  total_float_hr_cnt / 8.0 (a fixed 8h/day), while we bin ActivityView.total_float_days,
 *  which the server already converted using the schedule's real calendar day_hr_cnt. Our
 *  value is therefore calendar-aware (more correct on non-8h shift calendars) and will differ
 *  from the server's fixed-8h buckets for those schedules. The boundaries (<0, <=5, <=20)
 *  match the backend. Because the web client no longer uses the server group_by path, the two
 *  surfaces are independent by design. Covered in utils.test.ts. */
function bucketFor(dim: GroupDimension, act: ActivityView): BucketRef {
	switch (dim) {
		case 'status':
			return { key: act.status, order: STATUS_BUCKET_ORDER[act.status] ?? 99 };
		case 'critical':
			return act.is_critical ? { key: 'critical', order: 0 } : { key: 'non_critical', order: 1 };
		case 'task_type':
			return { key: act.task_type, order: TASK_TYPE_BUCKET_ORDER[act.task_type] ?? 99 };
		case 'calendar':
			// Calendar ids are data values, not enums — ordered alphabetically by label later.
			return { key: act.calendar_id || 'default', order: 0 };
		case 'float_bucket': {
			const tf = act.total_float_days;
			if (tf < 0) return { key: 'neg', order: 0 };
			if (tf <= 5) return { key: '0_5', order: 1 };
			if (tf <= 20) return { key: '5_20', order: 2 };
			return { key: 'gt20', order: 3 };
		}
		default:
			return { key: 'all', order: 0 };
	}
}

/** Built-in English display label for a bucket key. The Svelte layer overrides this with an
 *  i18n-aware labeller; this default keeps the transform pure + usable without a translation
 *  context, and is what utils.test.ts asserts against. */
export function defaultGroupLabel(dim: GroupDimension, key: string): string {
	switch (dim) {
		case 'status':
			return { complete: 'Complete', active: 'Active', not_started: 'Not started' }[key] ?? key;
		case 'critical':
			return key === 'critical' ? 'Critical' : 'Non-Critical';
		case 'task_type':
			return { task: 'Task', milestone: 'Milestone', loe: 'LOE' }[key] ?? key;
		case 'float_bucket':
			return (
				{ neg: 'Negative float', '0_5': '0–5 days', '5_20': '5–20 days', gt20: '>20 days' }[key] ??
				key
			);
		case 'calendar':
			return key === 'default' ? 'Default' : key;
		default:
			return key;
	}
}

/** Regroup the schedule by a non-WBS dimension, entirely client-side (W3 flagship).
 *
 *  `dimension === 'wbs'` returns the input object unchanged (identity — the real hierarchy).
 *  Otherwise every activity is re-parented to a synthetic single-level WBS node (one per
 *  bucket). The activity's real `wbs_path` is PRESERVED (only `wbs_id` is reassigned) so the
 *  WBS context remains visible on each row even when the tree is flattened.
 *
 *  Synthetic node ids are deterministic (`_grp_000`, `_grp_001`, …) assigned in the dimension's
 *  semantic bucket order (e.g. float severity Negative → >20), which intentionally differs from
 *  the backend's ASCII-ascending order — acceptable since the surfaces are now independent.
 *  `activity_count` is populated per node so WBSTree's count badge stays correct.
 *
 *  @param getLabel optional (dim, key) → display string; defaults to {@link defaultGroupLabel}.
 */
export function applyClientGrouping(
	data: ScheduleViewData,
	dimension: GroupDimension,
	getLabel: (dim: GroupDimension, key: string) => string = defaultGroupLabel,
): ScheduleViewData {
	if (dimension === 'wbs') return data;

	const buckets = new Map<string, { order: number; label: string; count: number }>();
	const keyByTask = new Map<string, string>();
	for (const act of data.activities) {
		const { key, order } = bucketFor(dimension, act);
		keyByTask.set(act.task_id, key);
		const existing = buckets.get(key);
		if (existing) existing.count++;
		else buckets.set(key, { order, label: getLabel(dimension, key), count: 1 });
	}

	const orderedKeys = [...buckets.entries()]
		.sort((a, b) => a[1].order - b[1].order || a[1].label.localeCompare(b[1].label))
		.map(([key]) => key);

	const idByKey = new Map<string, string>();
	const wbs_tree: WBSNode[] = orderedKeys.map((key, i) => {
		const id = `_grp_${String(i).padStart(3, '0')}`;
		idByKey.set(key, id);
		const b = buckets.get(key)!;
		return {
			wbs_id: id,
			name: b.label,
			short_name: b.label,
			depth: 0,
			parent_id: '',
			activity_count: b.count,
			children: [],
		};
	});

	const activities = data.activities.map((act) => ({
		...act,
		wbs_id: idByKey.get(keyByTask.get(act.task_id)!)!,
	}));

	return { ...data, wbs_tree, activities };
}
