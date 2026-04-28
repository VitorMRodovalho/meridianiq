<script lang="ts">
	import { getProjects, getProjectHealth } from '$lib/api';
	import { error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import GaugeChart from '$lib/components/charts/GaugeChart.svelte';
	import type { ScheduleHealthResponse } from '$lib/types';

	let projects: { project_id: string; name: string; activity_count?: number }[] = $state([]);
	let selectedProject = $state('');
	let baselineProject = $state('');
	let result = $state<ScheduleHealthResponse | null>(null);
	let loading = $state(false);
	let error = $state('');

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			const msg = e instanceof Error ? e.message : 'Failed to load projects';
			toastError(`Could not load projects: ${msg}`);
			console.error('loadProjects (health):', e);
		}
	}

	async function analyze() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		result = null;
		try {
			result = await getProjectHealth(selectedProject, baselineProject || undefined);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Analysis failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	function ratingBadge(rating: string): string {
		if (rating === 'excellent') return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300';
		if (rating === 'good') return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300';
		if (rating === 'fair') return 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300';
		return 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300';
	}

	function scoreColor(score: number): string {
		if (score >= 80) return 'text-green-600';
		if (score >= 60) return 'text-amber-600';
		return 'text-red-600';
	}
</script>

<svelte:head>
	<title>{$t('page.health')} | MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.health')}</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">Composite 0-100 score combining DCMA, float, logic, and trend metrics</p>
	</div>

	<!-- Controls -->
	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<div class="flex items-end gap-4 flex-wrap">
			<div class="flex-1 min-w-[200px]">
				<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('common.project')}</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 px-3 py-2 text-sm">
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id} ({p.activity_count} act.)</option>
					{/each}
				</select>
			</div>
			<div class="flex-1 min-w-[200px]">
				<label for="baseline" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Baseline (optional)</label>
				<select id="baseline" bind:value={baselineProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 px-3 py-2 text-sm">
					<option value="">No baseline</option>
					{#each projects.filter(p => p.project_id !== selectedProject) as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<button onclick={analyze} disabled={!selectedProject || loading}
				class="px-6 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Computing...' : 'Compute Health'}
			</button>
			{#if selectedProject}
				<a href="/schedule?project={selectedProject}" class="px-3 py-2 text-xs text-teal-600 hover:text-teal-800 font-medium">View Schedule</a>
			{/if}
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6">
			<p class="text-red-700 dark:text-red-400 text-sm">{error}</p>
		</div>
	{/if}

	{#if result}
		<!-- Overall Score -->
		<div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
			<div class="md:col-span-1 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 text-center">
				<GaugeChart value={result.overall} max={100} label="Overall Health" size={180} />
				<div class="mt-3 flex items-center justify-center gap-2">
					<span class="px-3 py-1 rounded-full text-sm font-bold uppercase {ratingBadge(result.rating)}">{result.rating}</span>
					{#if result.trend_arrow}
						<span class="text-lg">{result.trend_arrow}</span>
					{/if}
				</div>
			</div>

			<!-- Component Scores -->
			<div class="md:col-span-2 grid grid-cols-2 gap-4">
				{#each [
					{ name: 'DCMA Quality', score: result.dcma_component, weight: '35%' },
					{ name: 'Float Health', score: result.float_component, weight: '25%' },
					{ name: 'Logic Integrity', score: result.logic_component, weight: '25%' },
					{ name: 'Trend Direction', score: result.trend_component, weight: '15%' },
				] as comp}
					<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
						<div class="flex items-center justify-between mb-2">
							<p class="text-xs text-gray-500 dark:text-gray-400 uppercase font-medium">{comp.name}</p>
							<span class="text-[10px] text-gray-400">w: {comp.weight}</span>
						</div>
						<p class="text-2xl font-bold {scoreColor(comp.score)}">{comp.score.toFixed(0)}</p>
						<div class="mt-2 h-1.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
							<div class="h-full rounded-full {comp.score >= 80 ? 'bg-green-500' : comp.score >= 60 ? 'bg-amber-500' : 'bg-red-500'}"
								style="width: {Math.min(100, comp.score)}%"></div>
						</div>
					</div>
				{/each}
			</div>
		</div>

		<!-- Details Breakdown -->
		{#if result.details && Object.keys(result.details).length > 0}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Detail Breakdown</h2>
				<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
					{#each Object.entries(result.details) as [key, value]}
						<div class="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
							<p class="text-xs text-gray-500 dark:text-gray-400 capitalize">{key.replace(/_/g, ' ')}</p>
							<p class="text-sm font-bold text-gray-900 dark:text-gray-100 mt-1">
								{typeof value === 'number' ? (value % 1 === 0 ? value : value.toFixed(2)) : value}
							</p>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	{/if}
</main>
