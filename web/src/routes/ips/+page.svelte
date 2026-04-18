<script lang="ts">
	import { onMount } from 'svelte';
	import { getProjects, reconcileIPS, type IPSReconciliationResult } from '$lib/api';
	import { t } from '$lib/i18n';
	import type { ProjectListItem } from '$lib/types';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import GaugeChart from '$lib/components/charts/GaugeChart.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';

	let projects: ProjectListItem[] = $state([]);
	let loading = $state(true);
	let error = $state('');
	let masterProjectId = $state('');
	let subProjectIds: string[] = $state([]);
	let reconciling = $state(false);
	let result: IPSReconciliationResult | null = $state(null);

	onMount(async () => {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch {
			error = $t('ips.load_failed');
		} finally {
			loading = false;
		}
	});

	function toggleSub(pid: string) {
		if (subProjectIds.includes(pid)) {
			subProjectIds = subProjectIds.filter(id => id !== pid);
		} else {
			subProjectIds = [...subProjectIds, pid];
		}
	}

	async function runReconciliation() {
		if (!masterProjectId || subProjectIds.length === 0) return;
		reconciling = true;
		error = '';
		result = null;

		try {
			result = await reconcileIPS(masterProjectId, subProjectIds);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : $t('ips.reconciliation_failed');
		} finally {
			reconciling = false;
		}
	}

	function statusColor(status: string): string {
		if (status === 'aligned') return 'text-green-700 bg-green-50 dark:bg-green-950 border-green-200';
		if (status === 'minor_discrepancies') return 'text-yellow-700 bg-yellow-50 dark:bg-yellow-950 border-yellow-200';
		return 'text-red-700 bg-red-50 dark:bg-red-950 border-red-200';
	}

	function severityColor(s: string): string {
		if (s === 'critical') return 'bg-red-100 text-red-800';
		if (s === 'warning') return 'bg-yellow-100 text-yellow-800';
		return 'bg-blue-100 text-blue-800';
	}

	function scoreColor(score: number): string {
		if (score >= 85) return 'text-green-600';
		if (score >= 70) return 'text-yellow-600';
		return 'text-red-600';
	}
</script>

<svelte:head>
	<title>{$t('page.ips')} - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.ips')}</h1>
		<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
			{$t('ips.subtitle')}
		</p>
	</div>

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400 py-12 justify-center">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			{$t('ips.loading_projects')}
		</div>
	{:else}
		<!-- Setup -->
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-8">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{$t('ips.select_title')}</h2>

			{#if projects.length < 2}
				<div class="p-4 bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 rounded-lg text-yellow-800 text-sm">
					{$t('ips.need_two_prefix')} <a href="/upload" class="underline font-medium">{$t('ips.need_two_link')}</a>.
				</div>
			{:else}
				<div class="grid grid-cols-1 md:grid-cols-2 gap-6">
					<div>
						<label class="block">
							<span class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">{$t('ips.label_master')}</span>
							<select bind:value={masterProjectId} class="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm">
								<option value="">{$t('ips.select_master')}</option>
								{#each projects as p}
									<option value={p.project_id}>{p.name || p.project_id} ({p.activity_count} {$t('ips.act_suffix')})</option>
								{/each}
							</select>
						</label>
					</div>
					<div>
						<span class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">{$t('ips.label_subs')} ({subProjectIds.length} {$t('ips.subs_selected')})</span>
						<div class="max-h-48 overflow-y-auto border border-gray-300 dark:border-gray-600 rounded-lg p-2 space-y-1">
							{#each projects.filter(p => p.project_id !== masterProjectId) as p}
								<label class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer">
									<input
										type="checkbox"
										checked={subProjectIds.includes(p.project_id)}
										onchange={() => toggleSub(p.project_id)}
										class="rounded border-gray-300 dark:border-gray-600 text-blue-600"
									/>
									<span class="text-sm text-gray-700 dark:text-gray-300">{p.name || p.project_id}</span>
									<span class="text-xs text-gray-400 ml-auto">{p.activity_count} {$t('ips.act_suffix')}</span>
								</label>
							{/each}
						</div>
					</div>
				</div>
				<div class="mt-4">
					<button
						onclick={runReconciliation}
						disabled={!masterProjectId || subProjectIds.length === 0 || reconciling}
						class="px-6 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
					>
						{reconciling ? $t('ips.btn_reconciling') : $t('ips.btn_reconcile')}
					</button>
				</div>
			{/if}
		</div>

		{#if loading}
		<AnalysisSkeleton />
	{:else if error}
			<div class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg text-red-700 text-sm mb-8">{error}</div>
		{/if}

		<!-- Results -->
		{#if result}
			<!-- Summary -->
			<div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
					<p class="text-3xl font-bold {scoreColor(result.overall_alignment_score)}">{result.overall_alignment_score}</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('ips.stat_alignment')}</p>
				</div>
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
					<p class="text-3xl font-bold text-gray-900 dark:text-gray-100">{result.sub_count}</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('ips.stat_subs')}</p>
				</div>
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
					<p class="text-3xl font-bold text-red-600">{result.critical_issues}</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('ips.stat_critical')}</p>
				</div>
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
					<p class="text-3xl font-bold text-yellow-600">{result.warning_issues}</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('ips.stat_warnings')}</p>
				</div>
			</div>

			<!-- Alignment Charts -->
			<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
				<GaugeChart
					value={result.overall_alignment_score}
					title={$t('ips.gauge_title')}
					label={result.reconciliation_status === 'aligned' ? $t('ips.status_aligned_label') : result.reconciliation_status === 'minor_discrepancies' ? $t('ips.status_minor_label') : $t('ips.status_major_label')}
					size={200}
				/>
				{#if result.sub_results && result.sub_results.length > 1}
					<BarChart
						title={$t('ips.comparison_chart_title')}
						horizontal={true}
						height={Math.max(160, result.sub_results.length * 36)}
						data={result.sub_results.map((s) => ({
							label: s.sub_name || 'Sub',
							value: s.alignment_score,
							color: s.alignment_score >= 85 ? '#10b981' : s.alignment_score >= 70 ? '#3b82f6' : s.alignment_score >= 50 ? '#f59e0b' : '#ef4444',
						}))}
						formatValue={(v) => v.toFixed(0)}
					/>
				{/if}
			</div>

			<!-- Status banner -->
			<div class="p-4 rounded-lg border mb-8 {statusColor(result.reconciliation_status)}">
				<p class="font-semibold">
					{#if result.reconciliation_status === 'aligned'}
						{$t('ips.status_aligned_msg')}
					{:else if result.reconciliation_status === 'minor_discrepancies'}
						{$t('ips.status_minor_msg')}
					{:else}
						{$t('ips.status_major_msg')}
					{/if}
				</p>
			</div>

			<!-- Per sub-schedule results -->
			{#each result.sub_results as sub}
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg mb-6">
					<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
						<div>
							<h3 class="font-semibold text-gray-900 dark:text-gray-100">{sub.sub_name}</h3>
							<p class="text-xs text-gray-500 dark:text-gray-400">{sub.sub_activity_count} {$t('ips.sub_activities_suffix')} &middot; {sub.matched_milestones} {$t('ips.sub_milestones_suffix')} &middot; {sub.issues.length} {$t('ips.sub_issues_suffix')}</p>
						</div>
						<div class="text-2xl font-bold {scoreColor(sub.alignment_score)}">{sub.alignment_score}</div>
					</div>
					{#if sub.issues.length > 0}
						<div class="overflow-x-auto">
							<table class="min-w-full divide-y divide-gray-200 text-sm">
								<thead class="bg-gray-50 dark:bg-gray-800">
									<tr>
										<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('ips.col_severity')}</th>
										<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('ips.col_category')}</th>
										<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('ips.col_activity')}</th>
										<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('ips.col_description')}</th>
										<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('ips.col_delta')}</th>
									</tr>
								</thead>
								<tbody class="divide-y divide-gray-200">
									{#each sub.issues as issue}
										<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
											<td class="px-4 py-2">
												<span class="px-2 py-0.5 text-xs font-medium rounded-full {severityColor(issue.severity)}">{issue.severity}</span>
											</td>
											<td class="px-4 py-2 text-gray-600 dark:text-gray-400">{issue.category}</td>
											<td class="px-4 py-2 font-mono text-gray-700 dark:text-gray-300">{issue.master_activity}</td>
											<td class="px-4 py-2 text-gray-600 dark:text-gray-400">{issue.description}</td>
											<td class="px-4 py-2 font-mono text-gray-700 dark:text-gray-300">{issue.delta || '-'}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{:else}
						<div class="px-6 py-4 text-center text-green-600 text-sm">{$t('ips.no_issues')}</div>
					{/if}
				</div>
			{/each}
		{/if}
	{/if}
</div>
