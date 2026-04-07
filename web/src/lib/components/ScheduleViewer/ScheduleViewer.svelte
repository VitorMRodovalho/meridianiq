<script lang="ts">
	import type { ScheduleViewData } from './types';
	import WBSTree from './WBSTree.svelte';
	import GanttCanvas from './GanttCanvas.svelte';
	import { formatDateShort } from './utils';

	interface Props {
		data: ScheduleViewData;
		showFloat?: boolean;
		showBaseline?: boolean;
	}

	let { data, showFloat = true, showBaseline = true }: Props = $props();

	const ROW_HEIGHT = 24;

	// State
	let collapsedWbs = $state<Set<string>>(new Set());
	let zoomLevel = $state<'day' | 'week' | 'month'>('week');
	let scrollTop = $state(0);
	let hoveredId = $state('');
	let scrollContainer: HTMLDivElement | null = $state(null);

	function toggleWbs(wbsId: string) {
		const next = new Set(collapsedWbs);
		if (next.has(wbsId)) {
			next.delete(wbsId);
		} else {
			next.add(wbsId);
		}
		collapsedWbs = next;
	}

	function expandAll() {
		collapsedWbs = new Set();
	}

	function collapseAll() {
		const all = new Set<string>();
		function collect(nodes: typeof data.wbs_tree) {
			for (const n of nodes) {
				all.add(n.wbs_id);
				collect(n.children);
			}
		}
		collect(data.wbs_tree);
		collapsedWbs = all;
	}

	function handleScroll(e: Event) {
		const target = e.target as HTMLDivElement;
		scrollTop = target.scrollTop;
	}

	function handleHover(id: string) {
		hoveredId = id;
	}

	// Tooltip data
	const hoveredActivity = $derived(
		hoveredId ? data.activities.find(a => a.task_id === hoveredId) : null
	);
</script>

<div class="schedule-viewer bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
	<!-- Toolbar -->
	<div class="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
		<div class="flex items-center gap-3">
			<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{data.project_name || 'Schedule'}</h3>
			<span class="text-[10px] text-gray-500 dark:text-gray-400">
				{data.summary.total_activities} activities | {data.summary.critical_count} critical | {data.summary.complete_pct.toFixed(0)}% complete
			</span>
		</div>
		<div class="flex items-center gap-2">
			<!-- Zoom controls -->
			{#each ['day', 'week', 'month'] as level}
				<button
					onclick={() => zoomLevel = level as 'day' | 'week' | 'month'}
					class="px-2 py-0.5 text-[10px] rounded {zoomLevel === level ? 'bg-blue-600 text-white' : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}"
				>
					{level.charAt(0).toUpperCase() + level.slice(1)}
				</button>
			{/each}
			<span class="w-px h-4 bg-gray-300 dark:bg-gray-600"></span>
			<!-- Expand/Collapse -->
			<button onclick={expandAll} class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" title="Expand All">
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
				</svg>
			</button>
			<button onclick={collapseAll} class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" title="Collapse All">
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9V4.5M9 9H4.5M9 9L3.5 3.5M9 15v4.5M9 15H4.5M9 15l-5.5 5.5M15 9h4.5M15 9V4.5M15 9l5.5-5.5M15 15h4.5M15 15v4.5m0-4.5l5.5 5.5" />
				</svg>
			</button>
		</div>
	</div>

	<!-- Main content: WBS Tree (left) + Gantt (right) -->
	<div class="flex" style="height: 500px;">
		<!-- WBS Tree -->
		<WBSTree
			activities={data.activities}
			wbsTree={data.wbs_tree}
			{collapsedWbs}
			rowHeight={ROW_HEIGHT}
			{scrollTop}
			onToggleWbs={toggleWbs}
		/>

		<!-- Gantt Canvas (scrollable) -->
		<div
			bind:this={scrollContainer}
			onscroll={handleScroll}
			class="flex-1 overflow-auto"
		>
			<GanttCanvas
				activities={data.activities}
				wbsTree={data.wbs_tree}
				{collapsedWbs}
				startDate={data.project_start}
				endDate={data.project_finish}
				dataDate={data.data_date}
				{zoomLevel}
				rowHeight={ROW_HEIGHT}
				{scrollTop}
				{hoveredId}
				{showFloat}
				{showBaseline}
				onHover={handleHover}
			/>
		</div>
	</div>

	<!-- Tooltip -->
	{#if hoveredActivity}
		<div class="border-t border-gray-200 dark:border-gray-700 px-3 py-2 bg-gray-50 dark:bg-gray-800 flex items-center gap-4 text-[10px]">
			<span class="font-semibold text-gray-900 dark:text-gray-100">{hoveredActivity.task_code}</span>
			<span class="text-gray-600 dark:text-gray-400 truncate max-w-xs">{hoveredActivity.task_name}</span>
			<span class="text-gray-500">{formatDateShort(hoveredActivity.early_start)} — {formatDateShort(hoveredActivity.early_finish)}</span>
			<span class="text-gray-500">{hoveredActivity.duration_days}d</span>
			<span class="{hoveredActivity.total_float_days < 0 ? 'text-red-600 font-bold' : hoveredActivity.total_float_days === 0 ? 'text-amber-600' : 'text-green-600'}">
				TF: {hoveredActivity.total_float_days}d
			</span>
			<span class="{hoveredActivity.is_critical ? 'text-red-600 font-bold' : 'text-gray-400'}">
				{hoveredActivity.is_critical ? 'CRITICAL' : ''}
			</span>
			{#if hoveredActivity.progress_pct > 0}
				<span class="text-blue-600">{hoveredActivity.progress_pct}%</span>
			{/if}
			{#if hoveredActivity.baseline_start && hoveredActivity.baseline_finish}
				<span class="text-gray-400">BL: {formatDateShort(hoveredActivity.baseline_start)}—{formatDateShort(hoveredActivity.baseline_finish)}</span>
				{#if hoveredActivity.early_finish > hoveredActivity.baseline_finish}
					<span class="text-amber-600 font-bold">SLIDING RIGHT</span>
				{/if}
			{/if}
			{#each hoveredActivity.alerts as alert}
				<span class="px-1 py-0.5 bg-red-100 text-red-700 rounded text-[8px] font-bold">{alert.replace('_', ' ')}</span>
			{/each}
		</div>
	{/if}

	<!-- Legend -->
	<div class="border-t border-gray-200 dark:border-gray-700 px-3 py-1.5 flex items-center gap-3 text-[9px] text-gray-500 dark:text-gray-400">
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm bg-red-500"></span> Critical</span>
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm bg-blue-500"></span> Active</span>
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm bg-green-500"></span> Complete</span>
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm bg-gray-400"></span> Not Started</span>
		<span class="flex items-center gap-1"><span class="w-2 h-2 rotate-45 bg-amber-500"></span> Milestone</span>
		{#if showBaseline}
			<span class="flex items-center gap-1"><span class="w-3 h-1.5 rounded-sm bg-gray-400 opacity-50 border border-dashed border-gray-500"></span> Baseline</span>
		{/if}
		{#if showFloat}
			<span class="flex items-center gap-1"><span class="w-3 h-1 rounded-sm bg-amber-400 opacity-60"></span> Float</span>
		{/if}
		{#if data.data_date}
			<span class="ml-auto text-amber-600">Data Date: {formatDateShort(data.data_date)}</span>
		{/if}
	</div>
</div>
