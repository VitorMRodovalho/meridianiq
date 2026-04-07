<script lang="ts">
	import type { ActivityView, RelationshipView, WBSNode } from './types';
	import { daysBetween, getBarColor, formatDateShort } from './utils';
	import TimeScale from './TimeScale.svelte';

	interface Props {
		activities: ActivityView[];
		wbsTree: WBSNode[];
		relationships?: RelationshipView[];
		collapsedWbs: Set<string>;
		startDate: string;
		endDate: string;
		dataDate: string;
		zoomLevel: 'day' | 'week' | 'month';
		rowHeight: number;
		scrollTop: number;
		containerHeight: number;
		hoveredId: string;
		showFloat?: boolean;
		showBaseline?: boolean;
		onHover: (id: string) => void;
		onClick?: (id: string) => void;
	}

	let {
		activities,
		wbsTree,
		relationships = [],
		collapsedWbs,
		startDate,
		endDate,
		dataDate,
		zoomLevel,
		rowHeight,
		scrollTop,
		containerHeight,
		hoveredId,
		showFloat = true,
		showBaseline = true,
		onHover,
		onClick,
	}: Props = $props();

	const WIDTH = 1200;
	const PAD_LEFT = 0;
	const HEADER_H = 28;
	const BAR_H = 14;
	const BAR_PAD = (rowHeight - BAR_H) / 2;
	const BUFFER_ROWS = 20;

	const totalDays = $derived(Math.max(1, daysBetween(startDate, endDate)));

	function xPos(dateStr: string): number {
		if (!dateStr) return 0;
		return (daysBetween(startDate, dateStr) / totalDays) * WIDTH;
	}

	function barWidth(start: string, end: string): number {
		return Math.max(2, xPos(end) - xPos(start));
	}

	// Build ALL rows matching WBSTree order (not filtered by viewport)
	interface VisRow {
		type: 'wbs' | 'activity';
		activity?: ActivityView;
		wbsNode?: WBSNode;
	}

	const allRows = $derived.by(() => {
		const rows: VisRow[] = [];
		function addNode(node: WBSNode) {
			rows.push({ type: 'wbs', wbsNode: node });
			if (!collapsedWbs.has(node.wbs_id)) {
				for (const act of activities) {
					if (act.wbs_id === node.wbs_id) rows.push({ type: 'activity', activity: act });
				}
				for (const child of node.children) addNode(child);
			}
		}
		for (const root of wbsTree) addNode(root);
		return rows;
	});

	// Virtual scrolling: only render rows in the visible viewport + buffer
	const virtualStart = $derived(Math.max(0, Math.floor(scrollTop / rowHeight) - BUFFER_ROWS));
	const virtualEnd = $derived(Math.min(allRows.length, Math.ceil((scrollTop + containerHeight) / rowHeight) + BUFFER_ROWS));
	const renderedRows = $derived(allRows.slice(virtualStart, virtualEnd));

	const svgHeight = $derived(HEADER_H + allRows.length * rowHeight + 20);

	// WBS summary spans (earliest start → latest finish per WBS node)
	const wbsSpans = $derived.by(() => {
		const spans = new Map<string, { start: string; finish: string; count: number }>();
		for (const act of activities) {
			if (!act.early_start || !act.early_finish) continue;
			const existing = spans.get(act.wbs_id);
			if (!existing) {
				spans.set(act.wbs_id, { start: act.early_start, finish: act.early_finish, count: 1 });
			} else {
				if (act.early_start < existing.start) existing.start = act.early_start;
				if (act.early_finish > existing.finish) existing.finish = act.early_finish;
				existing.count++;
			}
		}
		return spans;
	});

	// Build row index for dependency line routing — uses ABSOLUTE indices from allRows
	const activityRowIndex = $derived.by(() => {
		const idx = new Map<string, number>();
		allRows.forEach((row, i) => {
			if (row.type === 'activity' && row.activity) {
				idx.set(row.activity.task_id, i);
			}
		});
		return idx;
	});

	// Build activity date lookup for dependency endpoints
	const activityDates = $derived.by(() => {
		const m = new Map<string, { start: string; finish: string }>();
		for (const a of activities) {
			m.set(a.task_id, { start: a.early_start, finish: a.early_finish });
		}
		return m;
	});
</script>

<svg
	viewBox="0 0 {WIDTH} {svgHeight}"
	class="w-full"
	style="min-width: 600px;"
>
	<!-- Time scale header -->
	<TimeScale
		{startDate}
		{endDate}
		{zoomLevel}
		width={WIDTH}
		padLeft={PAD_LEFT}
		{dataDate}
	/>

	<!-- Grid lines (every tick) -->
	{#each Array(Math.min(totalDays + 1, 100)) as _, d}
		{@const x = (d / totalDays) * WIDTH}
		{#if d % (zoomLevel === 'day' ? 1 : zoomLevel === 'week' ? 7 : 30) === 0}
			<line x1={x} y1={HEADER_H} x2={x} y2={svgHeight} stroke="#f3f4f6" stroke-width="0.5" class="dark:stroke-gray-800" />
		{/if}
	{/each}

	<!-- SVG pattern for LOE activities -->
	<defs>
		<pattern id="loe-pattern" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
			<line x1="0" y1="0" x2="0" y2="6" stroke="#9ca3af" stroke-width="1.5" opacity="0.4" />
		</pattern>
	</defs>

	<!-- Activity bars (virtual scrolling: only render visible rows + buffer) -->
	{#each renderedRows as row, i}
		{@const absoluteIdx = virtualStart + i}
		{@const y = HEADER_H + absoluteIdx * rowHeight}

		{#if row.type === 'wbs' && row.wbsNode}
			<!-- WBS summary row background -->
			<rect x="0" {y} width={WIDTH} height={rowHeight} fill="#f9fafb" opacity="0.5" class="dark:fill-gray-800" />
			<!-- WBS summary bar (span of all child activities) -->
			{@const span = wbsSpans.get(row.wbsNode.wbs_id)}
			{#if span}
				{@const sx = xPos(span.start)}
				{@const sw = Math.max(4, xPos(span.finish) - sx)}
				<g>
					<title>{row.wbsNode.name} — {span.count} activities | {span.start} → {span.finish}</title>
					<rect
						x={sx} y={y + rowHeight / 2 - 2}
						width={sw} height={4}
						rx="2" fill="#6b7280" opacity="0.3"
					/>
				</g>
				<polygon points="{sx},{y + rowHeight / 2 - 4} {sx},{y + rowHeight / 2 + 4} {sx - 3},{y + rowHeight / 2}" fill="#6b7280" opacity="0.4" />
				<polygon points="{sx + sw},{y + rowHeight / 2 - 4} {sx + sw},{y + rowHeight / 2 + 4} {sx + sw + 3},{y + rowHeight / 2}" fill="#6b7280" opacity="0.4" />
			{/if}
		{:else if row.type === 'activity' && row.activity}
			{@const act = row.activity}
			{@const x = xPos(act.early_start)}
			{@const w = barWidth(act.early_start, act.early_finish)}
			{@const color = getBarColor(act.status, act.is_critical)}
			{@const isHovered = hoveredId === act.task_id}

			<!-- Hover highlight -->
			{#if isHovered}
				<rect x="0" {y} width={WIDTH} height={rowHeight} fill="#eff6ff" opacity="0.5" class="dark:fill-blue-950" />
			{/if}

			<!-- Row border -->
			<line x1="0" y1={y + rowHeight} x2={WIDTH} y2={y + rowHeight} stroke="#f3f4f6" stroke-width="0.5" class="dark:stroke-gray-800" />

			{#if act.task_type === 'milestone'}
				<!-- Milestone diamond -->
				<g
					role="button"
					tabindex="0"
					aria-label="{act.task_name} (milestone)"
					transform="translate({x}, {y + rowHeight / 2})"
					onmouseenter={() => onHover(act.task_id)}
					onmouseleave={() => onHover('')}
					onclick={() => onClick?.(act.task_id)}
					class="cursor-pointer"
				>
					<polygon points="0,-6 6,0 0,6 -6,0" fill={color} stroke="white" stroke-width="1" />
				</g>
			{:else}
				<!-- Activity bar group -->
				<g
					role="button"
					tabindex="0"
					aria-label="{act.task_name}"
					onmouseenter={() => onHover(act.task_id)}
					onmouseleave={() => onHover('')}
					onclick={() => onClick?.(act.task_id)}
					class="cursor-pointer"
				>
					<!-- Background bar (full duration) -->
					{#if act.task_type === 'loe'}
						<!-- LOE: hatched pattern -->
						<rect x={x} y={y + BAR_PAD} width={w} height={BAR_H} rx="2" fill="url(#loe-pattern)" />
						<rect x={x} y={y + BAR_PAD} width={w} height={BAR_H} rx="2" fill="none" stroke="#9ca3af" stroke-width="0.5" stroke-dasharray="4 2" />
					{:else}
						<rect
							x={x} y={y + BAR_PAD}
							width={w} height={BAR_H}
							rx="2" fill={color} opacity="0.2"
						/>
					{/if}

					<!-- Progress fill -->
					{#if act.progress_pct > 0}
						<rect
							x={x} y={y + BAR_PAD}
							width={w * Math.min(act.progress_pct / 100, 1)} height={BAR_H}
							rx="2" fill={color} opacity="0.85"
						/>
					{:else if act.status !== 'not_started'}
						<rect
							x={x} y={y + BAR_PAD}
							width={w} height={BAR_H}
							rx="2" fill={color} opacity="0.6"
						/>
					{/if}

					<!-- Actual completion bar (solid green for complete activities) -->
					{#if act.actual_start && act.actual_finish && act.status === 'complete'}
						{@const acx = xPos(act.actual_start)}
						{@const acw = Math.max(2, xPos(act.actual_finish) - acx)}
						<rect
							x={acx} y={y + BAR_PAD + BAR_H - 3}
							width={acw} height={3}
							rx="1" fill="#10b981" opacity="0.9"
						/>
					{/if}

					<!-- Actual progress bar (green, shows actual_start → proportional progress) -->
					{#if act.actual_start && act.status === 'active' && act.progress_pct > 0}
						{@const ax = xPos(act.actual_start)}
						{@const plannedW = Math.max(2, xPos(act.early_finish) - xPos(act.early_start))}
						{@const actualW = Math.max(2, plannedW * (act.progress_pct / 100))}
						<rect
							x={ax} y={y + BAR_PAD + BAR_H - 3}
							width={actualW} height={3}
							rx="1" fill="#10b981" opacity="0.7"
						/>
					{/if}

					<!-- Native SVG tooltip -->
					<title>{act.task_code} — {act.task_name}
Duration: {act.duration_days}d | Remaining: {act.remaining_days}d | TF: {act.total_float_days}d | FF: {act.free_float_days}d | Progress: {act.progress_pct}%
ES: {act.early_start} → EF: {act.early_finish}{act.actual_start ? ` | AS: ${act.actual_start}` : ''}{act.actual_finish ? ` | AF: ${act.actual_finish}` : ''}{act.is_critical ? ' | CRITICAL' : ''}</title>

					<!-- Bar border -->
					<rect
						x={x} y={y + BAR_PAD}
						width={w} height={BAR_H}
						rx="2" fill="none" stroke={color} stroke-width="0.5" opacity="0.5"
					/>

					<!-- Constraint indicator -->
					{#if act.constraint_type && act.constraint_type !== '' && act.constraint_type !== 'CS_MEO'}
						<rect x={x - 1} y={y + BAR_PAD - 1} width={8} height={8} rx="2" fill="#7c3aed" opacity="0.8" />
						<text x={x + 3} y={y + BAR_PAD + 5} text-anchor="middle" class="text-[5px] fill-white font-bold select-none">C</text>
					{/if}

					<!-- Duration label (if bar wide enough) -->
					{#if w > 30}
						<text
							x={x + w / 2} y={y + BAR_PAD + BAR_H / 2 + 3}
							text-anchor="middle"
							class="text-[7px] fill-white font-medium select-none"
							style="paint-order: stroke; stroke: {color}; stroke-width: 2px;"
						>
							{act.duration_days > 0 ? `${act.duration_days}d` : ''}
						</text>
					{/if}

					<!-- Baseline bar (thin, below main bar) -->
					{#if showBaseline && act.baseline_start && act.baseline_finish}
						{@const bx = xPos(act.baseline_start)}
						{@const bw = Math.max(2, xPos(act.baseline_finish) - bx)}
						<rect
							x={bx} y={y + BAR_PAD + BAR_H + 1}
							width={bw} height={3}
							rx="1" fill="#9ca3af" opacity="0.4"
							stroke="#9ca3af" stroke-width="0.5" stroke-dasharray="3 2"
						/>
						<!-- Sliding right arrow if current finish > baseline finish -->
						{#if act.early_finish > act.baseline_finish}
							<polygon
								points="{x + w + 2},{y + BAR_PAD + BAR_H / 2 - 3} {x + w + 7},{y + BAR_PAD + BAR_H / 2} {x + w + 2},{y + BAR_PAD + BAR_H / 2 + 3}"
								fill="#f59e0b" opacity="0.8"
							/>
						{/if}
					{/if}

					<!-- Float bar (early finish → late finish) -->
					{#if showFloat && act.total_float_days > 0 && act.late_finish && act.early_finish}
						{@const fx = xPos(act.early_finish)}
						{@const fw = Math.max(1, xPos(act.late_finish) - fx)}
						<rect
							x={fx} y={y + BAR_PAD + 5}
							width={fw} height={4}
							rx="1" fill="#f59e0b" opacity="0.4"
						/>
					{/if}

					<!-- Negative float border -->
					{#if act.total_float_days < 0}
						<rect
							x={x - 2} y={y + BAR_PAD - 1}
							width={w + 4} height={BAR_H + 2}
							rx="3" fill="none" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="3 2" opacity="0.6"
						/>
					{/if}

					<!-- Alert indicators -->
					{#if act.alerts.length > 0}
						<circle
							cx={x + w + 5} cy={y + rowHeight / 2}
							r="3" fill="#ef4444"
						/>
					{/if}
				</g>
			{/if}
		{/if}
	{/each}

	<!-- Dependency lines (only render if at least one endpoint is near viewport) -->
	{#if relationships.length > 0}
		{#each relationships as rel}
			{@const fromRow = activityRowIndex.get(rel.from_id)}
			{@const toRow = activityRowIndex.get(rel.to_id)}
			{@const fromDates = activityDates.get(rel.from_id)}
			{@const toDates = activityDates.get(rel.to_id)}
			{#if fromRow !== undefined && toRow !== undefined && fromDates && toDates && (
				(fromRow >= virtualStart - BUFFER_ROWS && fromRow <= virtualEnd + BUFFER_ROWS) ||
				(toRow >= virtualStart - BUFFER_ROWS && toRow <= virtualEnd + BUFFER_ROWS)
			)}
				{@const fromY = HEADER_H + fromRow * rowHeight + rowHeight / 2}
				{@const toY = HEADER_H + toRow * rowHeight + rowHeight / 2}
				{@const fromX = rel.type === 'FS' || rel.type === 'FF' ? xPos(fromDates.finish) : xPos(fromDates.start)}
				{@const toX = rel.type === 'FS' || rel.type === 'SS' ? xPos(toDates.start) : xPos(toDates.finish)}
				{@const midX = fromX + (toX - fromX) * 0.5}
				{@const isHighlighted = hoveredId === rel.from_id || hoveredId === rel.to_id}
				<path
					d="M{fromX},{fromY} C{midX},{fromY} {midX},{toY} {toX},{toY}"
					fill="none"
					stroke={isHighlighted ? '#3b82f6' : '#94a3b8'}
					stroke-width={isHighlighted ? 2 : 1}
					opacity={isHighlighted ? 0.9 : 0.5}
					class={isHighlighted ? '' : 'dark:stroke-gray-500'}
				/>
				<!-- Arrow head -->
				<polygon
					points="{toX},{toY} {toX - 4},{toY - 2.5} {toX - 4},{toY + 2.5}"
					fill={isHighlighted ? '#3b82f6' : '#94a3b8'}
					opacity={isHighlighted ? 0.9 : 0.6}
					class="dark:fill-gray-500"
				/>
			{/if}
		{/each}
	{/if}
</svg>
