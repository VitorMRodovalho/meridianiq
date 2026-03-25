<script lang="ts">
	import { onMount } from 'svelte';
	import { getProjects } from '$lib/api';
	import type { ProjectListItem } from '$lib/types';

	let projects: ProjectListItem[] = $state([]);
	let loading = $state(true);
	let error = $state('');

	onMount(async () => {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load projects';
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head>
	<title>Projects - P6 XER Analytics</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<h1 class="text-2xl font-bold text-gray-900 mb-6">Projects</h1>

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			Loading projects...
		</div>
	{:else if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">{error}</div>
	{:else if projects.length === 0}
		<div class="bg-white rounded-lg border border-gray-200 p-8 text-center">
			<p class="text-gray-500 mb-4">No projects uploaded yet.</p>
			<a
				href="/upload"
				class="inline-block bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700"
			>
				Upload XER File
			</a>
		</div>
	{:else}
		<div class="bg-white rounded-lg border border-gray-200 overflow-hidden">
			<table class="min-w-full divide-y divide-gray-200">
				<thead class="bg-gray-50">
					<tr>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Project Name</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Project ID</th>
						<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Activities</th>
						<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Relationships</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200">
					{#each projects as project}
						<tr
							class="hover:bg-gray-50 cursor-pointer transition-colors"
							onclick={() => window.location.href = `/projects/${project.project_id}`}
						>
							<td class="px-6 py-4 text-sm font-medium text-gray-900">{project.name || 'Unnamed'}</td>
							<td class="px-6 py-4 text-sm text-gray-500">{project.project_id}</td>
							<td class="px-6 py-4 text-sm text-gray-500 text-right">{project.activity_count}</td>
							<td class="px-6 py-4 text-sm text-gray-500 text-right">{project.relationship_count}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
