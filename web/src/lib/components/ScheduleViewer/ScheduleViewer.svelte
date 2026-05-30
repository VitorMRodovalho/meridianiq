<script lang="ts">
	import type { ScheduleViewData, GroupDimension, WBSNode } from './types';
	import WBSTree from './WBSTree.svelte';
	import GanttCanvas from './GanttCanvas.svelte';
	import ActivityTooltip from './ActivityTooltip.svelte';
	import { onMount, untrack } from 'svelte';
	import { t } from '$lib/i18n';
	import { daysBetween, formatDateShort, computeWBSAggregates, buildFlatRows, getMaxWBSDepth, collectActivitiesByWbs, applyClientGrouping, presetCollapse, defaultGroupLabel } from './utils';

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

	// One-shot smart defaults — keyed on a STABLE DATA TOKEN (project identity + size), NOT object
	// identity. The page hands us a freshly-spread `data` object on every status-filter change; keying
	// on identity would re-fire init and stomp the user's manual collapse + zoom. The token is stable
	// across those filtered re-derivations (same project / dates / total), so defaults run exactly once
	// per real project load.
	let initedToken = $state('');
	function dataToken(d: ScheduleViewData): string {
		return `${d.project_name}|${d.data_date}|${d.project_start}|${d.project_finish}|${d.summary.total_activities}`;
	}
	function initDefaults() {
		collapsedWbs = presetCollapse(groupBy, wbsDepthFilter, data.wbs_tree, data.summary.total_activities);
		// Auto-zoom based on project duration
		if (data.project_start && data.project_finish) {
			const days = daysBetween(data.project_start, data.project_finish);
			zoomLevel = days > 365 ? 'month' : days > 60 ? 'week' : 'day';
		}
	}

	$effect(() => {
		const token = dataToken(data);
		if (token !== initedToken) {
			initedToken = token;
			untrack(() => initDefaults());
		}
	});

	// State
	let collapsedWbs = $state<Set<string>>(new Set());
	let zoomLevel = $state<'day' | 'week' | 'month'>('week');
	let groupBy = $state<GroupDimension>('wbs');
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

	// Translated label for a synthetic group node (falls back to the built-in English label).
	function bucketLabel(dim: GroupDimension, key: string): string {
		if (dim === 'calendar') {
			return key === 'default' ? $t('schedule.bucket.calendar_default', 'Default') : key;
		}
		return $t(`schedule.bucket.${dim}.${key}`, defaultGroupLabel(dim, key));
	}

	// W3: instant client-side regroup. group_by=wbs is identity (the real hierarchy); any other
	// dimension is a pure $derived transform — zero refetch. Reading $t inside keeps the synthetic
	// node labels reactive to locale changes.
	const viewData = $derived(
		groupBy === 'wbs'
			? searchFilteredData
			: applyClientGrouping(searchFilteredData, groupBy, bucketLabel)
	);

	// WBS aggregates (computed once, shared by WBSTree and GanttCanvas)
	const wbsAggregates = $derived(computeWBSAggregates(viewData.activities, viewData.wbs_tree));

	// WBS roll-up-to-level filter (0 = all levels) — only meaningful under the wbs dimension.
	let wbsDepthFilter = $state(0);
	const maxWbsDepth = $derived(getMaxWBSDepth(data.wbs_tree));

	// Dimension display label for the "grouped by …" indicator.
	const GROUP_LABEL_KEY: Record<GroupDimension, string> = {
		wbs: 'schedule.group_wbs',
		status: 'schedule.group_status',
		critical: 'schedule.group_critical',
		task_type: 'schedule.group_task_type',
		calendar: 'schedule.group_calendar',
		float_bucket: 'schedule.group_float_bucket',
	};

	// Reset collapse + transient view state on a dimension switch OR a roll-up-level change. Both are
	// presets the user can then toggle on top of. collapsedWbs is keyed by real wbs_id, so it MUST NOT
	// carry across a switch to a synthetic '_grp_*' tree. Only groupBy + wbsDepthFilter are tracked
	// (read outside untrack); every state write and the prev/data reads are untracked, so the effect is
	// data-change-independent and settles deterministically — it re-runs ONLY on a genuine input change.
	let prevGroupBy = $state<GroupDimension>('wbs');
	let prevDepthFilter = $state(0);
	$effect(() => {
		const dim = groupBy;
		const depth = wbsDepthFilter;
		untrack(() => {
			const dimChanged = dim !== prevGroupBy;
			const depthChanged = depth !== prevDepthFilter;
			if (!dimChanged && !depthChanged) return;
			if (dimChanged) {
				prevGroupBy = dim;
				// flatRows becomes a different array — reset scroll + hover so the viewport and
				// highlight don't point at unrelated rows. zoom/height are dimension-independent.
				if (scrollContainer) scrollContainer.scrollTop = 0;
				scrollTop = 0;
				hoveredId = '';
				// roll-up depth only applies under wbs; snap it back so the select matches the reset view
				wbsDepthFilter = 0;
			}
			prevDepthFilter = wbsDepthFilter;
			collapsedWbs = presetCollapse(dim, wbsDepthFilter, data.wbs_tree, data.summary.total_activities);
		});
	});

	// Single source of truth: flat row list shared by WBSTree and GanttCanvas
	const isFiltered = $derived(criticalOnly || searchQuery.trim() !== '' || groupBy !== 'wbs');
	const flatRows = $derived(buildFlatRows(
		viewData.wbs_tree,
		viewData.activities,
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
		// Operate on the CURRENT view tree (real WBS or a synthetic grouped tree), not the
		// raw server payload — otherwise collapse-all does nothing under a non-WBS grouping.
		const all = new Set<string>();
		function collect(nodes: WBSNode[]) {
			for (const n of nodes) {
				all.add(n.wbs_id);
				collect(n.children);
			}
		}
		collect(viewData.wbs_tree);
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
			// Don't hijack keystrokes while a form control is focused (search box, the new
			// group-by / roll-up selects) — typing 'e'/'c'/'+'/'-' there must not fire viewer actions.
			const tgt = e.target;
			if (tgt instanceof HTMLElement && ['INPUT', 'SELECT', 'TEXTAREA'].includes(tgt.tagName)) return;
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

	// Escape interpolations written into the detached print windows below. Both the
	// project name (user data) AND the click-time-read $t() translations can contain
	// & < > (esp. pt-BR), so every interpolated string must pass through this.
	function escapeHtml(s: string): string {
		return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
		// Read translations at click-time (the print window has no Svelte runtime) and
		// escape every interpolation (project name is user data; $t() can carry & < >).
		const projectName = escapeHtml(data.project_name || $t('schedule.viewer.default_project_name'));
		const ganttLabel = escapeHtml($t('schedule.viewer.print_title_gantt'));
		const dateStr = data.data_date
			? ` — ${escapeHtml($t('schedule.viewer.data_date'))}: ${escapeHtml(formatDateShort(data.data_date))}`
			: '';
		const activitiesLabel = escapeHtml($t('schedule.viewer.print_activities'));
		const printedLabel = escapeHtml($t('schedule.viewer.print_printed'));
		// Convention for both print functions: every interpolated value is escaped
		// at DEFINITION and interpolated bare below — so no use site can forget it.
		const printedDate = escapeHtml(new Date().toLocaleDateString());

		const printWindow = window.open('', '_blank');
		if (!printWindow) return;

		printWindow.document.write(`<!DOCTYPE html>
<html><head><title>${projectName} — ${ganttLabel}</title>
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
<div class="meta">${searchFilteredData.activities.length} ${activitiesLabel} | ${printedLabel} ${printedDate}</div>
${svgClone.outerHTML}
</body></html>`);
		printWindow.document.close();
		printWindow.focus();
		setTimeout(() => printWindow.print(), 300);
	}

	// Per-WBS print export — one printable table per top-level WBS node,
	// with page-break-before: always between sections. Uses the visible
	// (search-filtered) data so filters flow through to the print output.
	function exportPdfByWbs() {
		const roots = searchFilteredData.wbs_tree;
		if (roots.length === 0) return;

		// Convention: every interpolated value is escaped at DEFINITION and used bare
		// below, so no use site can forget it (project name is user data; pt-BR/es $t()
		// strings can carry & < >; the detached print window has no Svelte reactivity).
		const projectName = escapeHtml(data.project_name || $t('schedule.viewer.default_project_name'));
		const tr = {
			code: escapeHtml($t('schedule.col_code')),
			name: escapeHtml($t('schedule.col_name')),
			start: escapeHtml($t('schedule.viewer.print_col_start')),
			finish: escapeHtml($t('schedule.viewer.print_col_finish')),
			dur: escapeHtml($t('schedule.col_od')),
			tf: escapeHtml($t('schedule.col_tf')),
			pct: escapeHtml($t('schedule.col_pct')),
			status: escapeHtml($t('schedule.detail_status')),
			complete: escapeHtml($t('schedule.status_complete')),
			active: escapeHtml($t('schedule.status_active')),
			notStarted: escapeHtml($t('schedule.status_not_started')),
			activities: escapeHtml($t('schedule.viewer.print_activities')),
			printed: escapeHtml($t('schedule.viewer.print_printed')),
			byWbsTitle: escapeHtml($t('schedule.viewer.print_by_wbs_title')),
			headingByWbs: escapeHtml($t('schedule.viewer.print_heading_by_wbs')),
		};
		const dateStr = data.data_date
			? `${escapeHtml($t('schedule.viewer.data_date'))}: ${escapeHtml(formatDateShort(data.data_date))}`
			: '';
		const printedDate = escapeHtml(new Date().toLocaleDateString());

		const sections: string[] = [];
		let firstPage = true;
		for (const root of roots) {
			const acts = collectActivitiesByWbs(root, searchFilteredData.activities);
			if (acts.length === 0) continue;

			const rows = acts
				.map((a) => {
					const critCls = a.is_critical ? ' class="critical"' : '';
					const status =
						a.status === 'complete'
							? tr.complete
							: a.status === 'active'
								? tr.active
								: tr.notStarted;
					return `<tr${critCls}>
						<td>${escapeHtml(a.task_code)}</td>
						<td>${escapeHtml(a.task_name)}</td>
						<td>${escapeHtml(formatDateShort(a.early_start))}</td>
						<td>${escapeHtml(formatDateShort(a.early_finish))}</td>
						<td class="num">${a.duration_days.toFixed(0)}</td>
						<td class="num">${a.total_float_days.toFixed(0)}</td>
						<td class="num">${a.progress_pct.toFixed(0)}%</td>
						<td>${status}</td>
					</tr>`;
				})
				.join('\n');

			const pageClass = firstPage ? 'wbs-page' : 'wbs-page page-break';
			firstPage = false;
			sections.push(`<section class="${pageClass}">
				<h2>${escapeHtml(root.name)}</h2>
				<div class="meta">${acts.length} ${tr.activities}</div>
				<table>
					<thead><tr>
						<th>${tr.code}</th>
						<th>${tr.name}</th>
						<th>${tr.start}</th>
						<th>${tr.finish}</th>
						<th class="num">${tr.dur}</th>
						<th class="num">${tr.tf}</th>
						<th class="num">${tr.pct}</th>
						<th>${tr.status}</th>
					</tr></thead>
					<tbody>${rows}</tbody>
				</table>
			</section>`);
		}

		if (sections.length === 0) return;

		const printWindow = window.open('', '_blank');
		if (!printWindow) return;

		printWindow.document.write(`<!DOCTYPE html>
<html><head><title>${projectName} — ${tr.byWbsTitle}</title>
<style>
@page { size: letter portrait; margin: 12mm; }
@media print {
	body { margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
	.page-break { page-break-before: always; break-before: page; }
	table { page-break-inside: auto; }
	tr { page-break-inside: avoid; }
	thead { display: table-header-group; }
	h1, h2 { page-break-after: avoid; }
}
body { margin: 0; font-family: system-ui, sans-serif; color: #111; }
h1 { font-size: 14px; margin: 0 0 2px; }
h2 { font-size: 13px; margin: 6px 0; padding-bottom: 4px; border-bottom: 1px solid #9ca3af; }
.cover { margin-bottom: 14px; }
.meta { font-size: 10px; color: #666; margin-bottom: 6px; }
table { width: 100%; border-collapse: collapse; font-size: 10px; }
th, td { padding: 3px 6px; border-bottom: 1px solid #e5e7eb; text-align: left; }
th { background: #f3f4f6; font-weight: 600; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
tr.critical td { background: #fef2f2; color: #991b1b; font-weight: 500; }
section.wbs-page { margin-bottom: 10px; }
</style></head><body>
<div class="cover">
	<h1>${projectName} — ${tr.headingByWbs}</h1>
	<div class="meta">${dateStr} | ${searchFilteredData.activities.length} ${tr.activities} | ${tr.printed} ${printedDate}</div>
</div>
${sections.join('\n')}
</body></html>`);
		printWindow.document.close();
		printWindow.focus();
		setTimeout(() => printWindow.print(), 300);
	}

	// Tooltip data
	const hoveredActivity = $derived(
		hoveredId ? viewData.activities.find(a => a.task_id === hoveredId) : null
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
			<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{data.project_name || $t('schedule.viewer.default_project_name')}</h3>
			<span class="text-[10px] text-gray-500 dark:text-gray-400 flex items-center gap-1.5">
				<span class="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded font-mono">{searchFilteredData.activities.length}{searchFilteredData.activities.length !== data.summary.total_activities ? `/${data.summary.total_activities}` : ''}</span>
				<span class="text-red-500">{data.summary.critical_count}cp</span>
				<span class="text-orange-400">{data.summary.near_critical_count}nc</span>
				<span class="text-green-500">{data.summary.complete_pct.toFixed(0)}%</span>
				{#if data.project_start && data.project_finish}
					<span>{daysBetween(data.project_start, data.project_finish)}d</span>
				{/if}
			</span>
			{#if groupBy !== 'wbs'}
				<span
					class="text-[9px] px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 whitespace-nowrap"
					title={$t('schedule.flattened_hint')}
				>
					{$t('schedule.grouped_by')}: {$t(GROUP_LABEL_KEY[groupBy])}
				</span>
			{/if}
		</div>
		<div class="flex items-center gap-2">
			<!-- Search -->
			<div class="relative">
				<input
					type="text"
					bind:value={searchQuery}
					placeholder={$t('schedule.viewer.search_placeholder')}
					class="w-36 text-[10px] rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 px-2 py-1 pr-6"
				/>
				{#if searchQuery}
					<button onclick={() => searchQuery = ''} aria-label={$t('schedule.viewer.clear_search')} class="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
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
					{$t('schedule.viewer.zoom_' + level)}
				</button>
			{/each}
			<span class="w-px h-4 bg-gray-300 dark:bg-gray-600"></span>
			<!-- Height controls -->
			<button onclick={() => viewerHeight = Math.max(300, viewerHeight - 100)} class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" title={$t('schedule.viewer.shorter')} aria-label={$t('schedule.viewer.shorter')}>
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"/></svg>
			</button>
			<button onclick={() => viewerHeight = Math.min(900, viewerHeight + 100)} class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" title={$t('schedule.viewer.taller')} aria-label={$t('schedule.viewer.taller')}>
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
			</button>
			<span class="w-px h-4 bg-gray-300 dark:bg-gray-600"></span>
			<!-- Expand/Collapse -->
			<button onclick={expandAll} class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" title={$t('shortcuts.expand_all')} aria-label={$t('shortcuts.expand_all')}>
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
				</svg>
			</button>
			<button onclick={collapseAll} class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" title={$t('shortcuts.collapse_all')} aria-label={$t('shortcuts.collapse_all')}>
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9V4.5M9 9H4.5M9 9L3.5 3.5M9 15v4.5M9 15H4.5M9 15l-5.5 5.5M15 9h4.5M15 9V4.5M15 9l5.5-5.5M15 15h4.5M15 15v4.5m0-4.5l5.5 5.5" />
				</svg>
			</button>
			<!-- Group-by dimension (instant, client-side regroup — no server round-trip) -->
			<select
				bind:value={groupBy}
				aria-label={$t('schedule.group_by_label')}
				title={$t('schedule.group_by_label')}
				class="text-[10px] rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 px-1 py-0.5"
			>
				<option value="wbs">{$t('schedule.group_wbs')}</option>
				<option value="status">{$t('schedule.group_status')}</option>
				<option value="critical">{$t('schedule.group_critical')}</option>
				<option value="task_type">{$t('schedule.group_task_type')}</option>
				<option value="calendar">{$t('schedule.group_calendar')}</option>
				<option value="float_bucket">{$t('schedule.group_float_bucket')}</option>
			</select>
			<!-- WBS roll-up to level (only meaningful under the WBS dimension) -->
			{#if groupBy === 'wbs' && maxWbsDepth > 1}
				<select
					bind:value={wbsDepthFilter}
					aria-label={$t('schedule.roll_up_level')}
					title={$t('schedule.roll_up_level')}
					class="text-[10px] rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 px-1 py-0.5"
				>
					<option value={0}>{$t('schedule.all_levels')}</option>
					{#each Array(maxWbsDepth) as _, i}
						<option value={i + 1}>{$t('schedule.level')} {i + 1}</option>
					{/each}
				</select>
			{/if}
			<span class="w-px h-4 bg-gray-300 dark:bg-gray-600"></span>
			<!-- Export SVG -->
			<button
				onclick={exportSvg}
				class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
				title={$t('schedule.viewer.export_svg')}
				aria-label={$t('schedule.viewer.export_svg')}
			>
				<span class="text-[10px] font-bold">SVG</span>
			</button>
			<!-- Export PNG -->
			<button
				onclick={exportPng}
				class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
				title={$t('schedule.viewer.export_png')}
				aria-label={$t('schedule.viewer.export_png')}
			>
				<span class="text-[10px] font-bold">PNG</span>
			</button>
			<!-- Export PDF (print, single-page Gantt SVG) -->
			<button onclick={exportPdf} class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" title={$t('schedule.viewer.print_gantt')} aria-label={$t('schedule.viewer.print_gantt_aria')}>
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
				</svg>
			</button>
			<!-- Print by WBS (one page per top-level WBS) -->
			<button
				onclick={exportPdfByWbs}
				class="text-[10px] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 font-bold"
				title={$t('schedule.viewer.print_by_wbs')}
				aria-label={$t('schedule.viewer.print_by_wbs_aria')}
			>
				WBS
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
				activities={viewData.activities}
				relationships={showDependencies && groupBy === 'wbs' ? viewData.relationships : []}
				startDate={viewData.project_start}
				endDate={viewData.project_finish}
				dataDate={viewData.data_date}
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
			<span class="{hoveredActivity.total_float_days < 0 ? 'text-red-600 font-bold' : hoveredActivity.total_float_days === 0 ? 'text-amber-600' : 'text-green-600'}">{$t('schedule.col_tf')}:{hoveredActivity.total_float_days}d</span>
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
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm bg-red-500"></span> {$t('schedule.viewer.legend_critical')}</span>
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm bg-blue-500"></span> {$t('schedule.viewer.legend_active')}</span>
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm bg-green-500"></span> {$t('schedule.viewer.legend_complete')}</span>
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm bg-gray-400"></span> {$t('schedule.viewer.legend_not_started')}</span>
		<span class="flex items-center gap-1"><span class="w-2 h-2 rotate-45 bg-amber-500"></span> {$t('schedule.viewer.legend_milestone')}</span>
		<span class="flex items-center gap-1"><span class="w-3 h-1 rounded-sm bg-green-500 opacity-80"></span> {$t('schedule.viewer.legend_actual')}</span>
		<span class="flex items-center gap-1"><span class="w-3 h-2 rounded-sm border border-dashed border-gray-400 bg-gray-100"></span> {$t('schedule.viewer.legend_loe')}</span>
		{#if showBaseline}
			<span class="flex items-center gap-1"><span class="w-3 h-1.5 rounded-sm bg-gray-400 opacity-50 border border-dashed border-gray-500"></span> {$t('schedule.viewer.legend_baseline')}</span>
		{/if}
		{#if showFloat}
			<span class="flex items-center gap-1"><span class="w-3 h-1 rounded-sm bg-amber-400 opacity-60"></span> {$t('schedule.viewer.legend_float')}</span>
		{/if}
		{#if data.data_date}
			<span class="ml-auto text-amber-600">{$t('schedule.viewer.data_date')}: {formatDateShort(data.data_date)}</span>
		{/if}
	</div>
</div>
