<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';
	import { supabase } from '$lib/supabase';
	import { page } from '$app/stores';
	import ScheduleViewer from '$lib/components/ScheduleViewer/ScheduleViewer.svelte';
	import ResourceHistogramPanel from '$lib/components/ScheduleViewer/ResourceHistogramPanel.svelte';
	import type { ScheduleViewData } from '$lib/components/ScheduleViewer/types';

	let projects: { project_id: string; name: string; tags?: string[] }[] = $state([]);
	let selectedProject: string = $state('');
	let baselineProject: string = $state('');
	let groupBy: string = $state('wbs');
	let data = $state<ScheduleViewData | null>(null);
	let loading: boolean = $state(false);
	let error: string = $state('');
	let selectedActivity = $state<import('$lib/components/ScheduleViewer/types').ActivityView | null>(null);
	let showFloat: boolean = $state(true);
	let showBaseline: boolean = $state(true);
	let showDependencies: boolean = $state(false);
	let criticalOnly: boolean = $state(false);
	let statusFilter: string = $state('all');

	// Filtered data based on status
	const displayData = $derived.by(() => {
		if (!data || statusFilter === 'all') return data;
		let filtered: typeof data.activities;
		switch (statusFilter) {
			case 'active': filtered = data.activities.filter(a => a.status === 'active'); break;
			case 'not_started': filtered = data.activities.filter(a => a.status === 'not_started'); break;
			case 'complete': filtered = data.activities.filter(a => a.status === 'complete'); break;
			case 'critical': filtered = data.activities.filter(a => a.is_critical); break;
			case 'near_critical': filtered = data.activities.filter(a => a.total_float_days > 0 && a.total_float_days <= 10 && a.status !== 'complete'); break;
			case 'negative_float': filtered = data.activities.filter(a => a.total_float_days < 0); break;
			case 'milestones': filtered = data.activities.filter(a => a.task_type === 'milestone'); break;
			case 'constrained': filtered = data.activities.filter(a => a.constraint_type && a.constraint_type !== '' && a.constraint_type !== 'CS_MEO'); break;
			default: filtered = data.activities;
		}
		return { ...data, activities: filtered };
	});

	// Float distribution for mini-chart
	const floatDistribution = $derived(data ? (() => {
		const buckets = { 'Negative': 0, '0': 0, '1-10': 0, '11-20': 0, '21-44': 0, '>44': 0 };
		for (const a of data.activities) {
			if (a.status === 'complete') continue;
			const f = a.total_float_days;
			if (f < 0) buckets['Negative']++;
			else if (f === 0) buckets['0']++;
			else if (f <= 10) buckets['1-10']++;
			else if (f <= 20) buckets['11-20']++;
			else if (f <= 44) buckets['21-44']++;
			else buckets['>44']++;
		}
		return Object.entries(buckets).map(([label, value]) => ({ label, value }));
	})() : []);

	const statusCounts = $derived(data ? {
		all: data.activities.length,
		active: data.activities.filter(a => a.status === 'active').length,
		not_started: data.activities.filter(a => a.status === 'not_started').length,
		complete: data.activities.filter(a => a.status === 'complete').length,
		critical: data.activities.filter(a => a.is_critical).length,
		near_critical: data.activities.filter(a => a.total_float_days > 0 && a.total_float_days <= 10 && a.status !== 'complete').length,
		negative_float: data.activities.filter(a => a.total_float_days < 0).length,
		milestones: data.activities.filter(a => a.task_type === 'milestone').length,
	} : null);

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
		}
	}

	async function loadSchedule() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		data = null;
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = session?.access_token
				? { Authorization: `Bearer ${session.access_token}` }
				: {};
			const queryParts: string[] = [];
			if (baselineProject) queryParts.push(`baseline_id=${baselineProject}`);
			if (groupBy && groupBy !== 'wbs') queryParts.push(`group_by=${groupBy}`);
			const params = queryParts.length ? `?${queryParts.join('&')}` : '';
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/schedule-view${params}`, { headers });
			if (!res.ok) throw new Error(await res.text());
			data = await res.json();
			toastSuccess(`Loaded ${data!.summary.total_activities} activities`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	let autoLoaded = $state(false);

	$effect(() => {
		loadProjects();
		// Read URL params for pre-selection from compare page
		const params = $page.url.searchParams;
		if (params.get('project')) selectedProject = params.get('project')!;
		if (params.get('baseline')) baselineProject = params.get('baseline')!;
	});

	// Auto-load when URL params provide project ID
	$effect(() => {
		if (selectedProject && projects.length > 0 && !data && !loading && !autoLoaded) {
			autoLoaded = true;
			loadSchedule();
		}
	});

	// Column configuration
	interface ColDef {
		id: string;
		labelKey: string;
		sortKey: string;
		align: string;
		visible: boolean;
		render: (act: import('$lib/components/ScheduleViewer/types').ActivityView) => string;
	}

	let columns = $state<ColDef[]>([
		{ id: 'code', labelKey: 'schedule.col_code', sortKey: 'code', align: 'text-left', visible: true, render: a => a.task_code },
		{ id: 'name', labelKey: 'schedule.col_name', sortKey: 'name', align: 'text-left', visible: true, render: a => a.task_name },
		{ id: 'wbs', labelKey: 'schedule.col_wbs', sortKey: '', align: 'text-left', visible: true, render: a => a.wbs_path?.split('/').pop() || '' },
		{ id: 'status', labelKey: 'schedule.col_status', sortKey: 'status', align: 'text-left', visible: true, render: a => a.status },
		{ id: 'type', labelKey: 'schedule.col_type', sortKey: '', align: 'text-left', visible: false, render: a => a.task_type },
		{ id: 'od', labelKey: 'schedule.col_od', sortKey: 'duration', align: 'text-right', visible: true, render: a => a.duration_days + 'd' },
		{ id: 'rd', labelKey: 'schedule.col_rd', sortKey: '', align: 'text-right', visible: true, render: a => a.remaining_days > 0 ? a.remaining_days + 'd' : '' },
		{ id: 'tf', labelKey: 'schedule.col_tf', sortKey: 'float', align: 'text-right', visible: true, render: a => a.total_float_days + 'd' },
		{ id: 'ff', labelKey: 'schedule.col_ff', sortKey: '', align: 'text-right', visible: true, render: a => a.free_float_days !== 0 ? a.free_float_days + 'd' : '' },
		{ id: 'pct', labelKey: 'schedule.col_pct', sortKey: 'progress', align: 'text-right', visible: true, render: a => a.progress_pct > 0 ? a.progress_pct + '%' : '' },
		{ id: 'es', labelKey: 'schedule.col_es', sortKey: 'start', align: 'text-left', visible: true, render: a => a.early_start },
		{ id: 'ef', labelKey: 'schedule.col_ef', sortKey: 'finish', align: 'text-left', visible: true, render: a => a.early_finish },
		{ id: 'ls', labelKey: 'schedule.col_ls', sortKey: '', align: 'text-left', visible: false, render: a => (a as any).late_start || '' },
		{ id: 'lf', labelKey: 'schedule.col_lf', sortKey: '', align: 'text-left', visible: false, render: a => (a as any).late_finish || '' },
		{ id: 'as', labelKey: 'schedule.col_as', sortKey: '', align: 'text-left', visible: true, render: a => a.actual_start || '' },
		{ id: 'af', labelKey: 'schedule.col_af', sortKey: '', align: 'text-left', visible: true, render: a => a.actual_finish || '' },
		{ id: 'bs', labelKey: 'schedule.col_bs', sortKey: '', align: 'text-left', visible: false, render: a => a.baseline_start || '' },
		{ id: 'bf', labelKey: 'schedule.col_bf', sortKey: '', align: 'text-left', visible: false, render: a => a.baseline_finish || '' },
		{ id: 'cp', labelKey: 'schedule.col_cp', sortKey: '', align: 'text-center', visible: true, render: a => a.is_critical ? '●' : '' },
		{ id: 'constraint', labelKey: 'schedule.col_constraint', sortKey: '', align: 'text-left', visible: false, render: a => a.constraint_type && a.constraint_type !== 'CS_MEO' ? a.constraint_type : '' },
		{ id: 'sv', labelKey: 'schedule.col_sv', sortKey: '', align: 'text-right', visible: false, render: a => a.start_variance_days != null && a.start_variance_days !== 0 ? `${a.start_variance_days > 0 ? '+' : ''}${a.start_variance_days}d` : '' },
		{ id: 'fv', labelKey: 'schedule.col_fv', sortKey: '', align: 'text-right', visible: false, render: a => a.finish_variance_days != null && a.finish_variance_days !== 0 ? `${a.finish_variance_days > 0 ? '+' : ''}${a.finish_variance_days}d` : '' },
		{ id: 'alerts', labelKey: 'schedule.col_alerts', sortKey: '', align: 'text-left', visible: true, render: _ => '' },
	]);

	const visibleColumns = $derived(columns.filter(c => c.visible));
	let showColumnConfig = $state(false);

	function toggleColumn(id: string) {
		columns = columns.map(c => c.id === id ? { ...c, visible: !c.visible } : c);
	}

	// WBS filter for activity table
	let wbsFilter = $state('');
	const uniqueWbsPaths = $derived.by(() => {
		if (!data) return [];
		const paths = new Set<string>();
		for (const a of data.activities) {
			if (a.wbs_path) {
				const parts = a.wbs_path.split('/');
				// Add each level
				for (let i = 1; i <= parts.length; i++) {
					paths.add(parts.slice(0, i).join('/'));
				}
			}
		}
		return [...paths].sort();
	});

	// Table sorting
	let sortCol = $state<string>('');
	let sortAsc = $state(true);

	function toggleSort(col: string) {
		if (sortCol === col) {
			sortAsc = !sortAsc;
		} else {
			sortCol = col;
			sortAsc = true;
		}
	}

	const sortedActivities = $derived.by(() => {
		let base = data?.activities || [];
		if (wbsFilter) {
			base = base.filter(a => a.wbs_path?.startsWith(wbsFilter));
		}
		if (!sortCol) return base;
		const acts = [...base];
		const dir = sortAsc ? 1 : -1;
		acts.sort((a, b) => {
			let va: string | number, vb: string | number;
			switch (sortCol) {
				case 'code': va = a.task_code; vb = b.task_code; break;
				case 'name': va = a.task_name; vb = b.task_name; break;
				case 'status': va = a.status; vb = b.status; break;
				case 'duration': va = a.duration_days; vb = b.duration_days; break;
				case 'float': va = a.total_float_days; vb = b.total_float_days; break;
				case 'progress': va = a.progress_pct; vb = b.progress_pct; break;
				case 'start': va = a.early_start; vb = b.early_start; break;
				case 'finish': va = a.early_finish; vb = b.early_finish; break;
				default: return 0;
			}
			if (va < vb) return -1 * dir;
			if (va > vb) return 1 * dir;
			return 0;
		});
		return acts;
	});

	// Table virtual scrolling
	const TABLE_ROW_H = 24;
	const TABLE_BUFFER = 30;
	let tableContainer: HTMLDivElement | null = $state(null);
	let tableScrollTop = $state(0);
	let tableContainerH = $state(384);

	function handleTableScroll(e: Event) {
		const el = e.target as HTMLDivElement;
		tableScrollTop = el.scrollTop;
		tableContainerH = el.clientHeight;
	}

	const tableVStart = $derived(Math.max(0, Math.floor(tableScrollTop / TABLE_ROW_H) - TABLE_BUFFER));
	const tableVEnd = $derived(Math.min(sortedActivities.length, Math.ceil((tableScrollTop + tableContainerH) / TABLE_ROW_H) + TABLE_BUFFER));
	const tableRenderedRows = $derived(sortedActivities.slice(tableVStart, tableVEnd));

	function exportCSV() {
		if (!data) return;
		const headers = [
			$t('schedule.col_code'), $t('schedule.col_name'), $t('schedule.col_wbs'),
			$t('schedule.col_status'), $t('schedule.col_type'),
			$t('schedule.detail_duration'), $t('schedule.detail_total_float'), $t('schedule.detail_free_float'),
			$t('schedule.detail_progress'),
			$t('schedule.detail_early_start'), $t('schedule.detail_early_finish'),
			$t('schedule.detail_actual_start'), $t('schedule.detail_actual_finish'),
			$t('schedule.detail_late_start'), $t('schedule.detail_late_finish'),
			$t('schedule.detail_critical'), $t('schedule.detail_constraint'), 'WBS Path',
			$t('schedule.col_alerts'),
		];
		const rows = data.activities.map(a => [
			a.task_code, a.task_name, a.wbs_path?.split('/').pop() || '', a.status, a.task_type,
			a.duration_days, a.total_float_days, a.free_float_days, a.progress_pct,
			a.early_start, a.early_finish,
			a.actual_start || '', a.actual_finish || '',
			a.late_start, a.late_finish,
			a.is_critical ? $t('schedule.csv_critical_yes') : $t('schedule.csv_critical_no'), a.constraint_type || '', a.wbs_path,
			a.alerts.join('; '),
		]);
		const csv = [headers.join(','), ...rows.map(r => r.map(v => `"${v}"`).join(','))].join('\n');
		const blob = new Blob([csv], { type: 'text/csv' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `schedule-${selectedProject}.csv`;
		a.click();
		URL.revokeObjectURL(url);
	}
</script>

<svelte:head>
	<title>{$t('page.schedule')} - MeridianIQ</title>
</svelte:head>

<main class="max-w-[1400px] mx-auto px-4 py-6">
	<div class="flex items-center justify-between mb-6">
		<div>
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.schedule')}</h1>
			<p class="text-gray-500 dark:text-gray-400 mt-1">{$t('schedule.subtitle')}</p>
		</div>
		{#if selectedProject}
			<div class="flex items-center gap-2">
				<a href="/projects/{selectedProject}" class="px-3 py-1.5 text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700">{$t('schedule.nav_project_detail')}</a>
				<a href="/scorecard?project={selectedProject}" class="px-3 py-1.5 text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700">{$t('schedule.nav_scorecard')}</a>
				<a href="/anomalies?project={selectedProject}" class="px-3 py-1.5 text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700">{$t('schedule.nav_anomalies')}</a>
			</div>
		{/if}
	</div>

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-6">
		<div class="flex items-end gap-4 flex-wrap">
			<div class="flex-1 min-w-48">
				<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('common.project')}</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 px-3 py-2 text-sm">
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}{p.tags?.length ? ` [${p.tags.slice(0, 3).join(', ')}]` : ''}</option>
					{/each}
				</select>
			</div>
			<div class="flex-1 min-w-48">
				<label for="baseline" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('schedule.baseline_label')}</label>
				<select id="baseline" bind:value={baselineProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 px-3 py-2 text-sm">
					<option value="">{$t('schedule.baseline_none')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}{p.tags?.length ? ` [${p.tags.slice(0, 3).join(', ')}]` : ''}</option>
					{/each}
				</select>
			</div>
			<div class="min-w-44">
				<label for="groupBy" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('schedule.group_by_label')}</label>
				<select id="groupBy" bind:value={groupBy} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 px-3 py-2 text-sm">
					<option value="wbs">{$t('schedule.group_wbs')}</option>
					<option value="status">{$t('schedule.group_status')}</option>
					<option value="critical">{$t('schedule.group_critical')}</option>
					<option value="task_type">{$t('schedule.group_task_type')}</option>
					<option value="calendar">{$t('schedule.group_calendar')}</option>
					<option value="float_bucket">{$t('schedule.group_float_bucket')}</option>
				</select>
			</div>
			<button onclick={loadSchedule} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? $t('schedule.loading') : $t('schedule.view_button')}
			</button>
			{#if data}
				<button onclick={exportCSV}
					class="px-3 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-md text-sm font-medium hover:bg-gray-200 dark:hover:bg-gray-700">
					{$t('schedule.export_csv')}
				</button>
				<span class="w-px h-6 bg-gray-200 dark:bg-gray-700"></span>
				<a href="/scorecard?project={selectedProject}" class="text-[10px] px-2 py-1.5 rounded bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 hover:bg-amber-100 font-medium">{$t('schedule.nav_scorecard')}</a>
				<a href="/compare" class="text-[10px] px-2 py-1.5 rounded bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 hover:bg-blue-100 font-medium">{$t('schedule.link_compare')}</a>
				<a href="/trends" class="text-[10px] px-2 py-1.5 rounded bg-purple-50 dark:bg-purple-950 text-purple-700 dark:text-purple-300 hover:bg-purple-100 font-medium">{$t('schedule.link_trends')}</a>
			{/if}
		</div>
		{#if data}
			<div class="flex items-center gap-4 mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
				<label class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 cursor-pointer">
					<input type="checkbox" bind:checked={showBaseline} class="w-3.5 h-3.5 rounded" />
					{$t('schedule.show_baseline')}
				</label>
				<label class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 cursor-pointer">
					<input type="checkbox" bind:checked={showFloat} class="w-3.5 h-3.5 rounded" />
					{$t('schedule.show_float')}
				</label>
				<label class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 cursor-pointer">
					<input type="checkbox" bind:checked={showDependencies} class="w-3.5 h-3.5 rounded" />
					{$t('schedule.show_dependencies')}
				</label>
				<label class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 cursor-pointer">
					<input type="checkbox" bind:checked={criticalOnly} class="w-3.5 h-3.5 rounded" />
					{$t('schedule.critical_only')}
				</label>
				<span class="w-px h-4 bg-gray-200 dark:bg-gray-700"></span>
				<select bind:value={statusFilter} class="text-xs rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 px-2 py-0.5">
					<option value="all">{$t('schedule.status_all')}</option>
					<option value="active">{$t('schedule.status_active')}</option>
					<option value="not_started">{$t('schedule.status_not_started')}</option>
					<option value="complete">{$t('schedule.status_complete')}</option>
					<option value="critical">{$t('schedule.status_critical')}</option>
					<option value="near_critical">{$t('schedule.status_near_critical')}</option>
					<option value="negative_float">{$t('schedule.status_negative_float')}</option>
					<option value="milestones">{$t('schedule.status_milestones')}</option>
					<option value="constrained">{$t('schedule.status_constrained')}</option>
				</select>
			</div>
		{/if}
	</div>

	{#if loading}
		<AnalysisSkeleton cards={4} showChart={false} />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6">
			<p class="text-red-700 dark:text-red-300 text-sm">{error}</p>
		</div>
	{/if}

	{#if data}
		<!-- Status filter pills -->
		{#if statusCounts}
		<div class="flex items-center gap-2 mb-4 flex-wrap">
			{#each [
				['schedule.pill_all', 'all', 'bg-gray-600'],
				['schedule.pill_active', 'active', 'bg-blue-500'],
				['schedule.pill_not_started', 'not_started', 'bg-gray-400'],
				['schedule.pill_complete', 'complete', 'bg-green-500'],
				['schedule.pill_critical', 'critical', 'bg-red-500'],
				['schedule.pill_near_crit', 'near_critical', 'bg-orange-400'],
				['schedule.pill_neg_float', 'negative_float', 'bg-red-400'],
				['schedule.pill_milestones', 'milestones', 'bg-amber-500'],
			] as [labelKey, key, color]}
				<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
					<span class="w-2 h-2 rounded-full {color}"></span>
					{$t(labelKey)}: {statusCounts[key as keyof typeof statusCounts]}
				</span>
			{/each}
		</div>
		{/if}

		<!-- Progress bar -->
		<div class="mb-4 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3">
			<div class="flex items-center justify-between mb-1">
				<span class="text-xs font-semibold text-gray-700 dark:text-gray-300">{$t('schedule.overall_progress')}</span>
				<span class="text-xs font-bold {data.summary.complete_pct >= 90 ? 'text-green-600' : data.summary.complete_pct >= 50 ? 'text-blue-600' : 'text-amber-600'}">{data.summary.complete_pct.toFixed(1)}%</span>
			</div>
			<div class="h-2.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
				<div class="h-full rounded-full transition-all bg-gradient-to-r from-blue-500 to-green-500" style="width: {data.summary.complete_pct}%"></div>
			</div>
			<div class="flex justify-between mt-1 text-[9px] text-gray-400">
				<span>{data.project_start}</span>
				<span>{data.project_finish}</span>
			</div>
		</div>

		<!-- Summary cards -->
		<div class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-8 gap-2 mb-4">
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-2.5 text-center">
				<p class="text-lg font-bold text-gray-900 dark:text-gray-100">{data.summary.total_activities.toLocaleString()}</p>
				<p class="text-[9px] text-gray-500 uppercase">{$t('schedule.kpi_activities')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-2.5 text-center">
				<p class="text-lg font-bold text-green-600">{data.summary.complete_pct.toFixed(0)}%</p>
				<p class="text-[9px] text-gray-500 uppercase">{$t('schedule.kpi_complete')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-2.5 text-center">
				<p class="text-lg font-bold text-red-600">{data.summary.critical_count}</p>
				<p class="text-[9px] text-gray-500 uppercase">{$t('schedule.kpi_critical')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-2.5 text-center">
				<p class="text-lg font-bold text-orange-500">{data.summary.near_critical_count || 0}</p>
				<p class="text-[9px] text-gray-500 uppercase">{$t('schedule.kpi_near_crit')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-2.5 text-center">
				<p class="text-lg font-bold text-amber-600">{data.summary.negative_float_count}</p>
				<p class="text-[9px] text-gray-500 uppercase">{$t('schedule.kpi_neg_float')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-2.5 text-center">
				<p class="text-lg font-bold {(data.summary.avg_float_days ?? 0) < 0 ? 'text-red-600' : 'text-blue-600'}">{data.summary.avg_float_days ?? '—'}d</p>
				<p class="text-[9px] text-gray-500 uppercase">{$t('schedule.kpi_avg_float')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-2.5 text-center">
				<p class="text-lg font-bold text-purple-600">{data.summary.constraint_count ?? 0}</p>
				<p class="text-[9px] text-gray-500 uppercase">{$t('schedule.kpi_constraints')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-2.5 text-center">
				<p class="text-lg font-bold text-gray-700 dark:text-gray-300">{data.summary.milestones_count}</p>
				<p class="text-[9px] text-gray-500 uppercase">{$t('schedule.kpi_milestones')}</p>
			</div>
		</div>

		<!-- Float distribution -->
		{#if floatDistribution.length > 0}
			<details class="mb-4">
				<summary class="text-xs text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700">{$t('schedule.float_dist_summary')}</summary>
				<div class="mt-2">
					<BarChart data={floatDistribution} title={$t('schedule.float_dist_title')} height={140} />
				</div>
			</details>
		{/if}

		<!-- Schedule Viewer -->
		<ScheduleViewer
			data={displayData || data} {showFloat} {showBaseline} {showDependencies} {criticalOnly}
			onActivityClick={(taskId) => { selectedActivity = data?.activities.find(a => a.task_id === taskId) || null; }}
		/>

		<!-- Resource Histograms (Wave 7 — as-scheduled demand curves) -->
		{#if selectedProject}
			<ResourceHistogramPanel projectId={selectedProject} />
		{/if}

		<!-- Activity detail panel (click on bar) -->
		{#if selectedActivity}
			{@const a = selectedActivity}
			<div class="mt-4 bg-white dark:bg-gray-900 rounded-lg border border-blue-200 dark:border-blue-800 p-4">
				<div class="flex items-center justify-between mb-3">
					<div>
						<h3 class="text-sm font-bold text-gray-900 dark:text-gray-100">{a.task_code} — {a.task_name}</h3>
						<p class="text-[10px] text-gray-500">{a.wbs_path}</p>
					</div>
					<button onclick={() => selectedActivity = null} aria-label={$t('schedule.close_detail')} class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
					</button>
				</div>
				<div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 text-xs">
					<div>
						<p class="text-gray-500">{$t('schedule.detail_status')}</p>
						<p class="font-semibold capitalize {a.status === 'complete' ? 'text-green-600' : a.status === 'active' ? 'text-blue-600' : 'text-gray-600'}">{a.status}</p>
					</div>
					<div>
						<p class="text-gray-500">{$t('schedule.detail_type')}</p>
						<p class="font-semibold capitalize text-gray-700 dark:text-gray-300">{a.task_type}</p>
					</div>
					<div>
						<p class="text-gray-500">{$t('schedule.detail_duration')}</p>
						<p class="font-semibold text-gray-700 dark:text-gray-300">{a.duration_days}d</p>
					</div>
					<div>
						<p class="text-gray-500">{$t('schedule.detail_remaining')}</p>
						<p class="font-semibold text-gray-700 dark:text-gray-300">{a.remaining_days}d</p>
					</div>
					<div>
						<p class="text-gray-500">{$t('schedule.detail_total_float')}</p>
						<p class="font-semibold {a.total_float_days < 0 ? 'text-red-600' : a.total_float_days === 0 ? 'text-amber-600' : 'text-green-600'}">{a.total_float_days}d</p>
					</div>
					<div>
						<p class="text-gray-500">{$t('schedule.detail_free_float')}</p>
						<p class="font-semibold text-gray-500">{a.free_float_days}d</p>
					</div>
					<div>
						<p class="text-gray-500">{$t('schedule.detail_progress')}</p>
						<div class="flex items-center gap-1.5">
							<div class="w-12 h-1.5 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
								<div class="h-full rounded-full {a.is_critical ? 'bg-red-500' : 'bg-blue-500'}" style="width: {a.progress_pct}%"></div>
							</div>
							<span class="font-semibold text-blue-600">{a.progress_pct}%</span>
						</div>
					</div>
					<div>
						<p class="text-gray-500">{$t('schedule.detail_critical')}</p>
						<p class="font-semibold {a.is_critical ? 'text-red-600' : 'text-gray-400'}">{a.is_critical ? $t('schedule.detail_yes') : $t('schedule.detail_no')}</p>
					</div>
					<div>
						<p class="text-gray-500">{$t('schedule.detail_early_start')}</p>
						<p class="font-semibold text-gray-700 dark:text-gray-300">{a.early_start}</p>
					</div>
					<div>
						<p class="text-gray-500">{$t('schedule.detail_early_finish')}</p>
						<p class="font-semibold text-gray-700 dark:text-gray-300">{a.early_finish}</p>
					</div>
					<div>
						<p class="text-gray-500">{$t('schedule.detail_late_start')}</p>
						<p class="font-semibold text-gray-700 dark:text-gray-300">{a.late_start || '—'}</p>
					</div>
					<div>
						<p class="text-gray-500">{$t('schedule.detail_late_finish')}</p>
						<p class="font-semibold text-gray-700 dark:text-gray-300">{a.late_finish || '—'}</p>
					</div>
					{#if a.actual_start}
						<div>
							<p class="text-gray-500">{$t('schedule.detail_actual_start')}</p>
							<p class="font-semibold text-green-600">{a.actual_start}</p>
						</div>
					{/if}
					{#if a.actual_finish}
						<div>
							<p class="text-gray-500">{$t('schedule.detail_actual_finish')}</p>
							<p class="font-semibold text-green-600">{a.actual_finish}</p>
						</div>
					{/if}
					{#if a.baseline_start}
						<div>
							<p class="text-gray-500">{$t('schedule.detail_baseline_start')}</p>
							<p class="font-semibold text-gray-500">{a.baseline_start}</p>
						</div>
						<div>
							<p class="text-gray-500">{$t('schedule.detail_baseline_finish')}</p>
							<p class="font-semibold text-gray-500">{a.baseline_finish}</p>
						</div>
					{/if}
					{#if a.start_variance_days !== null && a.start_variance_days !== undefined}
						<div>
							<p class="text-gray-500">{$t('schedule.detail_start_variance')}</p>
							<p class="font-semibold {a.start_variance_days > 0 ? 'text-red-600' : a.start_variance_days < 0 ? 'text-green-600' : 'text-gray-500'}">{a.start_variance_days > 0 ? '+' : ''}{a.start_variance_days}d</p>
						</div>
					{/if}
					{#if a.finish_variance_days !== null && a.finish_variance_days !== undefined}
						<div>
							<p class="text-gray-500">{$t('schedule.detail_finish_variance')}</p>
							<p class="font-semibold {a.finish_variance_days > 0 ? 'text-red-600' : a.finish_variance_days < 0 ? 'text-green-600' : 'text-gray-500'}">{a.finish_variance_days > 0 ? '+' : ''}{a.finish_variance_days}d {a.finish_variance_days > 0 ? $t('schedule.detail_late_suffix') : a.finish_variance_days < 0 ? $t('schedule.detail_early_suffix') : ''}</p>
						</div>
					{/if}
					{#if a.constraint_type && a.constraint_type !== 'CS_MEO'}
						<div>
							<p class="text-gray-500">{$t('schedule.detail_constraint')}</p>
							<p class="font-semibold text-purple-600">{a.constraint_type} {a.constraint_date || ''}</p>
						</div>
					{/if}
					<div>
						<p class="text-gray-500">{$t('schedule.detail_calendar')}</p>
						<p class="font-semibold text-gray-500">{a.calendar_id || '—'}</p>
					</div>
				</div>
				<!-- Predecessors/Successors -->
				{#if data}
					{@const preds = data.relationships.filter(r => r.to_id === a.task_id)}
					{@const succs = data.relationships.filter(r => r.from_id === a.task_id)}
					{#if preds.length > 0 || succs.length > 0}
						<div class="grid grid-cols-2 gap-3 mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
							{#if preds.length > 0}
								<div>
									<p class="text-[9px] text-gray-500 mb-1">{$t('schedule.detail_predecessors')} ({preds.length})</p>
									<div class="space-y-0.5">
										{#each preds as rel}
											{@const predAct = data.activities.find(a2 => a2.task_id === rel.from_id)}
											{#if predAct}
												<button type="button" onclick={() => selectedActivity = predAct} class="block w-full text-left text-[9px] text-gray-600 dark:text-gray-400 truncate hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer">
													<span class="font-mono px-1 py-0.5 rounded {rel.is_driving ? 'bg-red-100 text-red-600 dark:bg-red-950 dark:text-red-400' : 'text-gray-400'}">{rel.type}</span>
													{#if rel.lag_days !== 0}<span class="text-amber-500 font-mono">{rel.lag_days > 0 ? '+' : ''}{rel.lag_days}d</span>{/if}
													<span class="font-mono text-gray-400">{predAct.task_code}</span> {predAct.task_name}
												</button>
											{/if}
										{/each}
									</div>
								</div>
							{/if}
							{#if succs.length > 0}
								<div>
									<p class="text-[9px] text-gray-500 mb-1">{$t('schedule.detail_successors')} ({succs.length})</p>
									<div class="space-y-0.5">
										{#each succs as rel}
											{@const succAct = data.activities.find(a2 => a2.task_id === rel.to_id)}
											{#if succAct}
												<button type="button" onclick={() => selectedActivity = succAct} class="block w-full text-left text-[9px] text-gray-600 dark:text-gray-400 truncate hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer">
													<span class="font-mono px-1 py-0.5 rounded {rel.is_driving ? 'bg-red-100 text-red-600 dark:bg-red-950 dark:text-red-400' : 'text-gray-400'}">{rel.type}</span>
													{#if rel.lag_days !== 0}<span class="text-amber-500 font-mono">{rel.lag_days > 0 ? '+' : ''}{rel.lag_days}d</span>{/if}
													<span class="font-mono text-gray-400">{succAct.task_code}</span> {succAct.task_name}
												</button>
											{/if}
										{/each}
									</div>
								</div>
							{/if}
						</div>
					{/if}
				{/if}

				{#if a.alerts.length > 0}
					<div class="mt-3 flex gap-1">
						{#each a.alerts as alert}
							<span class="px-1.5 py-0.5 bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 rounded text-[9px] font-bold">{alert.replace(/_/g, ' ')}</span>
						{/each}
					</div>
				{/if}
				<!-- Mini timeline bar -->
				{#if a.early_start && a.early_finish && data}
					{@const projStart = new Date(data.project_start + 'T00:00:00').getTime()}
					{@const projEnd = new Date(data.project_finish + 'T00:00:00').getTime()}
					{@const projSpan = Math.max(1, projEnd - projStart)}
					{@const actStart = new Date(a.early_start + 'T00:00:00').getTime()}
					{@const actEnd = new Date(a.early_finish + 'T00:00:00').getTime()}
					{@const leftPct = ((actStart - projStart) / projSpan) * 100}
					{@const widthPct = Math.max(0.5, ((actEnd - actStart) / projSpan) * 100)}
					<div class="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
						<p class="text-[9px] text-gray-500 mb-1">{$t('schedule.activity_timeline')}</p>
						<div class="relative h-6 bg-gray-100 dark:bg-gray-800 rounded overflow-hidden">
							{#if a.baseline_start && a.baseline_finish}
								{@const blStart = new Date(a.baseline_start + 'T00:00:00').getTime()}
								{@const blEnd = new Date(a.baseline_finish + 'T00:00:00').getTime()}
								{@const blLeft = ((blStart - projStart) / projSpan) * 100}
								{@const blWidth = Math.max(0.5, ((blEnd - blStart) / projSpan) * 100)}
								<div class="absolute top-4 h-1.5 bg-gray-400 opacity-30 rounded" style="left: {blLeft}%; width: {blWidth}%"></div>
							{/if}
							<div class="absolute top-1 h-3 rounded opacity-30 {a.is_critical ? 'bg-red-500' : 'bg-blue-500'}" style="left: {leftPct}%; width: {widthPct}%"></div>
							<div class="absolute top-1 h-3 rounded {a.is_critical ? 'bg-red-500' : 'bg-blue-500'}" style="left: {leftPct}%; width: {widthPct * Math.min(a.progress_pct / 100, 1)}%"></div>
						</div>
						<div class="flex justify-between mt-0.5 text-[7px] text-gray-400">
							<span>{data.project_start}</span>
							<span>{data.project_finish}</span>
						</div>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Activity data table -->
		<details class="mt-4 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
			<summary class="px-4 py-3 cursor-pointer text-sm font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 flex items-center justify-between">
				<span>{$t('schedule.activity_table')} ({sortedActivities.length}{wbsFilter ? `/${data.activities.length}` : ''} {$t('schedule.activities_suffix')})</span>
				<span class="flex items-center gap-2">
					<select
						onclick={(e: MouseEvent) => e.stopPropagation()}
						bind:value={wbsFilter}
						class="text-[9px] rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 px-1.5 py-0.5 max-w-40"
					>
						<option value="">{$t('schedule.all_wbs')}</option>
						{#each uniqueWbsPaths as path}
							<option value={path}>{path.split('/').pop()}</option>
						{/each}
					</select>
					<button
						type="button"
						onclick={(e: MouseEvent) => { e.stopPropagation(); showColumnConfig = !showColumnConfig; }}
						class="text-[9px] px-2 py-0.5 rounded bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600"
						title={$t('schedule.columns_tooltip')}
					>
						{$t('schedule.columns_button')} ({visibleColumns.length}/{columns.length})
					</button>
				</span>
			</summary>

			<!-- Column config dropdown -->
			{#if showColumnConfig}
				<div class="px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 flex flex-wrap gap-2">
					{#each columns as col}
						<label class="flex items-center gap-1 text-[9px] text-gray-600 dark:text-gray-400 cursor-pointer">
							<input type="checkbox" checked={col.visible} onchange={() => toggleColumn(col.id)} class="w-3 h-3 rounded" />
							{$t(col.labelKey)}
						</label>
					{/each}
				</div>
			{/if}

			<div class="overflow-x-auto overflow-y-auto max-h-96" bind:this={tableContainer} onscroll={handleTableScroll}>
				<table class="w-full text-[10px]">
					<thead class="sticky top-0 bg-gray-50 dark:bg-gray-800 z-10">
						<tr>
							{#each visibleColumns as col}
								<th class="{col.align} py-1.5 px-2 font-semibold text-gray-500 {col.sortKey ? 'cursor-pointer hover:text-gray-700 dark:hover:text-gray-300 select-none' : ''}"
									onclick={() => col.sortKey && toggleSort(col.sortKey)}
								>
									{$t(col.labelKey)}{#if sortCol === col.sortKey}<span class="ml-0.5">{sortAsc ? '▲' : '▼'}</span>{/if}
								</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						<!-- Virtual scrolling spacer -->
						{#if tableVStart > 0}
							<tr><td colspan={visibleColumns.length} style="height: {tableVStart * TABLE_ROW_H}px; padding: 0;"></td></tr>
						{/if}
						{#each tableRenderedRows as act}
							<tr class="border-t border-gray-100 dark:border-gray-800 hover:bg-blue-50 dark:hover:bg-gray-800" style="height: {TABLE_ROW_H}px;">
								{#each visibleColumns as col}
									{#if col.id === 'name'}
										<td class="py-1 px-2 text-gray-900 dark:text-gray-100 truncate max-w-48">{col.render(act)}</td>
									{:else if col.id === 'wbs'}
										<td class="py-1 px-2 text-[8px] text-gray-400 truncate max-w-24" title="{act.wbs_path}">{col.render(act)}</td>
									{:else if col.id === 'status'}
										<td class="py-1 px-2">
											<span class="px-1 py-0.5 rounded text-[8px] font-bold uppercase
												{act.status === 'complete' ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' :
												act.status === 'active' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' :
												'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}">{col.render(act)}</span>
										</td>
									{:else if col.id === 'tf'}
										<td class="py-1 px-2 text-right font-mono {act.total_float_days < 0 ? 'text-red-600 font-bold' : act.total_float_days === 0 ? 'text-amber-600' : 'text-gray-500'}">{col.render(act)}</td>
									{:else if col.id === 'cp'}
										<td class="py-1 px-2 text-center {act.is_critical ? 'text-red-600' : ''}">{col.render(act)}</td>
									{:else if col.id === 'alerts'}
										<td class="py-1 px-2">
											{#each act.alerts as alert}
												<span class="px-1 py-0.5 bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 rounded text-[8px] mr-0.5">{alert.replace('_', ' ')}</span>
											{/each}
										</td>
									{:else if col.id === 'code'}
										<td class="py-1 px-2 font-mono text-gray-500">{col.render(act)}</td>
									{:else if col.align === 'text-right'}
										<td class="py-1 px-2 text-right font-mono text-gray-500">{col.render(act)}</td>
									{:else}
										<td class="py-1 px-2 text-gray-500">{col.render(act)}</td>
									{/if}
								{/each}
							</tr>
						{/each}
						<!-- Bottom spacer -->
						{#if tableVEnd < sortedActivities.length}
							<tr><td colspan={visibleColumns.length} style="height: {(sortedActivities.length - tableVEnd) * TABLE_ROW_H}px; padding: 0;"></td></tr>
						{/if}
					</tbody>
				</table>
			</div>
		</details>
	{/if}
</main>
