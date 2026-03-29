<script lang="ts">
	import { onMount } from 'svelte';
	import { getProjects, getPrograms } from '$lib/api';
	import type { ProjectListItem, ProgramListItem } from '$lib/types';

	let projects: ProjectListItem[] = $state([]);
	let programs: ProgramListItem[] = $state([]);
	let loading = $state(true);
	let error = $state('');
	let viewMode: 'programs' | 'uploads' = $state('programs');

	onMount(async () => {
		try {
			const [projRes, progRes] = await Promise.all([
				getProjects(),
				getPrograms().catch(() => ({ programs: [] }))
			]);
			projects = projRes.projects;
			programs = progRes.programs;
			// Default to uploads view if no programs exist
			if (programs.length === 0 && projects.length > 0) {
				viewMode = 'uploads';
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load projects';
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head>
	<title>Projects - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-gray-900">Projects</h1>
		{#if programs.length > 0 && projects.length > 0}
			<div class="flex bg-gray-100 rounded-lg p-1">
				<button
					class="px-3 py-1 text-sm rounded-md transition-colors {viewMode === 'programs' ? 'bg-white shadow text-gray-900 font-medium' : 'text-gray-500 hover:text-gray-700'}"
					onclick={() => viewMode = 'programs'}
				>
					Programs
				</button>
				<button
					class="px-3 py-1 text-sm rounded-md transition-colors {viewMode === 'uploads' ? 'bg-white shadow text-gray-900 font-medium' : 'text-gray-500 hover:text-gray-700'}"
					onclick={() => viewMode = 'uploads'}
				>
					All Uploads
				</button>
			</div>
		{/if}
	</div>

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
	{:else if projects.length === 0 && programs.length === 0}
		<div class="bg-white rounded-lg border border-gray-200 p-8 text-center">
			<p class="text-gray-500 mb-4">No projects uploaded yet.</p>
			<a
				href="/upload"
				class="inline-block bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700"
			>
				Upload XER File
			</a>
		</div>
	{:else if viewMode === 'programs'}
		<!-- Programs view -->
		<div class="bg-white rounded-lg border border-gray-200 overflow-hidden">
			<table class="min-w-full divide-y divide-gray-200">
				<thead class="bg-gray-50">
					<tr>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Program Name</th>
						<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Revisions</th>
						<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Latest Activities</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200">
					{#each programs as program}
						<tr
							class="hover:bg-gray-50 cursor-pointer transition-colors"
							onclick={() => window.location.href = `/programs/${program.id}`}
						>
							<td class="px-6 py-4">
								<div class="text-sm font-medium text-gray-900">{program.name || 'Unnamed'}</div>
								{#if program.description}
									<div class="text-xs text-gray-400 mt-0.5">{program.description}</div>
								{/if}
							</td>
							<td class="px-6 py-4 text-sm text-gray-500 text-right">{program.revision_count}</td>
							<td class="px-6 py-4 text-sm text-gray-500 text-right">{program.latest_revision?.activity_count ?? '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else}
		<!-- Raw uploads view (backward compatible) -->
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
