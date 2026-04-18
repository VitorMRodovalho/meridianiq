<script lang="ts">
	import { onMount } from 'svelte';
	import { getContractProvisions, contractCheck, getTIAAnalyses } from '$lib/api';
	import PieChart from '$lib/components/charts/PieChart.svelte';
	import type {
		ContractProvisionsResponse,
		ContractCheckResponse,
		ComplianceCheckSchema,
		TIAAnalysisSummarySchema
	} from '$lib/types';
	import { error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';

	let provisions: ContractProvisionsResponse | null = $state(null);
	let analyses: TIAAnalysisSummarySchema[] = $state([]);
	let checkResult: ContractCheckResponse | null = $state(null);
	let loading = $state(true);
	let checking = $state(false);
	let error = $state('');
	let selectedAnalysisId = $state('');

	onMount(async () => {
		try {
			const [provRes, tiaRes] = await Promise.all([
				getContractProvisions(),
				getTIAAnalyses()
			]);
			provisions = provRes;
			analyses = tiaRes.analyses;
		} catch {
			error = $t('contract.load_failed');
			toastError(error);
		} finally {
			loading = false;
		}
	});

	async function runCheck() {
		if (!selectedAnalysisId) return;
		checking = true;
		error = '';
		checkResult = null;
		try {
			checkResult = await contractCheck(selectedAnalysisId);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : $t('contract.check_failed');
			toastError(error);
		} finally {
			checking = false;
		}
	}

	function statusColor(status: string): string {
		if (status === 'pass' || status === 'compliant') return 'text-green-700 bg-green-50 dark:bg-green-950 border-green-200';
		if (status === 'warning') return 'text-yellow-700 bg-yellow-50 dark:bg-yellow-950 border-yellow-200';
		if (status === 'fail' || status === 'non_compliant') return 'text-red-700 bg-red-50 dark:bg-red-950 border-red-200';
		return 'text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700';
	}

	function statusBadge(status: string): string {
		if (status === 'pass' || status === 'compliant') return 'bg-green-100 text-green-800';
		if (status === 'warning') return 'bg-yellow-100 text-yellow-800';
		if (status === 'fail' || status === 'non_compliant') return 'bg-red-100 text-red-800';
		return 'bg-gray-100 dark:bg-gray-800 text-gray-800';
	}

	function categoryIcon(category: string): string {
		if (category.toLowerCase().includes('time')) return 'clock';
		if (category.toLowerCase().includes('notice')) return 'bell';
		if (category.toLowerCase().includes('change')) return 'refresh';
		return 'shield';
	}
</script>

<svelte:head>
	<title>{$t('page.contract')} - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-7xl mx-auto">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.contract')}</h1>
		<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
			{$t('contract.subtitle')}
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
	{:else if error && !checkResult}
		<div class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
	{:else}
		<!-- Run Compliance Check -->
		<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-8">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{$t('contract.run_title')}</h2>
			<p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
				{$t('contract.run_description')}
			</p>
			{#if analyses.length === 0}
				<div class="p-4 bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 rounded-lg text-yellow-800 text-sm">
					{$t('contract.no_tia_prefix')} <a href="/tia" class="underline font-medium">{$t('contract.no_tia_link')}</a> {$t('contract.no_tia_suffix')}
				</div>
			{:else}
				<div class="flex items-end gap-4">
					<label class="flex-1">
						<span class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('contract.label_analysis')}</span>
						<select
							bind:value={selectedAnalysisId}
							class="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						>
							<option value="">{$t('contract.select_analysis')}</option>
							{#each analyses as a}
								<option value={a.analysis_id}>{a.project_name} ({a.analysis_id})</option>
							{/each}
						</select>
					</label>
					<button
						onclick={runCheck}
						disabled={!selectedAnalysisId || checking}
						class="px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
					>
						{checking ? $t('contract.btn_checking') : $t('contract.btn_run')}
					</button>
				</div>
			{/if}
		</div>

		<!-- Check Results -->
		{#if checkResult}
			<div class="mb-8">
				<div class="grid grid-cols-3 gap-4 mb-6">
					<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4 text-center">
						<p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('contract.stat_total')}</p>
						<p class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{checkResult.total_checks}</p>
					</div>
					<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-yellow-200 p-4 text-center">
						<p class="text-xs font-medium text-yellow-600 uppercase">{$t('contract.stat_warnings')}</p>
						<p class="text-2xl font-bold text-yellow-600 mt-1">{checkResult.warnings}</p>
					</div>
					<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-red-200 p-4 text-center">
						<p class="text-xs font-medium text-red-600 uppercase">{$t('contract.stat_failures')}</p>
						<p class="text-2xl font-bold text-red-600 mt-1">{checkResult.failures}</p>
					</div>
				</div>

				<!-- Compliance Distribution Chart -->
				<div class="mb-6">
					<PieChart
						title={$t('contract.chart_title')}
						size={170}
						data={[
							{ label: $t('contract.chart_pass'), value: checkResult.total_checks - checkResult.warnings - checkResult.failures, color: '#10b981' },
							{ label: $t('contract.chart_warning'), value: checkResult.warnings, color: '#f59e0b' },
							{ label: $t('contract.chart_fail'), value: checkResult.failures, color: '#ef4444' },
						]}
					/>
				</div>

				{#if checkResult.checks.length > 0}
					<div class="space-y-3">
						{#each checkResult.checks as check}
							<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border p-4 {statusColor(check.status)}">
								<div class="flex items-start justify-between gap-4">
									<div class="flex-1">
										<div class="flex items-center gap-2 mb-1">
											<span class="text-sm font-semibold">{check.provision_name}</span>
											<span class="px-2 py-0.5 text-xs font-medium rounded-full {statusBadge(check.status)}">
												{check.status.toUpperCase()}
											</span>
											{#if check.provision_category}
												<span class="px-2 py-0.5 text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 rounded-full">
													{check.provision_category}
												</span>
											{/if}
										</div>
										<p class="text-sm text-gray-600 dark:text-gray-400 mb-1">
											<span class="font-medium">{$t('contract.fragment_label')}</span> {check.fragment_name} ({check.fragment_id})
										</p>
										{#if check.finding}
											<p class="text-sm mt-1">{check.finding}</p>
										{/if}
										{#if check.recommendation}
											<p class="text-xs text-gray-500 dark:text-gray-400 mt-1 italic">{$t('contract.recommendation_label')} {check.recommendation}</p>
										{/if}
									</div>
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<div class="p-4 bg-green-50 dark:bg-green-950 border border-green-200 rounded-lg text-green-700 text-sm text-center">
						{$t('contract.all_pass')}
					</div>
				{/if}
			</div>
		{/if}

		{#if error && checkResult}
			<div class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg text-red-700 text-sm mb-8">{error}</div>
		{/if}

		<!-- Provisions Reference -->
		{#if provisions && provisions.provisions.length > 0}
			<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
				<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
					<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{$t('contract.provisions_title')}</h2>
					<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
						{provisions.provisions.length} {$t('contract.provisions_count_suffix')}
					</p>
				</div>
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('contract.col_provision')}</th>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('contract.col_category')}</th>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('contract.col_reference')}</th>
								<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('contract.col_threshold')}</th>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('contract.col_description')}</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each provisions.provisions as p}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{p.name}</td>
									<td class="px-4 py-3">
										<span class="px-2 py-0.5 text-xs font-medium text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 rounded-full">
											{p.category || $t('contract.category_general')}
										</span>
									</td>
									<td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 font-mono">{p.reference || '-'}</td>
									<td class="px-4 py-3 text-sm text-right text-gray-700 dark:text-gray-300">
										{p.threshold_days > 0 ? `${p.threshold_days}d` : '-'}
									</td>
									<td class="px-4 py-3 text-sm text-gray-600 dark:text-gray-400 max-w-xs truncate">{p.description}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	{/if}
</div>
