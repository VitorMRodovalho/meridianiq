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

import type { ActivityView, WBSNode, WBSAggregate, FlatRow } from './types';

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
