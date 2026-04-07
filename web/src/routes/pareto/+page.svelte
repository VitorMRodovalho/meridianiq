<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
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
			error = e instanceof Error ? e.message : 'Failed';
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
			toastSuccess(`Evaluated ${data!.scenarios_evaluated} scenarios`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
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
	<title>Pareto Analysis | MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-1">Pareto Analysis</h1>
	<p class="text-sm text-gray-500 dark:text-gray-400 mb-6">Cost-duration trade-off frontier — find optimal schedule compression scenarios</p>

	<div class="flex gap-4 mb-6">
		<div class="flex-1">
			<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Schedule</label>
			<select bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 px-3 py-2 text-sm">
				<option value="">Select schedule...</option>
				{#each projects as p}
					<option value={p.project_id}>{p.name || p.project_id}</option>
				{/each}
			</select>
		</div>
		<div class="flex items-end">
			<button onclick={analyze} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Analyzing...' : 'Run Pareto'}
			</button>
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm">{error}</div>
	{:else if data}
		<!-- Summary -->
		<div class="grid grid-cols-3 gap-4 mb-6">
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{data.base_duration_days}d</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">Base Duration</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-blue-600">{data.frontier.length}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">Pareto-Optimal Points</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-gray-700 dark:text-gray-300">{data.scenarios_evaluated}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">Scenarios Evaluated</p>
			</div>
		</div>

		<!-- Chart -->
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 mb-6">
			<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Cost vs Duration Frontier</h3>
			{#if chartData.length > 0}
				<ScatterChart data={chartData} xLabel="Duration (days)" yLabel="Cost" height={300} />
			{:else}
				<p class="text-sm text-gray-400 text-center py-8">No data points to display</p>
			{/if}
		</div>

		<!-- Frontier table -->
		{#if data.frontier.length > 0}
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
				<div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
					<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Pareto Frontier Points</h3>
				</div>
				<table class="w-full text-sm">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="text-left py-2 px-4 text-gray-500 dark:text-gray-400">Scenario</th>
							<th class="text-right py-2 px-4 text-gray-500 dark:text-gray-400">Duration</th>
							<th class="text-right py-2 px-4 text-gray-500 dark:text-gray-400">Cost</th>
							<th class="text-right py-2 px-4 text-gray-500 dark:text-gray-400">Duration Saved</th>
						</tr>
					</thead>
					<tbody>
						{#each data.frontier as point, i}
							<tr class="border-t border-gray-100 dark:border-gray-800">
								<td class="py-2 px-4 text-gray-900 dark:text-gray-100">{point.label || `Scenario ${i + 1}`}</td>
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
			<p class="text-lg mb-2">Select a schedule to run Pareto analysis</p>
			<p class="text-sm">Evaluates cost-duration trade-offs for schedule compression</p>
		</div>
	{/if}
</main>
