<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';
	import TimelineChart from '$lib/components/charts/TimelineChart.svelte';
	import { supabase } from '$lib/supabase';
	import { onMount } from 'svelte';

	let projects: { project_id: string; name: string; tags?: string[] }[] = $state([]);
	let selectedIds: string[] = $state([]);
	let data: TrendData | null = $state(null);
	let loading = $state(false);
	let error = $state('');

	interface TrendPoint {
		project_id: string;
		project_name: string;
		data_date: string;
		update_number: number | null;
		activity_count: number;
		relationship_count: number;
		wbs_count: number;
		milestone_count: number;
		complete_count: number;
		active_count: number;
		not_started_count: number;
		complete_pct: number;
		avg_total_float: number;
		negative_float_count: number;
		zero_float_count: number;
		critical_count: number;
		near_critical_count: number;
		logic_density: number;
		constraint_count: number;
		loe_count: number;
		project_duration_days: number;
		quality_score: number | null;
		quality_grade: string | null;
	}

	interface TrendData {
		series_name: string;
		point_count: number;
		insights: string[];
		points: TrendPoint[];
	}

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			error = e instanceof Error ? e.message : $t('trends.load_failed');
		}
	}

	onMount(loadProjects);

	function toggleProject(pid: string) {
		if (selectedIds.includes(pid)) {
			selectedIds = selectedIds.filter(id => id !== pid);
		} else {
			selectedIds = [...selectedIds, pid];
		}
	}

	function selectAll() {
		selectedIds = projects.map(p => p.project_id);
	}

	function clearSelection() {
		selectedIds = [];
		data = null;
	}

	async function analyze() {
		if (selectedIds.length < 2) {
			toastError($t('trends.toast_need_two'));
			return;
		}
		loading = true;
		error = '';
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = {
				'Content-Type': 'application/json',
				...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
			};
			const res = await fetch(`${BASE}/api/v1/trends`, {
				method: 'POST',
				headers,
				body: JSON.stringify({ project_ids: selectedIds, include_scorecard: true }),
			});
			if (!res.ok) throw new Error(await res.text());
			data = await res.json();
			toastSuccess(`${$t('trends.toast_analyzed_prefix')} ${data!.point_count} ${$t('trends.toast_analyzed_suffix')}`);
		} catch (e) {
			error = e instanceof Error ? e.message : $t('trends.analyze_failed');
			toastError(error);
		} finally {
			loading = false;
		}
	}

	// Chart data derivations
	function toLabel(p: TrendPoint): string {
		return p.update_number ? `UP ${p.update_number}` : p.data_date.slice(0, 7);
	}

	function chartFrom(fn: (p: TrendPoint) => number): { label: string; value: number }[] {
		if (!data) return [];
		return data.points.map(p => ({ label: toLabel(p), value: fn(p) }));
	}

	const activityChart = $derived(chartFrom(p => p.activity_count));
	const completionChart = $derived(chartFrom(p => Math.round(p.complete_pct * 10) / 10));
	const floatChart = $derived(chartFrom(p => Math.round(p.avg_total_float)));
	const criticalChart = $derived(chartFrom(p => p.critical_count));
	const negFloatChart = $derived(chartFrom(p => p.negative_float_count));
	const logicDensityChart = $derived(chartFrom(p => Math.round(p.logic_density * 100) / 100));
	const qualityChart = $derived(chartFrom(p => p.quality_score ?? 0));
</script>

<svelte:head>
	<title>{$t('nav.trends')} | MeridianIQ</title>
</svelte:head>

<main class="max-w-7xl mx-auto px-4 py-8">
	<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-1">{$t('nav.trends')}</h1>
	<p class="text-sm text-gray-500 dark:text-gray-400 mb-6">{$t('trends.subtitle')}</p>

	<!-- Project selector -->
	<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 mb-6">
		<div class="flex items-center justify-between mb-3">
			<h2 class="text-sm font-semibold text-gray-700 dark:text-gray-300">{$t('trends.select_title')} ({selectedIds.length} {$t('trends.selected_suffix')})</h2>
			<div class="flex gap-2">
				<button onclick={selectAll} class="text-[10px] px-2 py-1 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200">{$t('trends.btn_select_all')}</button>
				<button onclick={clearSelection} class="text-[10px] px-2 py-1 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200">{$t('trends.btn_clear')}</button>
				<button onclick={analyze} disabled={selectedIds.length < 2 || loading}
					class="text-[10px] px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 font-medium">
					{loading ? $t('trends.btn_analyzing') : $t('trends.btn_analyze')}
				</button>
			</div>
		</div>
		<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-1.5 max-h-48 overflow-y-auto">
			{#each projects as p}
				<label class="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-[10px] hover:bg-gray-50 dark:hover:bg-gray-800 {selectedIds.includes(p.project_id) ? 'bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800' : 'border border-transparent'}">
					<input type="checkbox" checked={selectedIds.includes(p.project_id)} onchange={() => toggleProject(p.project_id)} class="w-3 h-3 rounded" />
					<span class="truncate text-gray-700 dark:text-gray-300">{p.name || p.project_id}</span>
					{#if p.tags?.length}
						<span class="ml-auto shrink-0 text-[8px] text-gray-400">{p.tags.slice(0, 2).join(' ')}</span>
					{/if}
				</label>
			{/each}
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm">{error}</div>
	{:else if data}
		<!-- Insights -->
		{#if data.insights.length > 0}
			<div class="bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-lg p-4 mb-6">
				<h3 class="text-sm font-semibold text-amber-800 dark:text-amber-300 mb-2">{$t('trends.insights_title')} — {data.series_name}</h3>
				<ul class="space-y-1">
					{#each data.insights as insight}
						<li class="text-xs text-amber-700 dark:text-amber-400 flex items-start gap-2">
							<span class="shrink-0 mt-0.5 w-1.5 h-1.5 rounded-full bg-amber-500"></span>
							{insight}
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		<!-- Charts grid -->
		<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
			<!-- Activity Count -->
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{$t('trends.chart_activity')}</h3>
				<BarChart data={activityChart} height={200}/>
			</div>

			<!-- Completion % -->
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{$t('trends.chart_completion')}</h3>
				<BarChart data={completionChart} height={200}/>
			</div>

			<!-- Average Float -->
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{$t('trends.chart_float')}</h3>
				<BarChart data={floatChart} height={200}/>
			</div>

			<!-- Critical Count -->
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{$t('trends.chart_critical')}</h3>
				<BarChart data={criticalChart} height={200}/>
			</div>

			<!-- Negative Float -->
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{$t('trends.chart_neg_float')}</h3>
				<BarChart data={negFloatChart} height={200}/>
			</div>

			<!-- Logic Density -->
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{$t('trends.chart_logic_density')}</h3>
				<BarChart data={logicDensityChart} height={200}/>
			</div>

			<!-- Quality Score -->
			{#if qualityChart.some(d => d.value > 0)}
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
					<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{$t('trends.chart_quality')}</h3>
					<BarChart data={qualityChart} height={200}/>
				</div>
			{/if}
		</div>

		<!-- Data table -->
		<details class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg">
			<summary class="px-4 py-3 cursor-pointer text-sm font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
				{$t('trends.data_title')} ({data.point_count} {$t('trends.data_updates_suffix')})
			</summary>
			<div class="overflow-x-auto">
				<table class="w-full text-[10px]">
					<thead class="sticky top-0 bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="text-left py-1.5 px-2 font-semibold text-gray-500">{$t('trends.col_update')}</th>
							<th class="text-left py-1.5 px-2 font-semibold text-gray-500">{$t('trends.col_data_date')}</th>
							<th class="text-right py-1.5 px-2 font-semibold text-gray-500">{$t('trends.col_acts')}</th>
							<th class="text-right py-1.5 px-2 font-semibold text-gray-500">{$t('trends.col_rels')}</th>
							<th class="text-right py-1.5 px-2 font-semibold text-gray-500">{$t('trends.col_wbs')}</th>
							<th class="text-right py-1.5 px-2 font-semibold text-gray-500">{$t('trends.col_done_pct')}</th>
							<th class="text-right py-1.5 px-2 font-semibold text-gray-500">{$t('trends.col_avg_tf')}</th>
							<th class="text-right py-1.5 px-2 font-semibold text-gray-500">{$t('trends.col_cp')}</th>
							<th class="text-right py-1.5 px-2 font-semibold text-gray-500">{$t('trends.col_neg_tf')}</th>
							<th class="text-right py-1.5 px-2 font-semibold text-gray-500">{$t('trends.col_near_cp')}</th>
							<th class="text-right py-1.5 px-2 font-semibold text-gray-500">{$t('trends.col_density')}</th>
							<th class="text-right py-1.5 px-2 font-semibold text-gray-500">{$t('trends.col_score')}</th>
						</tr>
					</thead>
					<tbody>
						{#each data.points as p}
							<tr class="border-t border-gray-100 dark:border-gray-800 hover:bg-blue-50 dark:hover:bg-gray-800">
								<td class="py-1 px-2 font-mono">{p.update_number ? `UP ${String(p.update_number).padStart(2, '0')}` : '—'}</td>
								<td class="py-1 px-2 text-gray-500">{p.data_date}</td>
								<td class="py-1 px-2 text-right font-mono">{p.activity_count.toLocaleString()}</td>
								<td class="py-1 px-2 text-right font-mono text-gray-400">{p.relationship_count.toLocaleString()}</td>
								<td class="py-1 px-2 text-right font-mono text-gray-400">{p.wbs_count}</td>
								<td class="py-1 px-2 text-right font-mono text-green-600">{p.complete_pct}%</td>
								<td class="py-1 px-2 text-right font-mono {p.avg_total_float < 0 ? 'text-red-600' : 'text-gray-500'}">{p.avg_total_float}d</td>
								<td class="py-1 px-2 text-right font-mono text-red-500">{p.critical_count}</td>
								<td class="py-1 px-2 text-right font-mono {p.negative_float_count > 0 ? 'text-red-600 font-bold' : 'text-gray-400'}">{p.negative_float_count}</td>
								<td class="py-1 px-2 text-right font-mono text-amber-500">{p.near_critical_count}</td>
								<td class="py-1 px-2 text-right font-mono text-gray-400">{p.logic_density}</td>
								<td class="py-1 px-2 text-right font-mono {(p.quality_score ?? 0) >= 70 ? 'text-green-600' : (p.quality_score ?? 0) >= 50 ? 'text-amber-600' : 'text-red-600'}">{p.quality_score != null ? `${p.quality_score.toFixed(0)} ${p.quality_grade || ''}` : '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</details>
	{:else}
		<div class="text-center py-12 text-gray-400 dark:text-gray-600">
			<p class="text-lg mb-2">{$t('trends.empty_title')}</p>
			<p class="text-sm">{$t('trends.empty_hint')}</p>
		</div>
	{/if}
</main>
