<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { supabase } from '$lib/supabase';
	import ScatterChart from '$lib/components/charts/ScatterChart.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';

	interface Anomaly {
		activity_id: string;
		activity_name: string;
		anomaly_type: string;
		severity: string;
		value: number;
		expected_range: { low: number; high: number };
		z_score: number;
		description: string;
	}

	interface AnomalyResult {
		total_activities: number;
		anomalies: Anomaly[];
		summary: Record<string, number>;
		methodology: string;
	}

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let result = $state<AnomalyResult | null>(null);
	let loading: boolean = $state(false);
	let error: string = $state('');

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load projects';
			toastError(`Could not load projects: ${error}`);
			console.error('loadProjects (anomalies):', e);
		}
	}

	async function analyze() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		result = null;
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = session?.access_token
				? { Authorization: `Bearer ${session.access_token}` }
				: {};
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/anomalies`, { headers });
			if (!res.ok) throw new Error(await res.text());
			result = await res.json();
			toastSuccess(`Found ${result!.anomalies.length} anomalies in ${result!.total_activities} activities`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	const severityColor = (s: string) => {
		if (s === 'high') return 'bg-red-100 text-red-800';
		if (s === 'medium') return 'bg-amber-100 text-amber-800';
		return 'bg-green-100 text-green-800';
	};

	const scatterData = $derived(
		result ? result.anomalies.map(a => ({
			x: a.value,
			y: Math.abs(a.z_score),
			label: a.activity_name || a.activity_id,
		})) : []
	);

	const typeCounts = $derived(
		result ? Object.entries(result.summary).map(([label, value]) => ({ label, value })) : []
	);
</script>

<svelte:head>
	<title>{$t('page.anomalies')} - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.anomalies')}</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">{$t('anomalies.subtitle')}</p>
	</div>

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<div class="flex items-end gap-4">
			<div class="flex-1">
				<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('common.project')}</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm">
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<button onclick={analyze} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? $t('anomalies.scanning') : $t('anomalies.detect_button')}
			</button>
			{#if selectedProject}
				<a href="/schedule?project={selectedProject}" class="px-3 py-2 text-xs text-teal-600 hover:text-teal-800 font-medium">{$t('common.view_schedule')}</a>
			{/if}
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 mb-6">
			<p class="text-red-700 text-sm">{error}</p>
		</div>
	{/if}

	{#if result}
		<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-gray-900 dark:text-gray-100">{result.total_activities}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('anomalies.kpi_activities_scanned')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-red-600">{result.anomalies.length}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('anomalies.kpi_anomalies_found')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-amber-600">{result.anomalies.filter(a => a.severity === 'high').length}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('anomalies.kpi_high_severity')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-blue-600">{Object.keys(result.summary).length}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('anomalies.kpi_anomaly_types')}</p>
			</div>
		</div>

		{#if result.anomalies.length > 0}
			<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
				<ScatterChart
					data={scatterData}
					title={$t('anomalies.scatter_chart_title')}
					xLabel={$t('anomalies.scatter_x_label')}
					yLabel={$t('anomalies.scatter_y_label')}
				/>
				<BarChart
					data={typeCounts}
					title={$t('anomalies.bar_chart_title')}
				/>
			</div>

			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">{$t('anomalies.table_heading')} ({result.anomalies.length})</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-200 dark:border-gray-700">
								<th class="text-left py-2 px-3">{$t('anomalies.col_activity')}</th>
								<th class="text-left py-2 px-3">{$t('anomalies.col_type')}</th>
								<th class="text-left py-2 px-3">{$t('anomalies.col_severity')}</th>
								<th class="text-right py-2 px-3">{$t('anomalies.col_value')}</th>
								<th class="text-right py-2 px-3">{$t('anomalies.col_z_score')}</th>
								<th class="text-left py-2 px-3">{$t('anomalies.col_description')}</th>
							</tr>
						</thead>
						<tbody>
							{#each result.anomalies as a}
								<tr class="border-b border-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="py-2 px-3 font-mono text-xs">{a.activity_name || a.activity_id}</td>
									<td class="py-2 px-3 capitalize">{a.anomaly_type}</td>
									<td class="py-2 px-3">
										<span class="px-2 py-0.5 rounded text-xs font-medium {severityColor(a.severity)}">{a.severity}</span>
									</td>
									<td class="py-2 px-3 text-right font-mono">{a.value.toFixed(1)}</td>
									<td class="py-2 px-3 text-right font-mono">{a.z_score.toFixed(2)}</td>
									<td class="py-2 px-3 text-gray-600 dark:text-gray-400 text-xs">{a.description}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<p class="text-xs text-gray-400 mt-3">{result.methodology}</p>
			</div>
		{/if}
	{/if}
</main>
