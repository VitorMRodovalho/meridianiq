<script lang="ts">
	import { getPrograms } from '$lib/api';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { onMount } from 'svelte';

	let programs: any[] = $state([]);
	let loading = $state(true);
	let error = $state('');

	onMount(async () => {
		try {
			const res = await getPrograms();
			programs = res.programs || [];
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load programs';
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head>
	<title>Programs | MeridianIQ</title>
</svelte:head>

<main class="max-w-7xl mx-auto px-4 py-8">
	<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-1">Programs</h1>
	<p class="text-sm text-gray-500 dark:text-gray-400 mb-6">Schedule revision groups — track updates across the project lifecycle</p>

	{#if loading}
		<AnalysisSkeleton cards={3} showChart={false} />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm">{error}</div>
	{:else if programs.length === 0}
		<div class="text-center py-12 text-gray-400 dark:text-gray-600">
			<p class="text-lg mb-2">No programs yet</p>
			<p class="text-sm">Upload multiple schedule revisions to create a program</p>
			<a href="/upload" class="inline-block mt-4 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700">Upload Schedule</a>
		</div>
	{:else}
		<div class="grid gap-4">
			{#each programs as prog}
				<a href="/programs/{prog.program_id || prog.id}" class="block bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:border-blue-300 dark:hover:border-blue-700 transition-colors">
					<div class="flex items-center justify-between">
						<div>
							<h3 class="font-semibold text-gray-900 dark:text-gray-100">{prog.name || prog.program_id || 'Unnamed Program'}</h3>
							{#if prog.description}
								<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{prog.description}</p>
							{/if}
						</div>
						<div class="text-right text-sm">
							{#if prog.revision_count}
								<span class="px-2 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded-full text-xs font-medium">{prog.revision_count} revisions</span>
							{/if}
						</div>
					</div>
				</a>
			{/each}
		</div>
	{/if}
</main>
