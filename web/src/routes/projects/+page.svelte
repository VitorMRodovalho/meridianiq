<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { getProjects, getPrograms, MAX_PLACEMENT_PROJECT_IDS } from '$lib/api';
	import { success } from '$lib/toast';
	import MoveToProgramDialog from '$lib/components/MoveToProgramDialog.svelte';
	import { t } from '$lib/i18n';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
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

	// Schedules picked in the uploads view, to move into one program.
	let selected: string[] = $state([]);
	let moveOpen = $state(false);
	let selectionStatus: HTMLParagraphElement | null = $state(null);

	function toggleSelected(id: string): void {
		selected = selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id];
	}

	async function handleMoved(moved: { programName: string; count: number }): Promise<void> {
		moveOpen = false;
		selected = [];
		success(
			moved.count === 1
				? $t('move.done_one').replace('{name}', moved.programName)
				: $t('move.done_many')
						.replace('{n}', String(moved.count))
						.replace('{name}', moved.programName)
		);
		await load();
		// The opener is disabled now that nothing is selected, so focus the
		// selection line instead of letting it fall to the page.
		await tick();
		selectionStatus?.focus();
	}

	/** Reload after a move, so the lists show what actually moved. */
	async function load(): Promise<void> {
		try {
			const [projRes, progRes] = await Promise.all([
				getProjects(),
				getPrograms().catch(() => ({ programs: [] }))
			]);
			projects = projRes.projects;
			programs = progRes.programs;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : $t('projects.load_failed');
		}
	}

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
			error = e instanceof Error ? e.message : $t('projects.load_failed');
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

	const allShownSelected = $derived(
		filteredProjects.length > 0 && filteredProjects.every((p) => selected.includes(p.project_id))
	);
	const someShownSelected = $derived(
		filteredProjects.some((p) => selected.includes(p.project_id))
	);
	// Selected schedules the search hides; Move still moves them.
	const hiddenSelected = $derived.by(() => {
		const shown = new Set(filteredProjects.map((p) => p.project_id));
		return selected.filter((id) => !shown.has(id)).length;
	});

	const programNames = $derived(new Map(programs.map((p) => [p.id, p.name])));

	function toggleAllShown(): void {
		const shown = filteredProjects.map((p) => p.project_id);
		selected = allShownSelected
			? selected.filter((id) => !shown.includes(id))
			: [...new Set([...selected, ...shown])];
	}

	const sortIcon = $derived((col: string) => {
		if (sortBy !== col) return '';
		return sortDir === 'asc' ? '\u2191' : '\u2193';
	});
</script>

<svelte:head>
	<title>{$t('nav.projects')} - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('nav.projects')}</h1>
		{#if programs.length > 0 && projects.length > 0}
			<div class="flex bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
				<button
					class="px-3 py-1 text-sm rounded-md transition-colors {viewMode === 'programs' ? 'bg-white dark:bg-gray-900 shadow text-gray-900 dark:text-gray-100 font-medium' : 'text-gray-500 hover:text-gray-700'}"
					onclick={() => viewMode = 'programs'}
				>
					{$t('projects.view_programs')}
				</button>
				<button
					class="px-3 py-1 text-sm rounded-md transition-colors {viewMode === 'uploads' ? 'bg-white dark:bg-gray-900 shadow text-gray-900 dark:text-gray-100 font-medium' : 'text-gray-500 hover:text-gray-700'}"
					onclick={() => viewMode = 'uploads'}
				>
					{$t('projects.view_uploads')}
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
					placeholder={$t('projects.search_placeholder')}
					class="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
				/>
				{#if search}
					<button
						onclick={() => search = ''}
						class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:text-gray-400"
						aria-label={$t('projects.clear_search')}
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
			{$t('projects.loading')}
		</div>
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 text-sm text-red-700">{error}</div>
	{:else if projects.length === 0 && programs.length === 0}
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
			<p class="text-gray-500 dark:text-gray-400 mb-4">{$t('projects.empty_title')}</p>
			<a
				href="/upload"
				class="inline-block bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700"
			>
				{$t('projects.upload_cta')}
			</a>
		</div>
	{:else if viewMode === 'programs'}
		<!-- Programs view -->
		{#if filteredPrograms.length === 0}
			<p class="text-sm text-gray-500 dark:text-gray-400 py-8 text-center">{$t('projects.no_programs_match')} "{search}"</p>
		{:else}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{$t('projects.col_program')}</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{$t('projects.col_revisions')}</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{$t('projects.col_latest_activities')}</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each filteredPrograms as program}
							<tr
								class="hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
								onclick={() => window.location.href = `/programs/${program.id}`}
							>
								<td class="px-6 py-4">
									<a
										href="/programs/{program.id}"
										onclick={(e) => e.stopPropagation()}
										class="text-sm font-medium text-gray-900 dark:text-gray-100 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
									>{program.name || $t('projects.unnamed')}</a>
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
			<p class="text-sm text-gray-500 dark:text-gray-400 py-8 text-center">{$t('projects.no_match')} "{search}"</p>
		{:else}
			<div class="mb-3 flex flex-col sm:flex-row sm:items-center gap-2 text-sm">
				<p
					bind:this={selectionStatus}
					tabindex="-1"
					aria-live="polite"
					class="text-gray-600 dark:text-gray-400 focus:outline-none"
				>
					{$t('move.selected').replace('{n}', String(selected.length))}{#if hiddenSelected > 0}
						<span class="text-amber-700 dark:text-amber-300">
							· {$t('move.hidden_selected').replace('{n}', String(hiddenSelected))}</span
						>{/if}
				</p>
				<button
					type="button"
					onclick={() => (moveOpen = true)}
					disabled={selected.length === 0 || selected.length > MAX_PLACEMENT_PROJECT_IDS}
					class="self-start px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500"
				>
					{$t('move.move_selected')}
				</button>
				{#if selected.length > MAX_PLACEMENT_PROJECT_IDS}
					<span class="text-amber-700 dark:text-amber-300">
						{$t('move.too_many').replace('{n}', String(MAX_PLACEMENT_PROJECT_IDS))}
					</span>
				{/if}
			</div>
			{#if moveOpen}
				<MoveToProgramDialog
					projectIds={selected}
					onClose={() => (moveOpen = false)}
					onMoved={handleMoved}
					onFailed={() => void load()}
				/>
			{/if}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="pl-4 pr-2 py-3 text-left">
								<input
									type="checkbox"
									checked={allShownSelected}
									indeterminate={someShownSelected && !allShownSelected}
									onchange={toggleAllShown}
									aria-label={$t('move.select_all')}
									class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
								/>
							</th>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
								<button class="inline-flex items-center gap-1 hover:text-gray-700 dark:text-gray-300" onclick={() => toggleSort('name')}>
									{$t('projects.col_project_name')} <span class="text-blue-500">{sortIcon('name')}</span>
								</button>
							</th>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{$t('projects.col_program')}</th>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{$t('projects.col_project_id')}</th>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{$t('projects.col_status')}</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
								<button class="inline-flex items-center gap-1 hover:text-gray-700 dark:text-gray-300" onclick={() => toggleSort('activities')}>
									{$t('projects.col_activities')} <span class="text-blue-500">{sortIcon('activities')}</span>
								</button>
							</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
								<button class="inline-flex items-center gap-1 hover:text-gray-700 dark:text-gray-300" onclick={() => toggleSort('relationships')}>
									{$t('projects.col_relationships')} <span class="text-blue-500">{sortIcon('relationships')}</span>
								</button>
							</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('projects.col_quick_links')}</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each filteredProjects as project}
							<tr
								class="hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"
								onclick={() => window.location.href = `/projects/${project.project_id}`}
							>
								<td class="pl-4 pr-2 py-4" onclick={(e) => e.stopPropagation()}>
									<input
										type="checkbox"
										checked={selected.includes(project.project_id)}
										onchange={() => toggleSelected(project.project_id)}
										aria-label={$t('move.select_row').replace('{name}', project.name || project.project_id)}
										class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
									/>
								</td>
								<td class="px-6 py-4 text-sm font-medium text-gray-900 dark:text-gray-100">
									<a
										href="/projects/{project.project_id}"
										onclick={(e) => e.stopPropagation()}
										class="hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
									>{project.name || $t('projects.unnamed')}</a>
								</td>
								<td class="px-6 py-4 text-sm text-gray-700 dark:text-gray-300" onclick={(e) => e.stopPropagation()}>
									{#if project.program_id}
										<a
											href="/programs/{project.program_id}"
											class="hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
										>{programNames.get(project.program_id) ?? $t('move.view_program')}</a>
									{:else}
										<span class="text-gray-400 dark:text-gray-500">{$t('move.no_program')}</span>
									{/if}
								</td>
								<td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{project.project_id}</td>
								<td class="px-6 py-4 text-sm">
									<StatusBadge status={project.status ?? 'ready'} />
								</td>
								<td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-400 text-right">{project.activity_count}</td>
								<td class="px-6 py-4 text-sm text-gray-500 dark:text-gray-400 text-right">{project.relationship_count}</td>
								<td class="px-6 py-4 text-right" onclick={(e) => e.stopPropagation()}>
									<div class="flex items-center justify-end gap-1">
										<a href="/schedule?project={project.project_id}" class="px-1.5 py-0.5 text-[10px] text-teal-600 hover:bg-teal-50 rounded" title={$t('nav.gantt')}>{$t('projects.quick_gantt')}</a>
										<a href="/scorecard?project={project.project_id}" class="px-1.5 py-0.5 text-[10px] text-blue-600 hover:bg-blue-50 dark:bg-blue-950 rounded" title={$t('nav.scorecard')}>{$t('projects.quick_score')}</a>
										<a href="/anomalies?project={project.project_id}" class="px-1.5 py-0.5 text-[10px] text-amber-600 hover:bg-amber-50 dark:bg-amber-950 rounded" title={$t('nav.anomalies')}>{$t('projects.quick_anom')}</a>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="mt-2 text-xs text-gray-400 text-right">{filteredProjects.length} / {projects.length}</p>
		{/if}
	{/if}
</div>
