<script lang="ts">
	import { onMount } from 'svelte';
	import { getProjects, compareSchedules } from '$lib/api';
	import type { ProjectListItem, CompareResponse } from '$lib/types';

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
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Compare - P6 XER Analytics</title>
</svelte:head>

<div class="p-8 max-w-7xl mx-auto">
	<h1 class="text-2xl font-bold text-gray-900 mb-6">Compare Schedules</h1>

	<!-- Selection -->
	<div class="bg-white border border-gray-200 rounded-lg p-6 mb-6">
		{#if projectsLoading}
			<p class="text-gray-500">Loading projects...</p>
		{:else if projects.length < 2}
			<p class="text-gray-500">Upload at least two XER files to compare schedules.</p>
			<a href="/upload" class="mt-3 inline-block text-sm text-blue-600 hover:underline">Upload XER File</a>
		{:else}
			<div class="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
				<div>
					<label for="baseline" class="block text-sm font-medium text-gray-700 mb-1">Baseline Schedule</label>
					<select
						id="baseline"
						bind:value={baselineId}
						class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
					>
						<option value="">Select baseline...</option>
						{#each projects as p}
							<option value={p.project_id}>{p.name || p.project_id} ({p.activity_count} activities)</option>
						{/each}
					</select>
				</div>
				<div>
					<label for="update" class="block text-sm font-medium text-gray-700 mb-1">Update Schedule</label>
					<select
						id="update"
						bind:value={updateId}
						class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
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

	{#if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700 mb-6">{error}</div>
	{/if}

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
			Running comparison analysis...
		</div>
	{/if}

	{#if result}
		<!-- Summary Cards -->
		<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 uppercase">Changed</p>
				<p class="text-2xl font-bold {result.changed_percentage > 20 ? 'text-red-600' : result.changed_percentage > 5 ? 'text-yellow-600' : 'text-green-600'}">
					{result.changed_percentage.toFixed(1)}%
				</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 uppercase">Added</p>
				<p class="text-2xl font-bold text-green-600">{result.activities_added.length}</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 uppercase">Deleted</p>
				<p class="text-2xl font-bold text-red-600">{result.activities_deleted.length}</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 uppercase">Modified</p>
				<p class="text-2xl font-bold text-blue-600">{result.activity_modifications.length}</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 uppercase">Rel Added</p>
				<p class="text-2xl font-bold text-green-600">{result.relationships_added.length}</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 uppercase">CP Changed</p>
				<p class="text-lg font-bold {result.critical_path_changed ? 'text-red-600' : 'text-green-600'}">
					{result.critical_path_changed ? 'YES' : 'NO'}
				</p>
			</div>
		</div>

		<!-- Manipulation Alerts -->
		{#if result.manipulation_flags.length > 0}
			<div class="border-2 border-red-300 bg-red-50 rounded-lg p-6 mb-6">
				<div class="flex items-center gap-2 mb-4">
					<svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
					</svg>
					<h2 class="text-lg font-bold text-red-800">Schedule Manipulation Indicators</h2>
				</div>
				<div class="space-y-3">
					{#each result.manipulation_flags as flag}
						<div class="bg-white rounded-lg border border-red-200 p-4">
							<div class="flex items-center gap-2 mb-1">
								<span class="text-xs font-bold px-2 py-0.5 rounded-full {flag.severity === 'critical' ? 'bg-red-200 text-red-800' : 'bg-yellow-200 text-yellow-800'}">
									{flag.severity.toUpperCase()}
								</span>
								<span class="text-sm font-medium text-gray-900">{flag.indicator}</span>
							</div>
							<p class="text-sm text-gray-600">Activity: {flag.task_id} - {flag.task_name}</p>
							<p class="text-sm text-gray-500 mt-1">{flag.description}</p>
						</div>
					{/each}
				</div>
			</div>
		{:else}
			<div class="border border-green-200 bg-green-50 rounded-lg p-4 mb-6 flex items-center gap-2">
				<svg class="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
					<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
				</svg>
				<span class="text-sm font-medium text-green-800">No manipulation indicators detected</span>
			</div>
		{/if}

		<!-- Detailed Changes -->

		{#if result.activity_modifications.length > 0}
			<details class="bg-white border border-gray-200 rounded-lg mb-4">
				<summary class="px-6 py-3 cursor-pointer text-sm font-medium text-gray-900 hover:bg-gray-50">
					Activity Changes ({result.activity_modifications.length})
				</summary>
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Task ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Change Type</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Old Value</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">New Value</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each result.activity_modifications as change}
								<tr class="hover:bg-gray-50">
									<td class="px-4 py-2 font-medium text-gray-900">{change.task_id}</td>
									<td class="px-4 py-2 text-gray-700">{change.task_name}</td>
									<td class="px-4 py-2 text-gray-500">{change.change_type}</td>
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
			<details class="bg-white border border-gray-200 rounded-lg mb-4">
				<summary class="px-6 py-3 cursor-pointer text-sm font-medium text-gray-900 hover:bg-gray-50">
					Duration Changes ({result.duration_changes.length})
				</summary>
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Task ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Old Duration</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">New Duration</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Delta</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each result.duration_changes as change}
								<tr class="hover:bg-gray-50">
									<td class="px-4 py-2 font-medium text-gray-900">{change.task_id}</td>
									<td class="px-4 py-2 text-gray-700">{change.task_name}</td>
									<td class="px-4 py-2 text-right text-gray-500">{change.old_value}</td>
									<td class="px-4 py-2 text-right text-gray-500">{change.new_value}</td>
									<td class="px-4 py-2 text-right font-medium {parseFloat(change.new_value) > parseFloat(change.old_value) ? 'text-red-600' : 'text-green-600'}">
										{(parseFloat(change.new_value) - parseFloat(change.old_value)).toFixed(1)}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</details>
		{/if}

		{#if result.significant_float_changes.length > 0}
			<details class="bg-white border border-gray-200 rounded-lg mb-4">
				<summary class="px-6 py-3 cursor-pointer text-sm font-medium text-gray-900 hover:bg-gray-50">
					Float Changes ({result.significant_float_changes.length})
				</summary>
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Task ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Old Float</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">New Float</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Delta</th>
								<th class="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Direction</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each result.significant_float_changes as change}
								<tr class="hover:bg-gray-50">
									<td class="px-4 py-2 font-medium text-gray-900">{change.task_id}</td>
									<td class="px-4 py-2 text-gray-700">{change.task_name}</td>
									<td class="px-4 py-2 text-right text-gray-500">{change.old_float.toFixed(1)}</td>
									<td class="px-4 py-2 text-right text-gray-500">{change.new_float.toFixed(1)}</td>
									<td class="px-4 py-2 text-right font-medium {change.delta < 0 ? 'text-red-600' : 'text-green-600'}">{change.delta.toFixed(1)}</td>
									<td class="px-4 py-2 text-center text-lg">{change.direction === 'decreased' ? '\u2193' : '\u2191'}</td>
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
			<details class="bg-white border border-gray-200 rounded-lg mb-4">
				<summary class="px-6 py-3 cursor-pointer text-sm font-medium text-gray-900 hover:bg-gray-50">
					Relationship Changes ({allRelChanges.length})
				</summary>
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Task ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Pred ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Change Type</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each allRelChanges as rel}
								<tr class="hover:bg-gray-50">
									<td class="px-4 py-2 font-medium text-gray-900">{rel.task_id}</td>
									<td class="px-4 py-2 text-gray-700">{rel.pred_task_id}</td>
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
			<details class="bg-white border border-gray-200 rounded-lg mb-4">
				<summary class="px-6 py-3 cursor-pointer text-sm font-medium text-gray-900 hover:bg-gray-50">
					Constraint Changes ({result.constraint_changes.length})
				</summary>
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Task ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Change Type</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each result.constraint_changes as change}
								<tr class="hover:bg-gray-50">
									<td class="px-4 py-2 font-medium text-gray-900">{change.task_id}</td>
									<td class="px-4 py-2 text-gray-700">{change.change_type}</td>
									<td class="px-4 py-2 text-gray-500">{change.old_value} {change.new_value ? `\u2192 ${change.new_value}` : ''}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</details>
		{/if}
	{/if}
</div>
