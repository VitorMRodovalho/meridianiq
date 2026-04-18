<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getProjects,
		validateRecovery,
		type RecoveryValidationResult
	} from '$lib/api';
	import { t } from '$lib/i18n';
	import type { ProjectListItem } from '$lib/types';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import GaugeChart from '$lib/components/charts/GaugeChart.svelte';
	import PieChart from '$lib/components/charts/PieChart.svelte';

	let projects: ProjectListItem[] = $state([]);
	let loading = $state(true);
	let error = $state('');
	let impactedId = $state('');
	let recoveryId = $state('');
	let validating = $state(false);
	let result: RecoveryValidationResult | null = $state(null);

	onMount(async () => {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch {
			error = $t('recovery.load_failed');
		} finally {
			loading = false;
		}
	});

	async function runValidation() {
		if (!impactedId || !recoveryId) return;
		validating = true;
		error = '';
		result = null;
		try {
			result = await validateRecovery(impactedId, recoveryId);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : $t('recovery.validation_failed');
		} finally {
			validating = false;
		}
	}

	function verdictColor(v: string): string {
		if (v === 'acceptable') return 'text-green-700 bg-green-50 dark:bg-green-950 border-green-200';
		if (v === 'questionable') return 'text-yellow-700 bg-yellow-50 dark:bg-yellow-950 border-yellow-200';
		return 'text-red-700 bg-red-50 dark:bg-red-950 border-red-200';
	}

	function severityColor(s: string): string {
		if (s === 'critical') return 'bg-red-100 text-red-800';
		if (s === 'warning') return 'bg-yellow-100 text-yellow-800';
		return 'bg-blue-100 text-blue-800';
	}

	function scoreColor(score: number): string {
		if (score >= 70) return 'text-green-600';
		if (score >= 40) return 'text-yellow-600';
		return 'text-red-600';
	}
</script>

<svelte:head>
	<title>{$t('page.recovery')} - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.recovery')}</h1>
		<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
			{$t('recovery.subtitle')}
		</p>
	</div>

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400 py-12 justify-center">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			{$t('common.loading')}
		</div>
	{:else}
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-8">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{$t('recovery.select_title')}</h2>
			<div class="grid grid-cols-1 md:grid-cols-2 gap-6">
				<label class="block">
					<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$t('recovery.label_impacted')}</span>
					<select bind:value={impactedId} class="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm">
						<option value="">{$t('recovery.select_impacted')}</option>
						{#each projects as p}
							<option value={p.project_id}>{p.name || p.project_id} ({p.activity_count} {$t('recovery.act_suffix')})</option>
						{/each}
					</select>
				</label>
				<label class="block">
					<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$t('recovery.label_recovery')}</span>
					<select bind:value={recoveryId} class="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm">
						<option value="">{$t('recovery.select_recovery')}</option>
						{#each projects.filter(p => p.project_id !== impactedId) as p}
							<option value={p.project_id}>{p.name || p.project_id} ({p.activity_count} {$t('recovery.act_suffix')})</option>
						{/each}
					</select>
				</label>
			</div>
			<div class="mt-4">
				<button
					onclick={runValidation}
					disabled={!impactedId || !recoveryId || validating}
					class="px-6 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
				>
					{validating ? $t('recovery.btn_validating') : $t('recovery.btn_validate')}
				</button>
			</div>
		</div>

		{#if loading}
		<AnalysisSkeleton />
	{:else if error}
			<div class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg text-red-700 text-sm mb-8">{error}</div>
		{/if}

		{#if result}
			<!-- Summary -->
			<div class="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-8">
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
					<p class="text-3xl font-bold {scoreColor(result.validation_score)}">{result.validation_score}</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('recovery.stat_score')}</p>
				</div>
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
					<p class="text-3xl font-bold text-gray-900 dark:text-gray-100">{result.total_duration_reduction_pct}%</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('recovery.stat_reduction')}</p>
				</div>
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
					<p class="text-3xl font-bold text-orange-600">{result.activities_compressed}</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('recovery.stat_compressed')}</p>
				</div>
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
					<p class="text-3xl font-bold text-red-600">{result.critical_count}</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('recovery.stat_critical')}</p>
				</div>
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
					<p class="text-3xl font-bold text-yellow-600">{result.warning_count}</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('recovery.stat_warnings')}</p>
				</div>
			</div>

			<!-- Validation Charts -->
			<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
				<GaugeChart
					value={result.validation_score}
					title={$t('recovery.gauge_title')}
					label={result.verdict.toUpperCase()}
					size={200}
					bands={[
						{ threshold: 40, color: '#ef4444' },
						{ threshold: 70, color: '#f59e0b' },
						{ threshold: 100, color: '#10b981' },
					]}
				/>
				{#if result.critical_count > 0 || result.warning_count > 0}
					<PieChart
						title={$t('recovery.pie_title')}
						size={170}
						data={[
							{ label: $t('common.critical'), value: result.critical_count, color: '#ef4444' },
							{ label: $t('common.warning'), value: result.warning_count, color: '#f59e0b' },
						]}
					/>
				{/if}
			</div>

			<!-- Verdict -->
			<div class="p-4 rounded-lg border mb-8 {verdictColor(result.verdict)}">
				<p class="text-lg font-semibold">
					{$t('recovery.verdict_label')} {result.verdict.charAt(0).toUpperCase() + result.verdict.slice(1)}
				</p>
				<p class="text-sm mt-1">
					{#if result.verdict === 'acceptable'}
						{$t('recovery.verdict_acceptable_msg')}
					{:else if result.verdict === 'questionable'}
						{$t('recovery.verdict_questionable_msg')}
					{:else}
						{$t('recovery.verdict_unreasonable_msg')}
					{/if}
				</p>
			</div>

			<!-- Issues -->
			{#if result.issues.length > 0}
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden mb-8">
					<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
						<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{$t('recovery.issues_title')} ({result.issues.length})</h2>
					</div>
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('recovery.col_severity')}</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('recovery.col_category')}</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('recovery.col_activity')}</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('recovery.col_description')}</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each result.issues as issue}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="px-4 py-2">
										<span class="px-2 py-0.5 text-xs font-medium rounded-full {severityColor(issue.severity)}">{issue.severity}</span>
									</td>
									<td class="px-4 py-2 text-gray-600 dark:text-gray-400">{issue.category}</td>
									<td class="px-4 py-2 font-mono text-gray-700 dark:text-gray-300">{issue.task_code}</td>
									<td class="px-4 py-2 text-gray-600 dark:text-gray-400">{issue.description}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<div class="p-4 bg-green-50 dark:bg-green-950 border border-green-200 rounded-lg text-green-700 text-sm text-center mb-8">
					{$t('recovery.all_pass')}
				</div>
			{/if}
		{/if}
	{/if}
</div>
