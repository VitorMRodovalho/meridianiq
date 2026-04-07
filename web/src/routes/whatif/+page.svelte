<script lang="ts">
	import { getProjects, runWhatIf } from '$lib/api';
	import type { WhatIfResponse, DurationAdjustment } from '$lib/types';
	import BarChart from '$lib/components/charts/BarChart.svelte';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let result: WhatIfResponse | null = $state(null);
	let loading: boolean = $state(false);
	let error: string = $state('');

	// Scenario config
	let scenarioName: string = $state('Scenario 1');
	let targetCode: string = $state('*');
	let pctChange: number = $state(20);
	let useProbabilistic: boolean = $state(false);
	let iterations: number = $state(50);
	let minPct: number = $state(-10);
	let maxPct: number = $state(30);

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load projects';
		}
	}

	async function runScenario() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		result = null;
		try {
			const adj: DurationAdjustment = {
				target: targetCode,
				pct_change: pctChange / 100,
			};
			if (useProbabilistic) {
				adj.min_pct = minPct / 100;
				adj.max_pct = maxPct / 100;
			}
			result = await runWhatIf(
				selectedProject,
				scenarioName,
				[adj],
				useProbabilistic ? iterations : 1
			);
			toastSuccess(`Scenario complete: ${result.delta_days > 0 ? '+' : ''}${result.delta_days}d`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Scenario failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadProjects();
	});

	const histogramData = $derived(() => {
		if (!result || !result.distribution || result.distribution.length === 0) return [];
		const bins = 10;
		const vals = result.distribution;
		const vmin = Math.min(...vals);
		const vmax = Math.max(...vals);
		const step = (vmax - vmin) / bins || 1;
		const counts: number[] = Array(bins).fill(0);
		vals.forEach((v: number) => {
			const i = Math.min(Math.floor((v - vmin) / step), bins - 1);
			counts[i]++;
		});
		return counts.map((c: number, i: number) => ({
			label: `${(vmin + i * step).toFixed(0)}d`,
			value: c,
		}));
	});
</script>

<svelte:head>
	<title>What-If Simulator - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">What-If Simulator</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">Explore schedule scenarios with CPM re-analysis</p>
	</div>

	<!-- Config -->
	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
			<div>
				<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('common.project')}</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm">
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<div>
				<label for="target" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Target</label>
				<input id="target" bind:value={targetCode} placeholder="* or task_code or WBS:1.2" class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
			<div>
				<label for="pct" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Adjustment (%)</label>
				<input id="pct" type="number" bind:value={pctChange} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
		</div>

		<div class="mt-4 flex items-center gap-4">
			<label class="flex items-center gap-2 text-sm">
				<input type="checkbox" bind:checked={useProbabilistic} class="rounded" />
				Probabilistic mode
			</label>
			{#if useProbabilistic}
				<div class="flex items-center gap-2">
					<input type="number" bind:value={minPct} class="w-20 rounded-md border border-gray-300 dark:border-gray-600 px-2 py-1 text-sm" />
					<span class="text-sm text-gray-500 dark:text-gray-400">to</span>
					<input type="number" bind:value={maxPct} class="w-20 rounded-md border border-gray-300 dark:border-gray-600 px-2 py-1 text-sm" />
					<span class="text-sm text-gray-500 dark:text-gray-400">% range,</span>
					<input type="number" bind:value={iterations} class="w-20 rounded-md border border-gray-300 dark:border-gray-600 px-2 py-1 text-sm" />
					<span class="text-sm text-gray-500 dark:text-gray-400">iterations</span>
				</div>
			{/if}
		</div>

		<div class="mt-4">
			<button
				onclick={runScenario}
				disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
			>
				{loading ? 'Running...' : 'Run Scenario'}
			</button>
			{#if selectedProject}
				<a href="/schedule?project={selectedProject}" class="px-3 py-2 text-xs text-teal-600 hover:text-teal-800 font-medium">View Schedule</a>
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
		<!-- Summary Cards -->
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Base Duration</p>
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{result.base_duration_days}d</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Adjusted Duration</p>
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{result.adjusted_duration_days}d</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Delta</p>
				<p class="text-2xl font-bold {result.delta_days > 0 ? 'text-red-600' : result.delta_days < 0 ? 'text-green-600' : 'text-gray-600 dark:text-gray-400'}">
					{result.delta_days > 0 ? '+' : ''}{result.delta_days}d ({result.delta_pct}%)
				</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Critical Path</p>
				<p class="text-2xl font-bold {result.critical_path_changed ? 'text-amber-600' : 'text-green-600'}">
					{result.critical_path_changed ? 'Changed' : 'Unchanged'}
				</p>
			</div>
		</div>

		<!-- P-values (probabilistic) -->
		{#if Object.keys(result.p_values).length > 0}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">P-Value Distribution ({result.iterations} iterations)</h2>
				<div class="grid grid-cols-4 md:grid-cols-7 gap-3">
					{#each Object.entries(result.p_values) as [p, val]}
						<div class="text-center">
							<p class="text-xs text-gray-500 dark:text-gray-400">P{p}</p>
							<p class="text-lg font-bold text-gray-900 dark:text-gray-100">{val}d</p>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Histogram (probabilistic) -->
		{#if histogramData().length > 0}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
				<BarChart data={histogramData()} title="Duration Distribution" height={200} />
			</div>
		{/if}

		<!-- Activity Impacts -->
		{#if result.activity_impacts.length > 0}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Activity Impacts (top 20)</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-200 dark:border-gray-700">
								<th class="text-left py-2 px-3">Code</th>
								<th class="text-left py-2 px-3">Name</th>
								<th class="text-right py-2 px-3">Original</th>
								<th class="text-right py-2 px-3">Adjusted</th>
								<th class="text-right py-2 px-3">Delta</th>
								<th class="text-center py-2 px-3">CP</th>
							</tr>
						</thead>
						<tbody>
							{#each result.activity_impacts.slice(0, 20) as impact}
								<tr class="border-b border-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="py-2 px-3 font-mono text-xs">{impact.task_code}</td>
									<td class="py-2 px-3">{impact.task_name}</td>
									<td class="py-2 px-3 text-right">{impact.original_duration_days.toFixed(1)}d</td>
									<td class="py-2 px-3 text-right">{impact.adjusted_duration_days.toFixed(1)}d</td>
									<td class="py-2 px-3 text-right {impact.delta_days > 0 ? 'text-red-600' : impact.delta_days < 0 ? 'text-green-600' : ''}">
										{impact.delta_days > 0 ? '+' : ''}{impact.delta_days.toFixed(1)}d
									</td>
									<td class="py-2 px-3 text-center">
										{#if impact.is_critical}
											<span class="text-red-600 font-bold">CP</span>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	{/if}
</main>
