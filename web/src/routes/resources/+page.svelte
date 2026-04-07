<script lang="ts">
	import { getProjects, runResourceLeveling } from '$lib/api';
	import type { LevelingResponse } from '$lib/types';
	import ResourceChart from '$lib/components/charts/ResourceChart.svelte';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let result = $state<LevelingResponse | null>(null);
	let loading: boolean = $state(false);
	let error: string = $state('');

	let rsrcId: string = $state('');
	let maxUnits: number = $state(1);
	let priorityRule: string = $state('late_start');

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load projects';
		}
	}

	async function runLeveling() {
		if (!selectedProject || !rsrcId) return;
		loading = true;
		error = '';
		result = null;
		try {
			result = await runResourceLeveling(
				selectedProject,
				[{ rsrc_id: rsrcId, max_units: maxUnits }],
				priorityRule
			);
			toastSuccess(`Leveled: ${result.leveled_duration_days}d (+${result.extension_days}d)`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Leveling failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	const hasProfile = $derived(result !== null && result.resource_profiles.length > 0);
</script>

<svelte:head>
	<title>Resource Leveling - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Resource Leveling</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">Resource-constrained scheduling via Serial SGS (AACE RP 46R-11)</p>
	</div>

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
				<label for="rsrc" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Resource ID</label>
				<input id="rsrc" bind:value={rsrcId} placeholder="e.g. CRANE01" class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
			<div>
				<label for="units" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Max Units</label>
				<input id="units" type="number" min="1" bind:value={maxUnits} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
			<div>
				<label for="rule" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Priority Rule</label>
				<select id="rule" bind:value={priorityRule} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm">
					<option value="late_start">Late Start</option>
					<option value="early_start">Early Start</option>
					<option value="float">Float</option>
					<option value="duration">Duration</option>
				</select>
			</div>
		</div>
		<div class="mt-4">
			<button onclick={runLeveling} disabled={!selectedProject || !rsrcId || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Leveling...' : 'Run Resource Leveling'}
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

	{#if result}
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Original</p>
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{result.original_duration_days}d</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Leveled</p>
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{result.leveled_duration_days}d</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Extension</p>
				<p class="text-2xl font-bold {result.extension_days > 0 ? 'text-amber-600' : 'text-green-600'}">
					+{result.extension_days}d ({result.extension_pct}%)
				</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Priority Rule</p>
				<p class="text-lg font-bold text-gray-700 dark:text-gray-300">{result.priority_rule}</p>
			</div>
		</div>

		{#if hasProfile}
			{#each result.resource_profiles as profile}
				<div class="mb-6">
					<ResourceChart
						demandByDay={profile.demand_by_day}
						maxUnits={profile.max_units}
						title="Resource Demand Profile"
						rsrcName={profile.rsrc_name || profile.rsrc_id}
						height={240}
					/>
				</div>
			{/each}
		{/if}

		{#if result.activity_shifts.length > 0}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Activity Shifts ({result.activity_shifts.filter(s => s.shift_days > 0).length} shifted)</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-200 dark:border-gray-700">
								<th class="text-left py-2 px-3">Code</th>
								<th class="text-left py-2 px-3">Name</th>
								<th class="text-right py-2 px-3">Original Start</th>
								<th class="text-right py-2 px-3">Leveled Start</th>
								<th class="text-right py-2 px-3">Shift</th>
							</tr>
						</thead>
						<tbody>
							{#each result.activity_shifts.slice(0, 30) as shift}
								<tr class="border-b border-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="py-2 px-3 font-mono text-xs">{shift.task_code}</td>
									<td class="py-2 px-3">{shift.task_name}</td>
									<td class="py-2 px-3 text-right">Day {shift.original_start}</td>
									<td class="py-2 px-3 text-right">Day {shift.leveled_start}</td>
									<td class="py-2 px-3 text-right {shift.shift_days > 0 ? 'text-amber-600 font-semibold' : ''}">
										{shift.shift_days > 0 ? '+' : ''}{shift.shift_days}d
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
