<script lang="ts">
	import type { ScheduleViewData } from './types';
	import WBSTree from './WBSTree.svelte';
	import GanttCanvas from './GanttCanvas.svelte';
	import ActivityTooltip from './ActivityTooltip.svelte';
	import { onMount } from 'svelte';
	import { daysBetween, formatDateShort, computeWBSAggregates, buildFlatRows, getMaxWBSDepth, getWbsIdsBeyondDepth } from './utils';

	interface Props {
		data: ScheduleViewData;
		showFloat?: boolean;
		showBaseline?: boolean;
		showDependencies?: boolean;
		criticalOnly?: boolean;
		onActivityClick?: (taskId: string) => void;
	}

	let {
		data,
		showFloat = true,
		showBaseline = true,
		showDependencies = false,
		criticalOnly = false,
		onActivityClick,
	}: Props = $props();

	// Filter activities if criticalOnly
	const filteredData = $derived.by(() => {
		if (!criticalOnly) return data;
		return {
			...data,
			activities: data.activities.filter(a => a.is_critical || a.status === 'complete'),
			relationships: data.relationships.filter(r => {
				const critIds = new Set(data.activities.filter(a => a.is_critical).map(a => a.task_id));
				return critIds.has(r.from_id) && critIds.has(r.to_id);
			}),
		};
	});

	const ROW_HEIGHT = 24;
	let viewerHeight = $state(500);

	// Smart defaults based on data
	function initDefaults() {
		// Auto-collapse if >100 activities
		if (data.summary.total_activities > 100) {
			const all = new Set<string>();
			function collectWbs(nodes: typeof data.wbs_tree) {
				for (const n of nodes) {
					if (n.children.length > 0) all.add(n.wbs_id);
					collectWbs(n.children);
				}
			}
			collectWbs(data.wbs_tree);
			collapsedWbs = all;
		}
		// Auto-zoom based on project duration
		if (data.project_start && data.project_finish) {
			const days = daysBetween(data.project_start, data.project_finish);
			if (days > 365) zoomLevel = 'month';
			else if (days > 60) zoomLevel = 'week';
			else zoomLevel = 'day';
		}
	}

	$effect(() => { initDefaults(); });

	// State
	let collapsedWbs = $state<Set<string>>(new Set());
	let zoomLevel = $state<'day' | 'week' | 'month'>('week');
	let scrollTop = $state(0);
	let hoveredId = $state('');
	let searchQuery = $state('');
	let scrollContainer: HTMLDivElement | null = $state(null);
	let mouseX = $state(0);
	let mouseY = $state(0);

	// Search filter
	const searchFilteredData = $derived.by(() => {
		const base = filteredData;
		if (!searchQuery.trim()) return base;
		const q = searchQuery.toLowerCase();
		const matchedActivities = base.activities.filter(
			a => a.task_name.toLowerCase().includes(q) ||
				a.task_code.toLowerCase().includes(q) ||
				a.task_id.toLowerCase().includes(q)
		);
		return { ...base, activities: matchedActivities };
	});

	// WBS aggregates (computed once, shared by WBSTree and GanttCanvas)
	const wbsAggregates = $derived(computeWBSAggregates(searchFilteredData.activities, searchFilteredData.wbs_tree));

	// WBS depth filter (0 = all levels) — sets collapsedWbs directly as a preset
	let wbsDepthFilter = $state(0);
	const maxWbsDepth = $derived(getMaxWBSDepth(data.wbs_tree));

	// When depth filter changes, SET collapsedWbs directly. User can then manually toggle on top.
	let prevDepthFilter = $state(0);
	$effect(() => {
		if (wbsDepthFilter !== prevDepthFilter) {
			prevDepthFilter = wbsDepthFilter;
			if (wbsDepthFilter === 0) {
				collapsedWbs = new Set();
			} else {
				collapsedWbs = getWbsIdsBeyondDepth(data.wbs_tree, wbsDepthFilter);
			}
		}
	});

	// Single source of truth: flat row list shared by WBSTree and GanttCanvas
	const isFiltered = $derived(criticalOnly || searchQuery.trim() !== '');
	const flatRows = $derived(buildFlatRows(
		searchFilteredData.wbs_tree,
		searchFilteredData.activities,
		collapsedWbs,
		isFiltered,
	));

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

	// Track actual content area height for virtual scrolling
	let containerHeight = $state(500);

	function handleScroll(e: Event) {
		const target = e.target as HTMLDivElement;
		scrollTop = target.scrollTop;
		containerHeight = target.clientHeight;
	}

	function handleHover(id: string) {
		hoveredId = id;
	}

	// Drag-to-pan on Gantt canvas
	let isDragging = $state(false);
	let dragStartX = $state(0);
	let dragStartY = $state(0);
	let dragScrollLeft = $state(0);
	let dragScrollTop = $state(0);

	function handleMouseDown(e: MouseEvent) {
		if (!scrollContainer || e.button !== 0) return;
		isDragging = true;
		dragStartX = e.clientX;
		dragStartY = e.clientY;
		dragScrollLeft = scrollContainer.scrollLeft;
		dragScrollTop = scrollContainer.scrollTop;
		scrollContainer.style.cursor = 'grabbing';
		e.preventDefault();
	}

	function handleMouseMove(e: MouseEvent) {
		if (!isDragging || !scrollContainer) return;
		scrollContainer.scrollLeft = dragScrollLeft - (e.clientX - dragStartX);
		scrollContainer.scrollTop = dragScrollTop - (e.clientY - dragStartY);
	}

	function handleMouseUp() {
		if (!scrollContainer) return;
		isDragging = false;
		scrollContainer.style.cursor = 'grab';
	}

	// Keyboard shortcuts
	onMount(() => {
		function handleKey(e: KeyboardEvent) {
			if (e.key === '+' || e.key === '=') {
				if (zoomLevel === 'month') zoomLevel = 'week';
				else if (zoomLevel === 'week') zoomLevel = 'day';
			} else if (e.key === '-') {
				if (zoomLevel === 'day') zoomLevel = 'week';
				else if (zoomLevel === 'week') zoomLevel = 'month';
			} else if (e.key === 'e') {
				expandAll();
			} else if (e.key === 'c' && !e.ctrlKey && !e.metaKey) {
				collapseAll();
			}
		}
		document.addEventListener('keydown', handleKey);
		return () => document.removeEventListener('keydown', handleKey);
	});

	// Serialize the Gantt SVG with inlined CSS so it renders
	// correctly when opened outside the app (no Tailwind present).
	function buildSerializedSvg(): { xml: string; width: number; height: number } | null {
		if (!scrollContainer) return null;
		const svg = scrollContainer.querySelector('svg');
		if (!svg) return null;

		const svgClone = svg.cloneNode(true) as SVGSVGElement;
		// Ensure xmlns attrs so the file is a valid standalone SVG
		svgClone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
		svgClone.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');

		const width = Number(svgClone.getAttribute('width')) || svg.clientWidth || 1200;
		const height = Number(svgClone.getAttribute('height')) || svg.clientHeight || 600;
		svgClone.setAttribute('width', String(width));
		svgClone.setAttribute('height', String(height));
		// viewBox lets consumers scale without loss
		svgClone.setAttribute('viewBox', `0 0 ${width} ${height}`);

		// Inline a minimal style block — mirrors the Tailwind utilities
		// actually used by the Gantt so the exported file is readable
		// in Illustrator / browser preview without the app's CSS.
		const style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
		style.textContent = `
			text { font-family: system-ui, -apple-system, sans-serif; }
			.fill-white { fill: #ffffff; }
			.dark\\:fill-gray-500 { fill: #6b7280; }
		`;
		svgClone.insertBefore(style, svgClone.firstChild);

		return {
			xml: new XMLSerializer().serializeToString(svgClone),
			width,
			height,
		};
	}

	function downloadBlob(blob: Blob, filename: string): void {
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = filename;
		document.body.appendChild(a);
		a.click();
		a.remove();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}

	// SVG export — downloads the Gantt as a standalone .svg file
	function exportSvg() {
		const serialized = buildSerializedSvg();
		if (!serialized) return;
		const projectName = (data.project_name || 'schedule').replace(/[^a-z0-9_-]+/gi, '-');
		const blob = new Blob([`<?xml version="1.0" encoding="UTF-8"?>\n${serialized.xml}`], {
			type: 'image/svg+xml;charset=utf-8',
		});
		downloadBlob(blob, `${projectName}-gantt.svg`);
	}

	// PNG export — rasterize the Gantt SVG via canvas and download
	async function exportPng() {
		const serialized = buildSerializedSvg();
		if (!serialized) return;
		const projectName = (data.project_name || 'schedule').replace(/[^a-z0-9_-]+/gi, '-');
		const svgBlob = new Blob([serialized.xml], { type: 'image/svg+xml;charset=utf-8' });
		const url = URL.createObjectURL(svgBlob);
		try {
			const img = new Image();
			img.decoding = 'sync';
			const loaded = new Promise<void>((resolve, reject) => {
				img.onload = () => resolve();
				img.onerror = () => reject(new Error('Failed to rasterize SVG'));
			});
			img.src = url;
			await loaded;

			// Use 2x device pixel ratio for crisp output
			const scale = 2;
			const canvas = document.createElement('canvas');
			canvas.width = serialized.width * scale;
			canvas.height = serialized.height * scale;
			const ctx = canvas.getContext('2d');
			if (!ctx) return;
			ctx.scale(scale, scale);
			// White background so PNG is not transparent
			ctx.fillStyle = '#ffffff';
			ctx.fillRect(0, 0, serialized.width, serialized.height);
			ctx.drawImage(img, 0, 0);

			canvas.toBlob((blob) => {
				if (blob) downloadBlob(blob, `${projectName}-gantt.png`);
			}, 'image/png');
		} finally {
			URL.revokeObjectURL(url);
		}
	}

	// PDF export — opens print dialog with full schedule SVG
	function exportPdf() {
		if (!scrollContainer) return;
		const svg = scrollContainer.querySelector('svg');
		if (!svg) return;

		const svgClone = svg.cloneNode(true) as SVGElement;
		const projectName = data.project_name || 'Schedule';
		const dateStr = data.data_date ? ` — Data Date: ${formatDateShort(data.data_date)}` : '';

		const printWindow = window.open('', '_blank');
		if (!printWindow) return;

		printWindow.document.write(`<!DOCTYPE html>
<html><head><title>${projectName} — Gantt Chart</title>
<style>
@page { size: landscape; margin: 10mm; }
@media print {
  body { margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .page-break { page-break-before: always; break-before: page; }
  h1 { page-break-after: avoid; }
}
body { margin: 0; font-family: system-ui, sans-serif; }
h1 { font-size: 14px; margin: 4px 0; color: #111; }
.meta { font-size: 10px; color: #666; margin-bottom: 8px; }
svg { width: 100%; height: auto; }
</style></head><body>
<h1>${projectName}${dateStr}</h1>
<div class="meta">${searchFilteredData.activities.length} activities | Printed ${new Date().toLocaleDateString()}</div>
${svgClone.outerHTML}
</body></html>`);
		printWindow.document.close();
		printWindow.focus();
		setTimeout(() => printWindow.print(), 300);
	}

	// Tooltip data
	const hoveredActivity = $derived(
		hoveredId ? searchFilteredData.activities.find(a => a.task_id === hoveredId) : null
	);
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="schedule-viewer bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
	onmousemove={(e) => { mouseX = e.clientX; mouseY = e.clientY; }}
>
	<!-- Toolbar -->
	<div class="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
		<div class="flex items-center gap-3">
			<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{data.project_name || 'Schedule'}</h3>
			<span class="text-[10px] text-gray-500 dark:text-gray-400 flex items-center gap-1.5">
				<span class="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded font-mono">{searchFilteredData.activities.length}{searchFilteredData.activities.length !== data.summary.total_activities ? `/${data.summary.total_activities}` : ''}</span>
				<span class="text-red-500">{data.summary.critical_count}cp</span>
				<span class="text-orange-400">{data.summary.near_critical_count}nc</span>
				<span class="text-green-500">{data.summary.complete_pct.toFixed(0)}%</span>
				{#if data.project_start && data.project_finish}
					<span>{daysBetween(data.project_start, data.project_finish)}d</span>
				{/if}
			</span>
		</div>
		<div class="flex items-center gap-2">
			<!-- Search -->
			<div class="relative">
				<input
					type="text"
					bind:value={searchQuery}
					placeholder="Search activities..."
					class="w-36 text-[10px] rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 px-2 py-1 pr-6"
				/>
				{#if searchQuery}
					<button onclick={() => searchQuery = ''} aria-label="Clear search" class="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
						<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
					</button>
				{/if}
			</div>
			<span class="w-px h-4 bg-gray-300 dark:bg-gray-600"></span>
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
			<!-- Height controls -->
			<button onclick={() => viewerHeight = Math.max(300, viewerHeight - 100)} class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" title="Shorter" aria-label="Shorter">
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"/></svg>
			</button>
			<button onclick={() => viewerHeight = Math.min(900, viewerHeight + 100)} class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" title="Taller" aria-label="Taller">
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
			</button>
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
			<!-- WBS Depth filter -->
			{#if maxWbsDepth > 1}
				<select
					bind:value={wbsDepthFilter}
					class="text-[10px] rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 px-1 py-0.5"
					title="WBS depth filter"
				>
					<option value={0}>All Levels</option>
					{#each Array(maxWbsDepth) as _, i}
						<option value={i + 1}>Level {i + 1}</option>
					{/each}
				</select>
			{/if}
			<span class="w-px h-4 bg-gray-300 dark:bg-gray-600"></span>
			<!-- Export SVG -->
			<button
				onclick={exportSvg}
				class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
				title="Export SVG"
				aria-label="Export SVG"
			>
				<span class="text-[10px] font-bold">SVG</span>
			</button>
			<!-- Export PNG -->
			<button
				onclick={exportPng}
				class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
				title="Export PNG"
				aria-label="Export PNG"
			>
				<span class="text-[10px] font-bold">PNG</span>
			</button>
			<!-- Export PDF (print) -->
			<button onclick={exportPdf} class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" title="Export PDF (Print with per-WBS page breaks)" aria-label="Export PDF">
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
				</svg>
			</button>
		</div>
	</div>

	<!-- Main content: WBS Tree (left) + Gantt (right) -->
	<div class="flex" style="height: {viewerHeight}px;">
		<!-- WBS Tree -->
		<WBSTree
			{flatRows}
			{collapsedWbs}
			rowHeight={ROW_HEIGHT}
			{scrollTop}
			{containerHeight}
			{wbsAggregates}
			onToggleWbs={toggleWbs}
			onHover={handleHover}
		/>

		<!-- Gantt Canvas (scrollable, drag-to-pan) -->
		<div
			bind:this={scrollContainer}
			onscroll={handleScroll}
			onmousedown={handleMouseDown}
			onmousemove={handleMouseMove}
			onmouseup={handleMouseUp}
			onmouseleave={handleMouseUp}
			class="flex-1 overflow-auto"
			style="cursor: grab;"
		>
			<GanttCanvas
				{flatRows}
				activities={searchFilteredData.activities}
				relationships={showDependencies ? searchFilteredData.relationships : []}
				startDate={searchFilteredData.project_start}
				endDate={searchFilteredData.project_finish}
				dataDate={searchFilteredData.data_date}
				holidays={data.holidays || []}
				{wbsAggregates}
				{zoomLevel}
				rowHeight={ROW_HEIGHT}
				{scrollTop}
				{containerHeight}
				{hoveredId}
				{showFloat}
				{showBaseline}
				onHover={handleHover}
				onClick={onActivityClick}
			/>
		</div>
	</div>

	<!-- Status bar (compact) -->
	{#if hoveredActivity}
		<div class="border-t border-gray-200 dark:border-gray-700 px-3 py-1.5 bg-gray-50 dark:bg-gray-800 flex items-center gap-3 text-[10px]">
			<span class="font-semibold text-gray-900 dark:text-gray-100">{hoveredActivity.task_code}</span>
			<span class="text-gray-600 dark:text-gray-400 truncate max-w-xs">{hoveredActivity.task_name}</span>
			<span class="text-gray-500">{formatDateShort(hoveredActivity.early_start)} — {formatDateShort(hoveredActivity.early_finish)}</span>
			<span class="text-gray-500">{hoveredActivity.duration_days}d</span>
			<span class="{hoveredActivity.total_float_days < 0 ? 'text-red-600 font-bold' : hoveredActivity.total_float_days === 0 ? 'text-amber-600' : 'text-green-600'}">TF:{hoveredActivity.total_float_days}d</span>
			{#if hoveredActivity.progress_pct > 0}
				<span class="text-blue-600">{hoveredActivity.progress_pct}%</span>
			{/if}
		</div>
	{/if}

	<!-- Floating Magic Box tooltip -->
	{#if hoveredActivity}
		<ActivityTooltip activity={hoveredActivity} x={mouseX} y={mouseY} />
	{/if}

	<!-- Legend -->
	<div class="border-t border-gray-200 dark:border-gray-700 px-3 py-1.5 flex items-center gap-3 text-[9px] text-gray-500 dark:text-gray-400">
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm bg-red-500"></span> Critical</span>
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm bg-blue-500"></span> Active</span>
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm bg-green-500"></span> Complete</span>
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm bg-gray-400"></span> Not Started</span>
		<span class="flex items-center gap-1"><span class="w-2 h-2 rotate-45 bg-amber-500"></span> Milestone</span>
		<span class="flex items-center gap-1"><span class="w-3 h-1 rounded-sm bg-green-500 opacity-80"></span> Actual</span>
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm border border-dashed border-gray-400 bg-gray-100"></span> LOE</span>
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
