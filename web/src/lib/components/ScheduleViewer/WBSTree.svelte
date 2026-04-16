<script lang="ts">
	import type { WBSAggregate, FlatRow } from './types';
	import { formatDateCompact } from './utils';

	interface Props {
		flatRows: FlatRow[];
		collapsedWbs: Set<string>;
		rowHeight: number;
		scrollTop: number;
		containerHeight: number;
		wbsAggregates: Map<string, WBSAggregate>;
		onToggleWbs: (wbsId: string) => void;
		onHover?: (id: string) => void;
	}

	let {
		flatRows,
		collapsedWbs,
		rowHeight,
		scrollTop,
		containerHeight,
		wbsAggregates,
		onToggleWbs,
		onHover,
	}: Props = $props();

	const BUFFER_ROWS = 20;

	// Virtual scrolling: only render visible rows + buffer
	const virtualStart = $derived(Math.max(0, Math.floor(scrollTop / rowHeight) - BUFFER_ROWS));
	const virtualEnd = $derived(Math.min(flatRows.length, Math.ceil((scrollTop + containerHeight) / rowHeight) + BUFFER_ROWS));
	const renderedRows = $derived(flatRows.slice(virtualStart, virtualEnd));

	const totalHeight = $derived(flatRows.length * rowHeight);

	function floatColor(tf: number): string {
		if (tf < 0) return 'text-red-500 font-bold';
		if (tf === 0) return 'text-amber-500';
		return 'text-gray-500 dark:text-gray-400';
	}

	function progressColor(pct: number): string {
		if (pct >= 100) return 'text-green-600';
		if (pct > 0) return 'text-blue-600';
		return 'text-gray-400';
	}
</script>

<div
	class="wbs-tree overflow-hidden border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900"
	style="width: 550px; min-width: 550px; height: 100%; position: relative;"
>
	<!-- Header -->
	<div class="h-7 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 flex items-center text-[9px] font-semibold text-gray-500 dark:text-gray-400 uppercase">
		<span class="w-[72px] text-center shrink-0 px-1">ID</span>
		<span class="flex-1 min-w-0 px-1">Name</span>
		<span class="w-9 text-center shrink-0">Dur</span>
		<span class="w-[62px] text-center shrink-0">Start</span>
		<span class="w-[62px] text-center shrink-0">Finish</span>
		<span class="w-9 text-center shrink-0">TF</span>
		<span class="w-8 text-center shrink-0 pr-1">%</span>
	</div>

	<!-- Scrollable content (virtual scrolling) -->
	<div class="overflow-hidden" style="height: calc(100% - 28px); position: relative;">
		<!-- Spacer for full scroll height -->
		<div style="height: {totalHeight}px; position: relative; transform: translateY(-{scrollTop}px);">
			{#each renderedRows as row, i}
				{@const absoluteIdx = virtualStart + i}
				{#if row.type === 'wbs' && row.wbsNode}
					{@const agg = wbsAggregates.get(row.wbsNode.wbs_id)}
					{@const isCollapsed = collapsedWbs.has(row.wbsNode.wbs_id)}
					<button
						type="button"
						class="w-full flex items-center cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 border-b border-gray-100 dark:border-gray-800 text-left absolute bg-gray-50/50 dark:bg-gray-800/50"
						style="height: {rowHeight}px; top: {absoluteIdx * rowHeight}px; left: 0; right: 0;"
						onclick={() => onToggleWbs(row.wbsNode!.wbs_id)}
						aria-expanded={!isCollapsed}
						title="{row.wbsPath || row.wbsNode.name}"
					>
						<span class="w-[72px] text-[7px] font-mono text-gray-400 dark:text-gray-500 truncate text-center shrink-0 px-1">{row.wbsNode.short_name || ''}</span>
						<div class="flex items-center gap-1 flex-1 min-w-0 overflow-hidden" style="padding-left: {row.indent * 14 + 4}px;">
							<svg class="w-3 h-3 text-gray-400 shrink-0 transition-transform {isCollapsed ? '-rotate-90' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
							</svg>
							<span class="text-[9px] font-semibold text-gray-700 dark:text-gray-300 truncate">{row.wbsNode.name}</span>
							<span class="text-[7px] text-gray-400 shrink-0 ml-auto">{row.wbsNode.activity_count}</span>
						</div>
						{#if isCollapsed && agg}
							<span class="w-9 text-center text-[8px] font-mono text-gray-500 dark:text-gray-400 shrink-0">{Math.round(agg.total_duration)}d</span>
							<span class="w-[62px] text-center text-[7px] font-mono text-gray-500 dark:text-gray-400 shrink-0">{formatDateCompact(agg.start)}</span>
							<span class="w-[62px] text-center text-[7px] font-mono text-gray-500 dark:text-gray-400 shrink-0">{formatDateCompact(agg.finish)}</span>
							<span class="w-9 text-center text-[8px] font-mono shrink-0 {floatColor(agg.min_float)}">{Math.round(agg.min_float)}d</span>
							<span class="w-8 text-center text-[8px] font-mono shrink-0 pr-1 {progressColor(agg.total_weight > 0 ? agg.weighted_progress / agg.total_weight : 0)}">{agg.total_weight > 0 ? Math.round(agg.weighted_progress / agg.total_weight) : 0}</span>
						{:else}
							<span class="w-9 shrink-0"></span>
							<span class="w-[62px] shrink-0"></span>
							<span class="w-[62px] shrink-0"></span>
							<span class="w-9 shrink-0"></span>
							<span class="w-8 shrink-0"></span>
						{/if}
					</button>
				{:else if row.type === 'activity' && row.activity}
					{@const act = row.activity}
					<div
						class="flex items-center border-b border-gray-50 dark:border-gray-800 hover:bg-blue-50 dark:hover:bg-gray-800 group absolute"
						style="height: {rowHeight}px; top: {absoluteIdx * rowHeight}px; left: 0; right: 0;"
						title="{act.task_code} — {act.task_name}"
						role="button"
						tabindex="0"
						onmouseenter={() => onHover?.(act.task_id)}
						onmouseleave={() => onHover?.('')}
					>
						<span class="w-[72px] text-[7px] font-mono text-blue-500 dark:text-blue-400 truncate text-center shrink-0 px-1">{act.task_code}</span>
						<div class="flex items-center flex-1 min-w-0 overflow-hidden" style="padding-left: {row.indent * 14 + 4}px;">
							{#if act.task_type === 'milestone'}
								<span class="w-2 h-2 rotate-45 bg-amber-500 shrink-0 mr-1.5" title="Milestone"></span>
							{:else if act.task_type === 'loe'}
								<span class="w-2.5 h-1.5 shrink-0 mr-1 border border-dashed border-gray-400 bg-gray-100 dark:bg-gray-700 rounded-sm" title="LOE"></span>
							{:else}
								<span class="w-1.5 h-1.5 rounded-full shrink-0 mr-1.5 {act.is_critical ? 'bg-red-500' : act.status === 'complete' ? 'bg-green-500' : act.status === 'active' ? 'bg-blue-500' : 'bg-gray-300'}" title="{act.status}"></span>
							{/if}
							<span class="text-[9px] text-gray-600 dark:text-gray-400 truncate">{act.task_name || act.task_code}</span>
						</div>
						<span class="w-9 text-center text-[8px] font-mono text-gray-500 dark:text-gray-400 shrink-0">{act.duration_days}d</span>
						<span class="w-[62px] text-center text-[7px] font-mono text-gray-500 dark:text-gray-400 shrink-0">{formatDateCompact(act.early_start)}</span>
						<span class="w-[62px] text-center text-[7px] font-mono text-gray-500 dark:text-gray-400 shrink-0">{formatDateCompact(act.early_finish)}</span>
						<span class="w-9 text-center text-[8px] font-mono shrink-0 {floatColor(act.total_float_days)}">{act.total_float_days}d</span>
						<span class="w-8 text-center text-[8px] font-mono shrink-0 pr-1 {progressColor(act.progress_pct)}">{act.progress_pct > 0 ? act.progress_pct : ''}</span>
					</div>
				{/if}
			{/each}
		</div>
	</div>
</div>
