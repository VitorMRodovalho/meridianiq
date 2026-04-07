<script lang="ts">
	import { getProjects, getVisualization } from '$lib/api';
	import type { VisualizationResponse } from '$lib/types';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let viz = $state<VisualizationResponse | null>(null);
	let loading: boolean = $state(false);
	let error: string = $state('');

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load projects';
		}
	}

	async function loadViz() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		viz = null;
		try {
			viz = await getVisualization(selectedProject);
			toastSuccess(`Loaded: ${viz.total_activities} activities`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load visualization';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	const colorMap: Record<string, string> = {
		critical: '#ef4444',
		active: '#3b82f6',
		complete: '#10b981',
		not_started: '#9ca3af',
		high_float: '#a78bfa',
	};

	const svgWidth = 900;
	const svgPadding = { left: 120, right: 20, top: 30, bottom: 20 };
	const rowHeight = 18;
	const barHeight = 12;

	const chartWidth = $derived(svgWidth - svgPadding.left - svgPadding.right);

	const actCount = $derived(viz ? viz.activities.length : 0);
	const svgHeight = $derived(svgPadding.top + actCount * rowHeight + svgPadding.bottom);

	function xScale(d: number): number {
		if (viz && viz.project_duration_days > 0) {
			return svgPadding.left + (d / viz.project_duration_days) * chartWidth;
		}
		return svgPadding.left;
	}
</script>

<svelte:head>
	<title>4D Visualization - MeridianIQ</title>
</svelte:head>

<main class="max-w-7xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">4D Visualization</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">WBS spatial grouping x CPM temporal positioning</p>
	</div>

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<div class="flex items-end gap-4">
			<div class="flex-1">
				<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Select Project</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm">
					<option value="">Choose a project...</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<button onclick={loadViz} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Loading...' : 'Visualize'}
			</button>
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 mb-6">
			<p class="text-red-700 text-sm">{error}</p>
		</div>
	{/if}

	{#if viz}
		<!-- Legend -->
		<div class="flex items-center gap-4 mb-4 text-xs">
			{#each Object.entries(colorMap) as [cat, color]}
				<div class="flex items-center gap-1.5">
					<span class="w-3 h-3 rounded" style="background-color: {color}"></span>
					<span class="text-gray-600 dark:text-gray-400 capitalize">{cat.replace('_', ' ')}</span>
				</div>
			{/each}
			<div class="ml-auto text-gray-500 dark:text-gray-400">
				{viz.total_activities} activities | {viz.critical_count} critical | {viz.project_duration_days}d duration
			</div>
		</div>

		<!-- 4D Chart -->
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 overflow-x-auto">
			<svg viewBox="0 0 {svgWidth} {svgHeight}" class="w-full" style="min-width: 700px;">
				<!-- Time axis -->
				{#each [0, 0.25, 0.5, 0.75, 1] as pct}
					<line
						x1={xScale(pct * (viz.project_duration_days || 1))}
						y1={svgPadding.top - 5}
						x2={xScale(pct * (viz.project_duration_days || 1))}
						y2={svgHeight - svgPadding.bottom}
						stroke="#e5e7eb"
						stroke-width="1"
					/>
					<text
						x={xScale(pct * (viz.project_duration_days || 1))}
						y={svgPadding.top - 10}
						text-anchor="middle"
						class="text-[9px] fill-gray-400"
					>
						D{Math.round(pct * (viz.project_duration_days || 0))}
					</text>
				{/each}

				<!-- Activity bars -->
				{#each viz.activities as act, i}
					{@const y = svgPadding.top + i * rowHeight}
					{@const x1 = xScale(act.early_start)}
					{@const w = Math.max(2, xScale(act.early_finish) - xScale(act.early_start))}
					{@const fill = colorMap[act.color_category] || '#9ca3af'}

					<!-- Label -->
					<text
						x={svgPadding.left - 5}
						y={y + barHeight / 2 + 3}
						text-anchor="end"
						class="text-[8px] fill-gray-500"
					>
						{act.task_code.slice(0, 12)}
					</text>

					<!-- Bar -->
					<rect
						{x1}
						x={x1}
						{y}
						width={w}
						height={barHeight}
						rx="2"
						{fill}
						opacity="0.85"
					>
						<title>{act.task_name} | {act.duration_days}d | {act.color_category}</title>
					</rect>
				{/each}
			</svg>
		</div>

		<!-- WBS Groups -->
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mt-6">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">WBS Groups</h2>
			<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
				{#each viz.wbs_groups as group}
					<div class="border border-gray-100 rounded-md p-3">
						<p class="font-mono text-xs text-gray-500 dark:text-gray-400">{group.wbs_id}</p>
						<p class="font-medium text-sm text-gray-900 dark:text-gray-100">{group.wbs_name}</p>
						<p class="text-xs text-gray-400">{group.activity_count} activities</p>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</main>
