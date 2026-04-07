<script lang="ts">
	import type { ActivityView, WBSNode } from './types';

	interface Props {
		activities: ActivityView[];
		wbsTree: WBSNode[];
		collapsedWbs: Set<string>;
		rowHeight: number;
		scrollTop: number;
		containerHeight: number;
		onToggleWbs: (wbsId: string) => void;
	}

	let {
		activities,
		wbsTree,
		collapsedWbs,
		rowHeight,
		scrollTop,
		containerHeight,
		onToggleWbs,
	}: Props = $props();

	const BUFFER_ROWS = 20;

	// Build ALL rows: WBS headers interleaved with activities
	interface RowItem {
		type: 'wbs' | 'activity';
		wbsNode?: WBSNode;
		activity?: ActivityView;
		indent: number;
		wbsPath?: string;
	}

	const allRows = $derived.by(() => {
		const rows: RowItem[] = [];

		function addWbsNode(node: WBSNode, indent: number, parentPath: string) {
			const path = parentPath ? `${parentPath} / ${node.name}` : node.name;
			rows.push({ type: 'wbs', wbsNode: node, indent, wbsPath: path });
			if (!collapsedWbs.has(node.wbs_id)) {
				for (const act of activities) {
					if (act.wbs_id === node.wbs_id) {
						rows.push({ type: 'activity', activity: act, indent: indent + 1 });
					}
				}
				for (const child of node.children) {
					addWbsNode(child, indent + 1, path);
				}
			}
		}

		for (const root of wbsTree) {
			addWbsNode(root, 0, '');
		}
		return rows;
	});

	// Virtual scrolling: only render visible rows + buffer
	const virtualStart = $derived(Math.max(0, Math.floor(scrollTop / rowHeight) - BUFFER_ROWS));
	const virtualEnd = $derived(Math.min(allRows.length, Math.ceil((scrollTop + containerHeight) / rowHeight) + BUFFER_ROWS));
	const renderedRows = $derived(allRows.slice(virtualStart, virtualEnd));

	const totalHeight = $derived(allRows.length * rowHeight);
</script>

<div
	class="wbs-tree overflow-hidden border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900"
	style="width: 260px; height: 100%; position: relative;"
>
	<!-- Header -->
	<div class="h-7 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 flex items-center px-2">
		<span class="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase">WBS / Activity</span>
	</div>

	<!-- Scrollable content (virtual scrolling) -->
	<div class="overflow-hidden" style="height: calc(100% - 28px); position: relative;">
		<!-- Spacer for full scroll height -->
		<div style="height: {totalHeight}px; position: relative; transform: translateY(-{scrollTop}px);">
			{#each renderedRows as row, i}
				{@const absoluteIdx = virtualStart + i}
				{#if row.type === 'wbs' && row.wbsNode}
					<button
						type="button"
						class="w-full flex items-center gap-1 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 border-b border-gray-100 dark:border-gray-800 text-left absolute"
						style="height: {rowHeight}px; padding-left: {row.indent * 16 + 4}px; top: {absoluteIdx * rowHeight}px; left: 0; right: 0;"
						onclick={() => onToggleWbs(row.wbsNode!.wbs_id)}
						aria-expanded={!collapsedWbs.has(row.wbsNode.wbs_id)}
						title="{row.wbsPath || row.wbsNode.name}"
					>
						<svg class="w-3 h-3 text-gray-400 shrink-0 transition-transform {collapsedWbs.has(row.wbsNode.wbs_id) ? '-rotate-90' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
						</svg>
						{#if row.wbsNode.short_name && row.wbsNode.short_name !== row.wbsNode.name && !/^\d+$/.test(row.wbsNode.short_name)}
							<span class="text-[8px] text-gray-400 shrink-0 font-mono">{row.wbsNode.short_name}</span>
						{/if}
						<span class="text-[10px] font-semibold text-gray-700 dark:text-gray-300 truncate">{row.wbsNode.name}</span>
						<span class="text-[8px] text-gray-400 ml-auto shrink-0">{row.wbsNode.activity_count}</span>
					</button>
				{:else if row.type === 'activity' && row.activity}
					{@const act = row.activity}
					<div
						class="flex items-center border-b border-gray-50 dark:border-gray-800 hover:bg-blue-50 dark:hover:bg-gray-800 group absolute"
						style="height: {rowHeight}px; padding-left: {row.indent * 16 + 4}px; top: {absoluteIdx * rowHeight}px; left: 0; right: 0;"
						title="{act.task_code} — {act.task_name} | TF: {act.total_float_days}d | {act.progress_pct}%"
					>
						{#if act.task_type === 'milestone'}
							<span class="w-2 h-2 rotate-45 bg-amber-500 shrink-0 mr-1.5" title="Milestone"></span>
						{:else if act.task_type === 'loe'}
							<span class="w-2.5 h-1.5 shrink-0 mr-1 border border-dashed border-gray-400 bg-gray-100 dark:bg-gray-700 rounded-sm" title="LOE"></span>
						{:else}
							<span class="w-1.5 h-1.5 rounded-full shrink-0 mr-1.5 {act.is_critical ? 'bg-red-500' : act.status === 'complete' ? 'bg-green-500' : act.status === 'active' ? 'bg-blue-500' : 'bg-gray-300'}" title="{act.status}"></span>
						{/if}
						<span class="text-[9px] text-gray-600 dark:text-gray-400 truncate flex-1">{act.task_name || act.task_code}</span>
						<span class="shrink-0 ml-1 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
							{#if act.progress_pct > 0 && act.progress_pct < 100}
								<span class="w-6 h-1 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden"><span class="block h-full rounded-full bg-blue-500" style="width:{act.progress_pct}%"></span></span>
							{/if}
							<span class="text-[7px] font-mono {act.total_float_days < 0 ? 'text-red-500 font-bold' : act.total_float_days === 0 ? 'text-amber-500' : 'text-gray-400'}">{act.total_float_days}d</span>
						</span>
					</div>
				{/if}
			{/each}
		</div>
	</div>
</div>
