<script lang="ts">
	import { onMount } from 'svelte';
	import { getProjects, getPrograms } from '$lib/api';
	import type { ProjectListItem, ProgramListItem } from '$lib/types';

	let projects: ProjectListItem[] = $state([]);
	let programs: ProgramListItem[] = $state([]);
	let loading = $state(true);
	let error = $state('');
	let viewMode: 'programs' | 'uploads' = $state('programs');

	// Search, sort, filter state
	let search = $state('');
	let sortBy: 'name' | 'activities' | 'relationships' = $state('name');
	let sortDir: 'asc' | 'desc' = $state('asc');

	onMount(async () => {
		try {
			const [projRes, progRes] = await Promise.all([
				getProjects(),
				getPrograms().catch(() => ({ programs: [] }))
			]);
			projects = projRes.projects;
			programs = progRes.programs;
			if (programs.length === 0 && projects.length > 0) {
				viewMode = 'uploads';
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load projects';
		} finally {
			loading = false;
		}
	});

	function toggleSort(col: typeof sortBy) {
		if (sortBy === col) {
			sortDir = sortDir === 'asc' ? 'desc' : 'asc';
		} else {
			sortBy = col;
			sortDir = col === 'name' ? 'asc' : 'desc';
		}
	}

	const filteredProjects = $derived.by(() => {
		let list = projects;
		if (search.trim()) {
			const q = search.toLowerCase();
			list = list.filter(
				(p) =>
					(p.name || '').toLowerCase().includes(q) ||
					p.project_id.toLowerCase().includes(q)
			);
		}
		const dir = sortDir === 'asc' ? 1 : -1;
		return [...list].sort((a, b) => {
			if (sortBy === 'name') {
				return dir * (a.name || '').localeCompare(b.name || '');
			}
			if (sortBy === 'activities') {
				return dir * (a.activity_count - b.activity_count);
			}
			return dir * (a.relationship_count - b.relationship_count);
		});
	});

	const filteredPrograms = $derived.by(() => {
		if (!search.trim()) return programs;
		const q = search.toLowerCase();
		return programs.filter(
			(p) =>
				(p.name || '').toLowerCase().includes(q) ||
				(p.description || '').toLowerCase().includes(q)
		);
	});

	const sortIcon = $derived((col: string) => {
		if (sortBy !== col) return '';
		return sortDir === 'asc' ? '\u2191' : '\u2193';
	});
</script>

<svelte:head>
	<title>Projects - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Projects</h1>
		{#if programs.length > 0 && projects.length > 0}
			<div class="flex bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
				<button
					class="px-3 py-1 text-sm rounded-md transition-colors {viewMode === 'programs' ? 'bg-white dark:bg-gray-900 shadow text-gray-900 dark:text-gray-100 font-medium' : 'text-gray-500 hover:text-gray-700'}"
					onclick={() => viewMode = 'programs'}
				>
					Programs
				</button>
				<button
					class="px-3 py-1 text-sm rounded-md transition-colors {viewMode === 'uploads' ? 'bg-white dark:bg-gray-900 shadow text-gray-900 dark:text-gray-100 font-medium' : 'text-gray-500 hover:text-gray-700'}"
					onclick={() => viewMode = 'uploads'}
				>
					All Uploads
				</button>
			</div>
		{/if}
	</div>

	<!-- Search bar -->
	{#if !loading && (projects.length > 0 || programs.length > 0)}
		<div class="mb-4">
			<div class="relative">
				<svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
				</svg>
				<input
					type="text"
					bind:value={search}
					placeholder="Search by name or ID..."
					class="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
				/>
				{#if search}
					<button
						onclick={() => search = ''}
						class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:text-gray-400"
						aria-label="Clear search"
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				{/if}
			</div>
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			Loading projects...
		</div>
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 text-sm text-red-700">{error}</div>
	{:else if projects.length === 0 && programs.length === 0}
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
			<p class="text-gray-500 dark:text-gray-400 mb-4">No projects uploaded yet.</p>
			<a
				href="/upload"
				class="inline-block bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700"
			>
				Upload XER File
			</a>
		</div>
	{:else if viewMode === 'programs'}
		<!-- Programs view -->
		{#if filteredPrograms.length === 0}
			<p class="text-sm text-gray-500 dark:text-gray-400 py-8 text-center">No programs match "{search}"</p>
		{:else}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Program Name</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Revisions</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Latest Activities</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each filteredPrograms as program}
							<tr
								class="hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
								onclick={() => window.location.href = `/programs/${program.id}`}
							>
								<td class="px-6 py-4">
									<div class="text-sm font-medium text-gray-900 dark:text-gray-100">{program.name || 'Unnamed'}</div>
									{#if program.description}
										<div class="text-xs text-gray-400 mt-0.5">{program.description}</div>
									{/if}
								</td>
								<td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-400 text-right">{program.revision_count}</td>
								<td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-400 text-right">{program.latest_revision?.activity_count ?? '-'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{:else}
		<!-- Raw uploads view with sortable columns -->
		{#if filteredProjects.length === 0}
			<p class="text-sm text-gray-500 dark:text-gray-400 py-8 text-center">No projects match "{search}"</p>
		{:else}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
								<button class="inline-flex items-center gap-1 hover:text-gray-700 dark:text-gray-300" onclick={() => toggleSort('name')}>
									Project Name <span class="text-blue-500">{sortIcon('name')}</span>
								</button>
							</th>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Project ID</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
								<button class="inline-flex items-center gap-1 hover:text-gray-700 dark:text-gray-300" onclick={() => toggleSort('activities')}>
									Activities <span class="text-blue-500">{sortIcon('activities')}</span>
								</button>
							</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
								<button class="inline-flex items-center gap-1 hover:text-gray-700 dark:text-gray-300" onclick={() => toggleSort('relationships')}>
									Relationships <span class="text-blue-500">{sortIcon('relationships')}</span>
								</button>
							</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Quick Links</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each filteredProjects as project}
							<tr
								class="hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
								onclick={() => window.location.href = `/projects/${project.project_id}`}
							>
								<td class="px-6 py-4 text-sm font-medium text-gray-900 dark:text-gray-100">{project.name || 'Unnamed'}</td>
								<td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{project.project_id}</td>
								<td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-400 text-right">{project.activity_count}</td>
								<td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-400 text-right">{project.relationship_count}</td>
								<td class="px-6 py-4 text-right" onclick={(e) => e.stopPropagation()}>
									<div class="flex items-center justify-end gap-1">
										<a href="/schedule?project={project.project_id}" class="px-1.5 py-0.5 text-[10px] text-teal-600 hover:bg-teal-50 rounded" title="Schedule">Gantt</a>
										<a href="/scorecard?project={project.project_id}" class="px-1.5 py-0.5 text-[10px] text-blue-600 hover:bg-blue-50 dark:bg-blue-950 rounded" title="Scorecard">Score</a>
										<a href="/anomalies?project={project.project_id}" class="px-1.5 py-0.5 text-[10px] text-amber-600 hover:bg-amber-50 dark:bg-amber-950 rounded" title="Anomalies">Anom</a>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="mt-2 text-xs text-gray-400 text-right">{filteredProjects.length} of {projects.length} projects</p>
		{/if}
	{/if}
</div>
