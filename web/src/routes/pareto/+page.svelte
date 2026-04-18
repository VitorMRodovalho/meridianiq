<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import ScatterChart from '$lib/components/charts/ScatterChart.svelte';
	import { supabase } from '$lib/supabase';
	import { onMount } from 'svelte';

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject = $state('');
	let data: ParetoData | null = $state(null);
	let loading = $state(false);
	let error = $state('');

	interface ParetoPoint {
		duration_days: number;
		cost: number;
		is_pareto_optimal: boolean;
		label: string;
	}

	interface ParetoData {
		base_duration_days: number;
		base_cost: number;
		all_points: ParetoPoint[];
		frontier: ParetoPoint[];
		scenarios_evaluated: number;
	}

	onMount(async () => {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			error = e instanceof Error ? e.message : $t('pareto.error_generic');
		}
	});

	async function analyze() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = {
				'Content-Type': 'application/json',
				...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
			};
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/pareto`, {
				method: 'POST',
				headers,
				body: JSON.stringify({}),
			});
			if (!res.ok) throw new Error(await res.text());
			data = await res.json();
			toastSuccess(`${data!.scenarios_evaluated} ${$t('pareto.toast_evaluated')}`);
		} catch (e) {
			error = e instanceof Error ? e.message : $t('pareto.error_generic');
			toastError(error);
		} finally {
			loading = false;
		}
	}

	const chartData = $derived.by(() => {
		if (!data) return [];
		return data.all_points.map(p => ({
			x: p.duration_days,
			y: p.cost,
			label: p.label || `${p.duration_days}d`,
			color: p.is_pareto_optimal ? '#3b82f6' : '#d1d5db',
		}));
	});
</script>

<svelte:head>
	<title>{$t('nav.pareto')} | MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-1">{$t('nav.pareto')}</h1>
	<p class="text-sm text-gray-500 dark:text-gray-400 mb-6">{$t('pareto.subtitle')}</p>

	<div class="flex gap-4 mb-6">
		<div class="flex-1">
			<label for="pareto-schedule" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('pareto.label_schedule')}</label>
			<select id="pareto-schedule" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 px-3 py-2 text-sm">
				<option value="">{$t('pareto.select_schedule')}</option>
				{#each projects as p}
					<option value={p.project_id}>{p.name || p.project_id}</option>
				{/each}
			</select>
		</div>
		<div class="flex items-end">
			<button onclick={analyze} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? $t('pareto.btn_analyzing') : $t('pareto.btn_run')}
			</button>
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm">{error}</div>
	{:else if data}
		<!-- Summary -->
		<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{data.base_duration_days}d</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">{$t('pareto.stat_base_duration')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-blue-600">{data.frontier.length}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">{$t('pareto.stat_optimal_points')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-gray-700 dark:text-gray-300">{data.scenarios_evaluated}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">{$t('pareto.stat_scenarios')}</p>
			</div>
		</div>

		<!-- Chart -->
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 mb-6">
			<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{$t('pareto.chart_title')}</h3>
			{#if chartData.length > 0}
				<ScatterChart data={chartData} xLabel={$t('pareto.chart_x')} yLabel={$t('pareto.chart_y')} height={300} />
			{:else}
				<p class="text-sm text-gray-400 text-center py-8">{$t('pareto.no_points')}</p>
			{/if}
		</div>

		<!-- Frontier table -->
		{#if data.frontier.length > 0}
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
				<div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
					<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">{$t('pareto.frontier_title')}</h3>
				</div>
				<table class="w-full text-sm">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="text-left py-2 px-4 text-gray-500 dark:text-gray-400">{$t('pareto.col_scenario')}</th>
							<th class="text-right py-2 px-4 text-gray-500 dark:text-gray-400">{$t('pareto.col_duration')}</th>
							<th class="text-right py-2 px-4 text-gray-500 dark:text-gray-400">{$t('pareto.col_cost')}</th>
							<th class="text-right py-2 px-4 text-gray-500 dark:text-gray-400">{$t('pareto.col_duration_saved')}</th>
						</tr>
					</thead>
					<tbody>
						{#each data.frontier as point, i}
							<tr class="border-t border-gray-100 dark:border-gray-800">
								<td class="py-2 px-4 text-gray-900 dark:text-gray-100">{point.label || `${$t('pareto.col_scenario')} ${i + 1}`}</td>
								<td class="py-2 px-4 text-right font-mono text-gray-700 dark:text-gray-300">{point.duration_days}d</td>
								<td class="py-2 px-4 text-right font-mono text-gray-700 dark:text-gray-300">${(point.cost / 1e6).toFixed(1)}M</td>
								<td class="py-2 px-4 text-right font-mono text-green-600">{data.base_duration_days - point.duration_days}d</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{:else}
		<div class="text-center py-12 text-gray-400 dark:text-gray-600">
			<p class="text-lg mb-2">{$t('pareto.empty_title')}</p>
			<p class="text-sm">{$t('pareto.empty_hint')}</p>
		</div>
	{/if}
</main>
