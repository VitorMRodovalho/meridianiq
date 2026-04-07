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
	let selectedActivity = $state<import('$lib/components/ScheduleViewer/types').ActivityView | null>(null);
	let showFloat: boolean = $state(true);
	let showBaseline: boolean = $state(true);
	let showDependencies: boolean = $state(false);
	let criticalOnly: boolean = $state(false);

	const statusCounts = $derived(data ? {
		all: data.activities.length,
		active: data.activities.filter(a => a.status === 'active').length,
		not_started: data.activities.filter(a => a.status === 'not_started').length,
		complete: data.activities.filter(a => a.status === 'complete').length,
		critical: data.activities.filter(a => a.is_critical).length,
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
		<!-- Status filter pills -->
		{#if statusCounts}
		<div class="flex items-center gap-2 mb-4 flex-wrap">
			{#each [
				['All', 'all', 'bg-gray-600'],
				['Active', 'active', 'bg-blue-500'],
				['Not Started', 'not_started', 'bg-gray-400'],
				['Complete', 'complete', 'bg-green-500'],
				['Critical', 'critical', 'bg-red-500'],
				['Neg Float', 'negative_float', 'bg-red-400'],
				['Milestones', 'milestones', 'bg-amber-500'],
			] as [label, key, color]}
				<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
					<span class="w-2 h-2 rounded-full {color}"></span>
					{label}: {statusCounts[key as keyof typeof statusCounts]}
				</span>
			{/each}
		</div>
		{/if}

		<!-- Progress bar -->
		<div class="mb-4 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3">
			<div class="flex items-center justify-between mb-1">
				<span class="text-xs font-semibold text-gray-700 dark:text-gray-300">Overall Progress</span>
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
		<ScheduleViewer
			{data} {showFloat} {showBaseline} {showDependencies} {criticalOnly}
			onActivityClick={(taskId) => { selectedActivity = data?.activities.find(a => a.task_id === taskId) || null; }}
		/>

		<!-- Activity detail panel (click on bar) -->
		{#if selectedActivity}
			{@const a = selectedActivity}
			<div class="mt-4 bg-white dark:bg-gray-900 rounded-lg border border-blue-200 dark:border-blue-800 p-4">
				<div class="flex items-center justify-between mb-3">
					<div>
						<h3 class="text-sm font-bold text-gray-900 dark:text-gray-100">{a.task_code} — {a.task_name}</h3>
						<p class="text-[10px] text-gray-500">{a.wbs_path}</p>
					</div>
					<button onclick={() => selectedActivity = null} aria-label="Close detail" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
					</button>
				</div>
				<div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 text-xs">
					<div>
						<p class="text-gray-500">Status</p>
						<p class="font-semibold capitalize {a.status === 'complete' ? 'text-green-600' : a.status === 'active' ? 'text-blue-600' : 'text-gray-600'}">{a.status}</p>
					</div>
					<div>
						<p class="text-gray-500">Type</p>
						<p class="font-semibold capitalize text-gray-700 dark:text-gray-300">{a.task_type}</p>
					</div>
					<div>
						<p class="text-gray-500">Duration</p>
						<p class="font-semibold text-gray-700 dark:text-gray-300">{a.duration_days}d</p>
					</div>
					<div>
						<p class="text-gray-500">Total Float</p>
						<p class="font-semibold {a.total_float_days < 0 ? 'text-red-600' : a.total_float_days === 0 ? 'text-amber-600' : 'text-green-600'}">{a.total_float_days}d</p>
					</div>
					<div>
						<p class="text-gray-500">Progress</p>
						<p class="font-semibold text-blue-600">{a.progress_pct}%</p>
					</div>
					<div>
						<p class="text-gray-500">Critical</p>
						<p class="font-semibold {a.is_critical ? 'text-red-600' : 'text-gray-400'}">{a.is_critical ? 'YES' : 'No'}</p>
					</div>
					<div>
						<p class="text-gray-500">Early Start</p>
						<p class="font-semibold text-gray-700 dark:text-gray-300">{a.early_start}</p>
					</div>
					<div>
						<p class="text-gray-500">Early Finish</p>
						<p class="font-semibold text-gray-700 dark:text-gray-300">{a.early_finish}</p>
					</div>
					<div>
						<p class="text-gray-500">Late Start</p>
						<p class="font-semibold text-gray-700 dark:text-gray-300">{a.late_start || '—'}</p>
					</div>
					<div>
						<p class="text-gray-500">Late Finish</p>
						<p class="font-semibold text-gray-700 dark:text-gray-300">{a.late_finish || '—'}</p>
					</div>
					{#if a.baseline_start}
						<div>
							<p class="text-gray-500">Baseline Start</p>
							<p class="font-semibold text-gray-500">{a.baseline_start}</p>
						</div>
						<div>
							<p class="text-gray-500">Baseline Finish</p>
							<p class="font-semibold text-gray-500">{a.baseline_finish}</p>
						</div>
					{/if}
				</div>
				{#if a.alerts.length > 0}
					<div class="mt-3 flex gap-1">
						{#each a.alerts as alert}
							<span class="px-1.5 py-0.5 bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 rounded text-[9px] font-bold">{alert.replace(/_/g, ' ')}</span>
						{/each}
					</div>
				{/if}
			</div>
		{/if}

		<!-- Activity data table -->
		<details class="mt-4 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
			<summary class="px-4 py-3 cursor-pointer text-sm font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
				Activity Table ({data.activities.length} activities)
			</summary>
			<div class="overflow-x-auto max-h-96">
				<table class="w-full text-[10px]">
					<thead class="sticky top-0 bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="text-left py-1.5 px-2 font-semibold text-gray-500">Code</th>
							<th class="text-left py-1.5 px-2 font-semibold text-gray-500">Name</th>
							<th class="text-left py-1.5 px-2 font-semibold text-gray-500">Status</th>
							<th class="text-left py-1.5 px-2 font-semibold text-gray-500">Type</th>
							<th class="text-right py-1.5 px-2 font-semibold text-gray-500">Duration</th>
							<th class="text-right py-1.5 px-2 font-semibold text-gray-500">TF</th>
							<th class="text-right py-1.5 px-2 font-semibold text-gray-500">Progress</th>
							<th class="text-left py-1.5 px-2 font-semibold text-gray-500">Early Start</th>
							<th class="text-left py-1.5 px-2 font-semibold text-gray-500">Early Finish</th>
							<th class="text-center py-1.5 px-2 font-semibold text-gray-500">CP</th>
							<th class="text-left py-1.5 px-2 font-semibold text-gray-500">Alerts</th>
						</tr>
					</thead>
					<tbody>
						{#each data.activities as act}
							<tr class="border-t border-gray-100 dark:border-gray-800 hover:bg-blue-50 dark:hover:bg-gray-800">
								<td class="py-1 px-2 font-mono text-gray-500">{act.task_code}</td>
								<td class="py-1 px-2 text-gray-900 dark:text-gray-100 truncate max-w-48">{act.task_name}</td>
								<td class="py-1 px-2">
									<span class="px-1 py-0.5 rounded text-[8px] font-bold uppercase
										{act.status === 'complete' ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' :
										act.status === 'active' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' :
										'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}">{act.status}</span>
								</td>
								<td class="py-1 px-2 text-gray-500 capitalize">{act.task_type}</td>
								<td class="py-1 px-2 text-right font-mono">{act.duration_days}d</td>
								<td class="py-1 px-2 text-right font-mono {act.total_float_days < 0 ? 'text-red-600 font-bold' : act.total_float_days === 0 ? 'text-amber-600' : 'text-gray-500'}">{act.total_float_days}d</td>
								<td class="py-1 px-2 text-right font-mono">{act.progress_pct > 0 ? act.progress_pct + '%' : ''}</td>
								<td class="py-1 px-2 text-gray-500">{act.early_start}</td>
								<td class="py-1 px-2 text-gray-500">{act.early_finish}</td>
								<td class="py-1 px-2 text-center">{act.is_critical ? '●' : ''}</td>
								<td class="py-1 px-2">
									{#each act.alerts as alert}
										<span class="px-1 py-0.5 bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 rounded text-[8px] mr-0.5">{alert.replace('_', ' ')}</span>
									{/each}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</details>
	{/if}
</main>
