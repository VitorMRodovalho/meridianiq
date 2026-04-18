<script lang="ts">
	import { onMount } from 'svelte';
	import { getProjects, getTimelines, createTimeline } from '$lib/api';
	import type { ProjectListItem, TimelineSummarySchema, TimelineDetailSchema } from '$lib/types';
	import { error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';

	let projects: ProjectListItem[] = $state([]);
	let timelines: TimelineSummarySchema[] = $state([]);
	let selectedIds: string[] = $state([]);
	let loading = $state(false);
	let projectsLoading = $state(true);
	let error = $state('');
	let showCreate = $state(false);

	onMount(async () => {
		try {
			const [projRes, tlRes] = await Promise.all([getProjects(), getTimelines()]);
			projects = projRes.projects;
			timelines = tlRes.timelines;
		} catch {
			error = $t('forensic.load_failed');
			toastError(error);
		} finally {
			projectsLoading = false;
		}
	});

	function toggleProject(id: string) {
		if (selectedIds.includes(id)) {
			selectedIds = selectedIds.filter((x) => x !== id);
		} else {
			selectedIds = [...selectedIds, id];
		}
	}

	async function doCreate() {
		if (selectedIds.length < 2) {
			error = $t('forensic.need_two_selected');
			return;
		}
		loading = true;
		error = '';
		try {
			const result: TimelineDetailSchema = await createTimeline(selectedIds);
			window.location.href = `/forensic/${result.timeline_id}`;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : $t('forensic.create_failed');
			toastError(error);
		} finally {
			loading = false;
		}
	}

	function formatDate(d: string | null): string {
		if (!d) return '-';
		return new Date(d).toLocaleDateString();
	}
</script>

<svelte:head>
	<title>{$t('page.forensic')} - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-7xl mx-auto">
	<div class="flex items-center justify-between mb-6">
		<div>
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.forensic')}</h1>
			<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
				{$t('forensic.subtitle')}
			</p>
		</div>
		<button
			onclick={() => (showCreate = !showCreate)}
			class="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors"
		>
			{showCreate ? $t('forensic.btn_cancel') : $t('forensic.btn_new')}
		</button>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 text-sm text-red-700 mb-6">
			{error}
		</div>
	{/if}

	{#if showCreate}
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{$t('forensic.create_title')}</h2>
			<p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
				{$t('forensic.create_description')}
			</p>
			{#if projectsLoading}
				<p class="text-gray-500 dark:text-gray-400">{$t('forensic.loading_projects')}</p>
			{:else if projects.length < 2}
				<p class="text-gray-500 dark:text-gray-400">
					{$t('forensic.need_two_uploads')}
				</p>
				<a href="/upload" class="mt-3 inline-block text-sm text-blue-600 hover:underline"
					>{$t('projects.upload_cta')}</a
				>
			{:else}
				<div class="space-y-2 max-h-64 overflow-y-auto mb-4">
					{#each projects as p}
						<label
							class="flex items-center gap-3 px-3 py-2 rounded-md border cursor-pointer transition-colors {selectedIds.includes(
								p.project_id
							)
								? 'border-blue-500 bg-blue-50 dark:bg-blue-950'
								: 'border-gray-200 dark:border-gray-700 hover:border-gray-300'}"
						>
							<input
								type="checkbox"
								checked={selectedIds.includes(p.project_id)}
								onchange={() => toggleProject(p.project_id)}
								class="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
							/>
							<div class="flex-1">
								<span class="text-sm font-medium text-gray-900 dark:text-gray-100"
									>{p.name || p.project_id}</span
								>
								<span class="text-xs text-gray-500 dark:text-gray-400 ml-2"
									>({p.activity_count} {$t('forensic.activities_suffix')})</span
								>
							</div>
							<span class="text-xs font-mono text-gray-400">{p.project_id}</span>
						</label>
					{/each}
				</div>
				<div class="flex items-center gap-4">
					<button
						onclick={doCreate}
						disabled={loading || selectedIds.length < 2}
						class="bg-blue-600 text-white px-6 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
					>
						{loading ? $t('forensic.btn_analyzing') : $t('forensic.btn_analyze_count').replace('{n}', String(selectedIds.length))}
					</button>
					<span class="text-xs text-gray-500 dark:text-gray-400">{selectedIds.length} {$t('forensic.count_selected')}</span>
						{#if selectedIds.length >= 2}
							<a href="/schedule?project={selectedIds[selectedIds.length - 1]}&baseline={selectedIds[0]}" class="text-xs text-teal-600 hover:text-teal-800 font-medium ml-2">{$t('forensic.view_schedule_baseline')}</a>
						{/if}
				</div>
			{/if}
		</div>
	{/if}

	<!-- Existing Timelines -->
	{#if timelines.length > 0}
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg">
			<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{$t('forensic.timelines_title')}</h2>
			</div>
			<div class="overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200 text-sm">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th
								class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase"
								>{$t('forensic.col_timeline')}</th
							>
							<th
								class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase"
								>{$t('common.project')}</th
							>
							<th
								class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase"
								>{$t('forensic.col_schedules')}</th
							>
							<th
								class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase"
								>{$t('forensic.col_windows')}</th
							>
							<th
								class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase"
								>{$t('forensic.col_total_delay')}</th
							>
							<th class="px-4 py-3"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each timelines as tl}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
								<td class="px-4 py-3 font-mono text-gray-900 dark:text-gray-100">{tl.timeline_id}</td>
								<td class="px-4 py-3 text-gray-700 dark:text-gray-300">{tl.project_name}</td>
								<td class="px-4 py-3 text-right text-gray-500 dark:text-gray-400"
									>{tl.schedule_count}</td
								>
								<td class="px-4 py-3 text-right text-gray-500 dark:text-gray-400"
									>{tl.window_count}</td
								>
								<td
									class="px-4 py-3 text-right font-medium {tl.total_delay_days > 0
										? 'text-red-600'
										: tl.total_delay_days < 0
											? 'text-green-600'
											: 'text-gray-500 dark:text-gray-400'}"
								>
									{tl.total_delay_days > 0 ? '+' : ''}{tl.total_delay_days.toFixed(
										0
									)}d
								</td>
								<td class="px-4 py-3 text-right">
									<a
										href="/forensic/{tl.timeline_id}"
										class="text-blue-600 hover:underline text-sm"
									>
										{$t('forensic.btn_view')}
									</a>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{:else if !projectsLoading && !showCreate}
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-12 text-center">
			<svg
				class="mx-auto h-12 w-12 text-gray-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
				/>
			</svg>
			<h3 class="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">{$t('forensic.empty_title')}</h3>
			<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
				{$t('forensic.empty_hint')}
			</p>
		</div>
	{/if}
</div>
