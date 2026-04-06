<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import GanttChart from '$lib/components/charts/GanttChart.svelte';
	import { supabase } from '$lib/supabase';

	interface LookaheadActivity {
		task_id: string;
		task_code: string;
		task_name: string;
		status: string;
		start_day: number;
		finish_day: number;
		duration_days: number;
		total_float_days: number;
		progress_pct: number;
		is_critical: boolean;
	}

	interface LookaheadResult {
		window_weeks: number;
		window_days: number;
		activities: LookaheadActivity[];
		total_in_window: number;
		active_count: number;
		starting_count: number;
		finishing_count: number;
		critical_count: number;
	}

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let weeks: number = $state(2);
	let result = $state<LookaheadResult | null>(null);
	let loading: boolean = $state(false);
	let error: string = $state('');

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
		}
	}

	async function loadLookahead() {
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
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/lookahead?weeks=${weeks}`, { headers });
			if (!res.ok) throw new Error(await res.text());
			result = await res.json();
			toastSuccess(`${result!.total_in_window} activities in ${weeks}-week window`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	const ganttItems = $derived(
		result
			? result.activities.slice(0, 40).map((a) => ({
					id: a.task_id,
					label: a.task_code || a.task_name.slice(0, 15),
					start: a.start_day,
					duration: a.duration_days,
					isCritical: a.is_critical,
					progress: a.progress_pct,
					color: a.is_critical ? '#ef4444' : a.status === 'TK_Active' ? '#3b82f6' : '#9ca3af',
				}))
			: []
	);
</script>

<svelte:head>
	<title>Look-Ahead Schedule - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900">Look-Ahead Schedule</h1>
		<p class="text-gray-500 mt-1">Short-term activity window for field coordination (Lean Construction LPS)</p>
	</div>

	<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
		<div class="flex items-end gap-4">
			<div class="flex-1">
				<label for="project" class="block text-sm font-medium text-gray-700 mb-1">Project</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
					<option value="">Choose project...</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<div>
				<label for="weeks" class="block text-sm font-medium text-gray-700 mb-1">Window</label>
				<select id="weeks" bind:value={weeks} class="rounded-md border border-gray-300 px-3 py-2 text-sm">
					<option value={1}>1 week</option>
					<option value={2}>2 weeks</option>
					<option value={3}>3 weeks</option>
					<option value={4}>4 weeks</option>
					<option value={6}>6 weeks</option>
				</select>
			</div>
			<button onclick={loadLookahead} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Loading...' : 'Generate'}
			</button>
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
			<p class="text-red-700 text-sm">{error}</p>
		</div>
	{/if}

	{#if result}
		<div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-2xl font-bold text-gray-900">{result.total_in_window}</p>
				<p class="text-xs text-gray-500 uppercase">In Window</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-2xl font-bold text-blue-600">{result.active_count}</p>
				<p class="text-xs text-gray-500 uppercase">Active</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-2xl font-bold text-green-600">{result.starting_count}</p>
				<p class="text-xs text-gray-500 uppercase">Starting</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-2xl font-bold text-amber-600">{result.finishing_count}</p>
				<p class="text-xs text-gray-500 uppercase">Finishing</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-2xl font-bold text-red-600">{result.critical_count}</p>
				<p class="text-xs text-gray-500 uppercase">Critical</p>
			</div>
		</div>

		{#if ganttItems.length > 0}
			<div class="mb-6">
				<GanttChart
					items={ganttItems}
					title="{weeks}-Week Look-Ahead"
					totalDuration={result.window_days}
				/>
			</div>
		{/if}

		{#if result.activities.length > 0}
			<div class="bg-white rounded-lg border border-gray-200 p-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-3">Activities ({result.total_in_window})</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-200">
								<th class="text-left py-2 px-3">Code</th>
								<th class="text-left py-2 px-3">Name</th>
								<th class="text-left py-2 px-3">Status</th>
								<th class="text-right py-2 px-3">Start</th>
								<th class="text-right py-2 px-3">Dur</th>
								<th class="text-right py-2 px-3">Float</th>
								<th class="text-right py-2 px-3">Prog</th>
								<th class="text-center py-2 px-3">CP</th>
							</tr>
						</thead>
						<tbody>
							{#each result.activities as act}
								<tr class="border-b border-gray-100 hover:bg-gray-50 {act.is_critical ? 'bg-red-50' : ''}">
									<td class="py-2 px-3 font-mono text-xs">{act.task_code}</td>
									<td class="py-2 px-3">{act.task_name}</td>
									<td class="py-2 px-3">
										<span class="px-1.5 py-0.5 rounded text-xs {act.status === 'TK_Active' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'}">
											{act.status.replace('TK_', '')}
										</span>
									</td>
									<td class="py-2 px-3 text-right">D{act.start_day}</td>
									<td class="py-2 px-3 text-right">{act.duration_days}d</td>
									<td class="py-2 px-3 text-right {act.total_float_days <= 0 ? 'text-red-600 font-semibold' : ''}">{act.total_float_days}d</td>
									<td class="py-2 px-3 text-right">{act.progress_pct.toFixed(0)}%</td>
									<td class="py-2 px-3 text-center">{act.is_critical ? '●' : ''}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	{/if}
</main>
