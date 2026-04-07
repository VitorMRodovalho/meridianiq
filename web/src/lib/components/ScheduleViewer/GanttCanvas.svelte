<script lang="ts">
	import type { ActivityView, WBSNode } from './types';
	import { daysBetween, getBarColor, formatDateShort } from './utils';
	import TimeScale from './TimeScale.svelte';

	interface Props {
		activities: ActivityView[];
		wbsTree: WBSNode[];
		collapsedWbs: Set<string>;
		startDate: string;
		endDate: string;
		dataDate: string;
		zoomLevel: 'day' | 'week' | 'month';
		rowHeight: number;
		scrollTop: number;
		hoveredId: string;
		onHover: (id: string) => void;
	}

	let {
		activities,
		wbsTree,
		collapsedWbs,
		startDate,
		endDate,
		dataDate,
		zoomLevel,
		rowHeight,
		scrollTop,
		hoveredId,
		onHover,
	}: Props = $props();

	const WIDTH = 1200;
	const PAD_LEFT = 0;
	const HEADER_H = 28;
	const BAR_H = 14;
	const BAR_PAD = (rowHeight - BAR_H) / 2;

	const totalDays = $derived(Math.max(1, daysBetween(startDate, endDate)));

	function xPos(dateStr: string): number {
		if (!dateStr) return 0;
		return (daysBetween(startDate, dateStr) / totalDays) * WIDTH;
	}

	function barWidth(start: string, end: string): number {
		return Math.max(2, xPos(end) - xPos(start));
	}

	// Build visible rows matching WBSTree order
	interface VisRow {
		type: 'wbs' | 'activity';
		activity?: ActivityView;
		wbsNode?: WBSNode;
	}

	const visibleRows = $derived.by(() => {
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

	const svgHeight = $derived(HEADER_H + visibleRows.length * rowHeight + 20);
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

	<!-- Activity bars -->
	{#each visibleRows as row, i}
		{@const y = HEADER_H + i * rowHeight}

		{#if row.type === 'wbs' && row.wbsNode}
			<!-- WBS summary row background -->
			<rect x="0" {y} width={WIDTH} height={rowHeight} fill="#f9fafb" opacity="0.5" class="dark:fill-gray-800" />
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
					transform="translate({x}, {y + rowHeight / 2})"
					onmouseenter={() => onHover(act.task_id)}
					onmouseleave={() => onHover('')}
					class="cursor-pointer"
				>
					<polygon points="0,-6 6,0 0,6 -6,0" fill={color} stroke="white" stroke-width="1" />
				</g>
			{:else}
				<!-- Activity bar group -->
				<g
					onmouseenter={() => onHover(act.task_id)}
					onmouseleave={() => onHover('')}
					class="cursor-pointer"
				>
					<!-- Background bar (full duration) -->
					<rect
						x={x} y={y + BAR_PAD}
						width={w} height={BAR_H}
						rx="2" fill={color} opacity="0.2"
					/>

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

					<!-- Bar border -->
					<rect
						x={x} y={y + BAR_PAD}
						width={w} height={BAR_H}
						rx="2" fill="none" stroke={color} stroke-width="0.5" opacity="0.5"
					/>

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
</svg>
