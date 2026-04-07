<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { supabase } from '$lib/supabase';
	import ScheduleViewer from '$lib/components/ScheduleViewer/ScheduleViewer.svelte';
	import type { ScheduleViewData } from '$lib/components/ScheduleViewer/types';

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let baselineProject: string = $state('');
	let data = $state<ScheduleViewData | null>(null);
	let loading: boolean = $state(false);
	let error: string = $state('');
	let showFloat: boolean = $state(true);
	let showBaseline: boolean = $state(true);
	let showDependencies: boolean = $state(false);
	let criticalOnly: boolean = $state(false);

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
			const params = baselineProject ? `?baseline_id=${baselineProject}` : '';
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

	$effect(() => { loadProjects(); });
</script>

<svelte:head>
	<title>Schedule Viewer - MeridianIQ</title>
</svelte:head>

<main class="max-w-[1400px] mx-auto px-4 py-6">
	<div class="mb-6">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Schedule Viewer</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">Interactive Gantt chart with WBS hierarchy, progress bars, and critical path</p>
	</div>

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-6">
		<div class="flex items-end gap-4 flex-wrap">
			<div class="flex-1 min-w-48">
				<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('common.project')}</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 px-3 py-2 text-sm">
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<div class="flex-1 min-w-48">
				<label for="baseline" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Baseline (optional)</label>
				<select id="baseline" bind:value={baselineProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 px-3 py-2 text-sm">
					<option value="">None</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<button onclick={loadSchedule} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Loading...' : 'View Schedule'}
			</button>
		</div>
		{#if data}
			<div class="flex items-center gap-4 mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
				<label class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 cursor-pointer">
					<input type="checkbox" bind:checked={showBaseline} class="w-3.5 h-3.5 rounded" />
					Show Baseline
				</label>
				<label class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 cursor-pointer">
					<input type="checkbox" bind:checked={showFloat} class="w-3.5 h-3.5 rounded" />
					Show Float
				</label>
				<label class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 cursor-pointer">
					<input type="checkbox" bind:checked={showDependencies} class="w-3.5 h-3.5 rounded" />
					Dependencies
				</label>
				<label class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 cursor-pointer">
					<input type="checkbox" bind:checked={criticalOnly} class="w-3.5 h-3.5 rounded" />
					Critical Path Only
				</label>
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
		<!-- Summary cards -->
		<div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-gray-900 dark:text-gray-100">{data.summary.total_activities}</p>
				<p class="text-xs text-gray-500 uppercase">Activities</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-red-600">{data.summary.critical_count}</p>
				<p class="text-xs text-gray-500 uppercase">Critical</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-green-600">{data.summary.complete_pct.toFixed(0)}%</p>
				<p class="text-xs text-gray-500 uppercase">Complete</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-amber-600">{data.summary.negative_float_count}</p>
				<p class="text-xs text-gray-500 uppercase">Neg. Float</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-gray-700 dark:text-gray-300">{data.summary.milestones_count}</p>
				<p class="text-xs text-gray-500 uppercase">Milestones</p>
			</div>
		</div>

		<!-- Schedule Viewer -->
		<ScheduleViewer {data} {showFloat} {showBaseline} {showDependencies} {criticalOnly} />
	{/if}
</main>
