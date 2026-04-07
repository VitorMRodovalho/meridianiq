<script lang="ts">
	import { onMount } from 'svelte';
	import { getProjects, compareSchedules } from '$lib/api';
	import type { ProjectListItem, CompareResponse } from '$lib/types';
	import GaugeChart from '$lib/components/charts/GaugeChart.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';
	import { error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';

	let projects: ProjectListItem[] = $state([]);
	let baselineId = $state('');
	let updateId = $state('');
	let loading = $state(false);
	let projectsLoading = $state(true);
	let error = $state('');
	let result: CompareResponse | null = $state(null);

	onMount(async () => {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch {
			error = 'Failed to load projects';
			toastError(error);
		} finally {
			projectsLoading = false;
		}
	});

	async function doCompare() {
		if (!baselineId || !updateId) {
			error = 'Please select both baseline and update projects';
			return;
		}
		if (baselineId === updateId) {
			error = 'Baseline and update must be different projects';
			return;
		}
		loading = true;
		error = '';
		result = null;
		try {
			result = await compareSchedules(baselineId, updateId);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Comparison failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Compare - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-7xl mx-auto">
	<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6">Compare Schedules</h1>

	<!-- Selection -->
	<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
		{#if projectsLoading}
			<p class="text-gray-500 dark:text-gray-400">Loading projects...</p>
		{:else if projects.length < 2}
			<p class="text-gray-500 dark:text-gray-400">Upload at least two XER files to compare schedules.</p>
			<a href="/upload" class="mt-3 inline-block text-sm text-blue-600 hover:underline">Upload XER File</a>
		{:else}
			<div class="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
				<div>
					<label for="baseline" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Baseline Schedule</label>
					<select
						id="baseline"
						bind:value={baselineId}
						class="w-full border border-gray-300 dark:border-gray-600 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
					>
						<option value="">Select baseline...</option>
						{#each projects as p}
							<option value={p.project_id}>{p.name || p.project_id} ({p.activity_count} activities)</option>
						{/each}
					</select>
				</div>
				<div>
					<label for="update" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Update Schedule</label>
					<select
						id="update"
						bind:value={updateId}
						class="w-full border border-gray-300 dark:border-gray-600 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
					>
						<option value="">Select update...</option>
						{#each projects as p}
							<option value={p.project_id}>{p.name || p.project_id} ({p.activity_count} activities)</option>
						{/each}
					</select>
				</div>
				<div>
					<button
						onclick={doCompare}
						disabled={loading}
						class="w-full bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
					>
						{loading ? 'Comparing...' : 'Compare'}
					</button>
				</div>
			</div>
		{/if}
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 text-sm text-red-700 mb-6">{error}</div>
	{/if}

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
			Running comparison analysis...
		</div>
	{/if}

	{#if result}
		<!-- Quick actions -->
		<div class="flex items-center gap-3 mb-4">
			<a
				href="/schedule?project={updateId}&baseline={baselineId}"
				class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 text-white rounded-md text-xs font-medium hover:bg-teal-700"
			>
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>
				View in Schedule Viewer
			</a>
			{#if result.significant_float_changes.length > 0}
				<span class="text-xs text-gray-500 dark:text-gray-400">
					Float erosion: <strong class="text-red-600">{result.significant_float_changes.filter(f => f.direction === 'decreased').length}</strong> decreased,
					<strong class="text-green-600">{result.significant_float_changes.filter(f => f.direction === 'increased').length}</strong> increased
				</span>
			{/if}
		</div>

		<!-- Summary Cards -->
		<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Changed</p>
				<p class="text-2xl font-bold {result.changed_percentage > 20 ? 'text-red-600' : result.changed_percentage > 5 ? 'text-yellow-600' : 'text-green-600'}">
					{result.changed_percentage.toFixed(1)}%
				</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Added</p>
				<p class="text-2xl font-bold text-green-600">{result.activities_added.length}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Deleted</p>
				<p class="text-2xl font-bold text-red-600">{result.activities_deleted.length}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Modified</p>
				<p class="text-2xl font-bold text-blue-600">{result.activity_modifications.length}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Rel Added</p>
				<p class="text-2xl font-bold text-green-600">{result.relationships_added.length}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">CP Changed</p>
				<p class="text-lg font-bold {result.critical_path_changed ? 'text-red-600' : 'text-green-600'}">
					{result.critical_path_changed ? 'YES' : 'NO'}
				</p>
			</div>
		</div>

		<!-- Visual Charts -->
		<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
			<BarChart
				title="Change Distribution"
				data={[
					{ label: 'Added', value: result.activities_added.length, color: '#10b981' },
					{ label: 'Deleted', value: result.activities_deleted.length, color: '#ef4444' },
					{ label: 'Modified', value: result.activity_modifications.length, color: '#3b82f6' },
					{ label: 'Duration', value: result.duration_changes.length, color: '#8b5cf6' },
					{ label: 'Float', value: result.significant_float_changes.length, color: '#f59e0b' },
					{ label: 'Constraints', value: result.constraint_changes.length, color: '#06b6d4' },
				]}
				formatValue={(v) => Math.round(v).toString()}
			/>
			{#if result.manipulation_score !== undefined}
				<GaugeChart
					value={result.manipulation_score}
					title="Manipulation Risk Score"
					label={result.manipulation_classification === 'red_flag' ? 'RED FLAG' : result.manipulation_classification === 'suspicious' ? 'SUSPICIOUS' : 'NORMAL'}
					size={200}
					bands={[
						{ threshold: 30, color: '#10b981' },
						{ threshold: 60, color: '#f59e0b' },
						{ threshold: 100, color: '#ef4444' },
					]}
				/>
			{/if}
		</div>

		<!-- Match Method + Code Restructuring -->
		{#if result.match_stats}
			<div class="bg-blue-50 dark:bg-blue-950 border border-blue-200 rounded-lg p-4 mb-6">
				<h3 class="text-sm font-medium text-blue-800 mb-2">Matching Method</h3>
				<div class="grid grid-cols-3 gap-4 text-sm">
					<div>
						<span class="text-blue-600 font-bold">{result.match_stats.matched_by_task_id.toLocaleString()}</span>
						<span class="text-blue-700"> by system ID</span>
					</div>
					<div>
						<span class="text-blue-600 font-bold">{result.match_stats.matched_by_task_code.toLocaleString()}</span>
						<span class="text-blue-700"> by activity code</span>
					</div>
					<div>
						<span class="text-blue-600 font-bold">{result.match_stats.total_matched.toLocaleString()}</span>
						<span class="text-blue-700"> total matched</span>
					</div>
				</div>
				{#if result.match_stats.code_restructured > 0}
					<p class="text-xs text-blue-600 mt-2">
						{result.match_stats.code_restructured} activities had their activity code changed between versions
					</p>
				{/if}
			</div>
		{/if}

		{#if result.code_restructuring && result.code_restructuring.length > 0}
			<div class="border border-yellow-300 bg-yellow-50 dark:bg-yellow-950 rounded-lg p-4 mb-6">
				<h3 class="text-sm font-medium text-yellow-800 mb-2">Schedule Restructuring Detected ({result.code_restructuring.length} code changes)</h3>
				<div class="max-h-48 overflow-y-auto">
					<table class="w-full text-xs">
						<thead><tr class="text-left text-yellow-700"><th class="py-1 pr-2">Old Code</th><th class="py-1 pr-2">New Code</th><th class="py-1">Activity</th></tr></thead>
						<tbody>
							{#each result.code_restructuring.slice(0, 20) as cr}
								<tr class="border-t border-yellow-200"><td class="py-1 pr-2 font-mono">{cr.old_code}</td><td class="py-1 pr-2 font-mono">{cr.new_code}</td><td class="py-1">{cr.activity_name}</td></tr>
							{/each}
							{#if result.code_restructuring.length > 20}
								<tr><td colspan="3" class="py-1 text-yellow-600">... and {result.code_restructuring.length - 20} more</td></tr>
							{/if}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		<!-- Manipulation Classification Banner -->
		{@const classColor = result.manipulation_classification === 'red_flag' ? 'border-red-300 bg-red-50 dark:bg-red-950' : result.manipulation_classification === 'suspicious' ? 'border-yellow-300 bg-yellow-50 dark:bg-yellow-950' : 'border-green-300 bg-green-50 dark:bg-green-950'}
		{@const classText = result.manipulation_classification === 'red_flag' ? 'text-red-800' : result.manipulation_classification === 'suspicious' ? 'text-yellow-800' : 'text-green-800'}
		{@const classLabel = result.manipulation_classification === 'red_flag' ? 'RED FLAG' : result.manipulation_classification === 'suspicious' ? 'SUSPICIOUS' : 'NORMAL'}

		<div class="border-2 {classColor} rounded-lg p-6 mb-6">
			<div class="flex items-center justify-between mb-4">
				<div class="flex items-center gap-3">
					<span class="px-3 py-1 text-sm font-bold rounded-full {result.manipulation_classification === 'red_flag' ? 'bg-red-200 text-red-900' : result.manipulation_classification === 'suspicious' ? 'bg-yellow-200 text-yellow-900' : 'bg-green-200 text-green-900'}">
						{classLabel}
					</span>
					<h2 class="text-lg font-bold {classText}">
						{#if result.manipulation_classification === 'normal'}
							No manipulation indicators
						{:else}
							Schedule Manipulation Indicators
						{/if}
					</h2>
				</div>
				{#if result.manipulation_score !== undefined}
					<div class="text-right">
						<p class="text-2xl font-bold {classText}">{result.manipulation_score}</p>
						<p class="text-xs text-gray-500 dark:text-gray-400">Risk Score</p>
					</div>
				{/if}
			</div>

			{#if result.manipulation_rationale}
				<p class="text-sm {classText} mb-4">{result.manipulation_rationale}</p>
			{/if}

			{#if result.manipulation_flags.length > 0}
				<div class="space-y-3">
					{#each result.manipulation_flags as flag}
						<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
							<div class="flex items-center gap-2 mb-1">
								<span class="text-xs font-bold px-2 py-0.5 rounded-full {flag.classification === 'red_flag' ? 'bg-red-200 text-red-800' : flag.classification === 'suspicious' ? 'bg-yellow-200 text-yellow-800' : 'bg-gray-200 text-gray-800'}">
									{(flag.classification || flag.severity).toUpperCase().replace('_', ' ')}
								</span>
								<span class="text-sm font-medium text-gray-900 dark:text-gray-100">{flag.indicator}</span>
								{#if flag.score}
									<span class="text-xs text-gray-400 ml-auto">Score: {flag.score}</span>
								{/if}
							</div>
							<p class="text-sm text-gray-600 dark:text-gray-400">Activity: {flag.task_id} — {flag.task_name}</p>
							<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{flag.description}</p>
							{#if flag.rationale}
								<p class="text-xs text-gray-400 mt-1 italic">{flag.rationale}</p>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Detailed Changes -->

		{#if result.activity_modifications.length > 0}
			<details class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg mb-4">
				<summary class="px-6 py-3 cursor-pointer text-sm font-medium text-gray-900 dark:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800">
					Activity Changes ({result.activity_modifications.length})
				</summary>
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Task ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Change Type</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Old Value</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">New Value</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each result.activity_modifications as change}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="px-4 py-2 font-medium text-gray-900 dark:text-gray-100">{change.task_id}</td>
									<td class="px-4 py-2 text-gray-700 dark:text-gray-300">{change.task_name}</td>
									<td class="px-4 py-2 text-gray-500 dark:text-gray-400">{change.change_type}</td>
									<td class="px-4 py-2 text-red-600">{change.old_value}</td>
									<td class="px-4 py-2 text-green-600">{change.new_value}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</details>
		{/if}

		{#if result.duration_changes.length > 0}
			<details class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg mb-4">
				<summary class="px-6 py-3 cursor-pointer text-sm font-medium text-gray-900 dark:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800">
					Duration Changes ({result.duration_changes.length})
				</summary>
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Task ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Old</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">New</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Delta</th>
								<th class="px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase w-32">Visual</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each result.duration_changes as change}
								{@const oldVal = parseFloat(change.old_value)}
								{@const newVal = parseFloat(change.new_value)}
								{@const maxVal = Math.max(oldVal, newVal, 1)}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="px-4 py-2 font-medium text-gray-900 dark:text-gray-100">{change.task_id}</td>
									<td class="px-4 py-2 text-gray-700 dark:text-gray-300">{change.task_name}</td>
									<td class="px-4 py-2 text-right text-gray-500 dark:text-gray-400">{change.old_value}</td>
									<td class="px-4 py-2 text-right text-gray-500 dark:text-gray-400">{change.new_value}</td>
									<td class="px-4 py-2 text-right font-medium {newVal > oldVal ? 'text-red-600' : 'text-green-600'}">
										{(newVal - oldVal).toFixed(1)}
									</td>
									<td class="px-4 py-2">
										<div class="flex items-center gap-0.5 h-4">
											<div class="h-2 rounded bg-gray-400 opacity-50" style="width: {(oldVal / maxVal) * 100}%"></div>
										</div>
										<div class="flex items-center gap-0.5 h-4 -mt-1">
											<div class="h-2 rounded {newVal > oldVal ? 'bg-red-500' : 'bg-green-500'}" style="width: {(newVal / maxVal) * 100}%"></div>
										</div>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</details>
		{/if}

		{#if result.significant_float_changes.length > 0}
			<details class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg mb-4">
				<summary class="px-6 py-3 cursor-pointer text-sm font-medium text-gray-900 dark:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800">
					Float Changes ({result.significant_float_changes.length})
				</summary>
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Task ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Old Float</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">New Float</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Delta</th>
								<th class="px-4 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Direction</th>
								<th class="px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase w-24">Erosion</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each result.significant_float_changes as change}
								{@const maxFloat = Math.max(Math.abs(change.old_float), Math.abs(change.new_float), 1)}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800 {change.delta < -5 ? 'bg-red-50 dark:bg-red-950' : ''}">
									<td class="px-4 py-2 font-medium text-gray-900 dark:text-gray-100">{change.task_id}</td>
									<td class="px-4 py-2 text-gray-700 dark:text-gray-300">{change.task_name}</td>
									<td class="px-4 py-2 text-right text-gray-500 dark:text-gray-400">{change.old_float.toFixed(1)}</td>
									<td class="px-4 py-2 text-right text-gray-500 dark:text-gray-400">{change.new_float.toFixed(1)}</td>
									<td class="px-4 py-2 text-right font-medium {change.delta < 0 ? 'text-red-600' : 'text-green-600'}">{change.delta.toFixed(1)}</td>
									<td class="px-4 py-2 text-center text-lg">{change.direction === 'decreased' ? '\u2193' : '\u2191'}</td>
									<td class="px-4 py-2">
										<div class="h-1.5 rounded-full bg-gray-200 overflow-hidden">
											<div class="h-full rounded-full {change.delta < 0 ? 'bg-red-500' : 'bg-green-500'}" style="width: {Math.min(100, Math.abs(change.delta) / maxFloat * 100)}%"></div>
										</div>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</details>
		{/if}

		{#if result.relationships_added.length > 0 || result.relationships_deleted.length > 0 || result.relationships_modified.length > 0}
			{@const allRelChanges = [
				...result.relationships_added.map(r => ({ ...r, type: 'Added' })),
				...result.relationships_deleted.map(r => ({ ...r, type: 'Deleted' })),
				...result.relationships_modified.map(r => ({ ...r, type: 'Modified' }))
			]}
			<details class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg mb-4">
				<summary class="px-6 py-3 cursor-pointer text-sm font-medium text-gray-900 dark:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800">
					Relationship Changes ({allRelChanges.length})
				</summary>
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Task ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Pred ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Change Type</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each allRelChanges as rel}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="px-4 py-2 font-medium text-gray-900 dark:text-gray-100">{rel.task_id}</td>
									<td class="px-4 py-2 text-gray-700 dark:text-gray-300">{rel.pred_task_id}</td>
									<td class="px-4 py-2">
										<span class="px-2 py-0.5 rounded-full text-xs font-medium {rel.type === 'Added' ? 'bg-green-100 text-green-800' : rel.type === 'Deleted' ? 'bg-red-100 text-red-800' : 'bg-blue-100 text-blue-800'}">
											{rel.type}
										</span>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</details>
		{/if}

		{#if result.constraint_changes.length > 0}
			<details class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg mb-4">
				<summary class="px-6 py-3 cursor-pointer text-sm font-medium text-gray-900 dark:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800">
					Constraint Changes ({result.constraint_changes.length})
				</summary>
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Task ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Change Type</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Details</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each result.constraint_changes as change}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="px-4 py-2 font-medium text-gray-900 dark:text-gray-100">{change.task_id}</td>
									<td class="px-4 py-2 text-gray-700 dark:text-gray-300">{change.change_type}</td>
									<td class="px-4 py-2 text-gray-500 dark:text-gray-400">{change.old_value} {change.new_value ? `\u2192 ${change.new_value}` : ''}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</details>
		{/if}
	{/if}
</div>
