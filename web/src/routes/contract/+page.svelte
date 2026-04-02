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
			error = 'Failed to load data';
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
			error = e instanceof Error ? e.message : 'Compliance check failed';
		} finally {
			checking = false;
		}
	}

	function statusColor(status: string): string {
		if (status === 'pass' || status === 'compliant') return 'text-green-700 bg-green-50 border-green-200';
		if (status === 'warning') return 'text-yellow-700 bg-yellow-50 border-yellow-200';
		if (status === 'fail' || status === 'non_compliant') return 'text-red-700 bg-red-50 border-red-200';
		return 'text-gray-700 bg-gray-50 border-gray-200';
	}

	function statusBadge(status: string): string {
		if (status === 'pass' || status === 'compliant') return 'bg-green-100 text-green-800';
		if (status === 'warning') return 'bg-yellow-100 text-yellow-800';
		if (status === 'fail' || status === 'non_compliant') return 'bg-red-100 text-red-800';
		return 'bg-gray-100 text-gray-800';
	}

	function categoryIcon(category: string): string {
		if (category.toLowerCase().includes('time')) return 'clock';
		if (category.toLowerCase().includes('notice')) return 'bell';
		if (category.toLowerCase().includes('change')) return 'refresh';
		return 'shield';
	}
</script>

<svelte:head>
	<title>Contract Compliance - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-7xl mx-auto">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900">Contract Compliance</h1>
		<p class="text-sm text-gray-500 mt-1">
			Automated compliance checks against AIA A201, ConsensusDocs, and SCL Delay & Disruption Protocol.
		</p>
	</div>

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500 py-12 justify-center">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			Loading...
		</div>
	{:else if error && !checkResult}
		<div class="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
	{:else}
		<!-- Run Compliance Check -->
		<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-8">
			<h2 class="text-lg font-semibold text-gray-900 mb-4">Run Compliance Check</h2>
			<p class="text-sm text-gray-600 mb-4">
				Select a TIA analysis to check against contract provisions. The check evaluates delay fragments
				against notice requirements, time extension thresholds, and procedural compliance.
			</p>
			{#if analyses.length === 0}
				<div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800 text-sm">
					No TIA analyses available. <a href="/tia" class="underline font-medium">Run a TIA analysis</a> first.
				</div>
			{:else}
				<div class="flex items-end gap-4">
					<label class="flex-1">
						<span class="block text-sm font-medium text-gray-700 mb-1">TIA Analysis</span>
						<select
							bind:value={selectedAnalysisId}
							class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						>
							<option value="">Select an analysis...</option>
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
						{checking ? 'Checking...' : 'Run Check'}
					</button>
				</div>
			{/if}
		</div>

		<!-- Check Results -->
		{#if checkResult}
			<div class="mb-8">
				<div class="grid grid-cols-3 gap-4 mb-6">
					<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 text-center">
						<p class="text-xs font-medium text-gray-500 uppercase">Total Checks</p>
						<p class="text-2xl font-bold text-gray-900 mt-1">{checkResult.total_checks}</p>
					</div>
					<div class="bg-white rounded-lg shadow-sm border border-yellow-200 p-4 text-center">
						<p class="text-xs font-medium text-yellow-600 uppercase">Warnings</p>
						<p class="text-2xl font-bold text-yellow-600 mt-1">{checkResult.warnings}</p>
					</div>
					<div class="bg-white rounded-lg shadow-sm border border-red-200 p-4 text-center">
						<p class="text-xs font-medium text-red-600 uppercase">Failures</p>
						<p class="text-2xl font-bold text-red-600 mt-1">{checkResult.failures}</p>
					</div>
				</div>

				<!-- Compliance Distribution Chart -->
				<div class="mb-6">
					<PieChart
						title="Compliance Check Results"
						size={170}
						data={[
							{ label: 'Pass', value: checkResult.total_checks - checkResult.warnings - checkResult.failures, color: '#10b981' },
							{ label: 'Warning', value: checkResult.warnings, color: '#f59e0b' },
							{ label: 'Fail', value: checkResult.failures, color: '#ef4444' },
						]}
					/>
				</div>

				{#if checkResult.checks.length > 0}
					<div class="space-y-3">
						{#each checkResult.checks as check}
							<div class="bg-white rounded-lg shadow-sm border p-4 {statusColor(check.status)}">
								<div class="flex items-start justify-between gap-4">
									<div class="flex-1">
										<div class="flex items-center gap-2 mb-1">
											<span class="text-sm font-semibold">{check.provision_name}</span>
											<span class="px-2 py-0.5 text-xs font-medium rounded-full {statusBadge(check.status)}">
												{check.status.toUpperCase()}
											</span>
											{#if check.provision_category}
												<span class="px-2 py-0.5 text-xs text-gray-500 bg-gray-100 rounded-full">
													{check.provision_category}
												</span>
											{/if}
										</div>
										<p class="text-sm text-gray-600 mb-1">
											<span class="font-medium">Fragment:</span> {check.fragment_name} ({check.fragment_id})
										</p>
										{#if check.finding}
											<p class="text-sm mt-1">{check.finding}</p>
										{/if}
										{#if check.recommendation}
											<p class="text-xs text-gray-500 mt-1 italic">Recommendation: {check.recommendation}</p>
										{/if}
									</div>
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<div class="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm text-center">
						All checks passed. No compliance issues found.
					</div>
				{/if}
			</div>
		{/if}

		{#if error && checkResult}
			<div class="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm mb-8">{error}</div>
		{/if}

		<!-- Provisions Reference -->
		{#if provisions && provisions.provisions.length > 0}
			<div class="bg-white rounded-lg shadow-sm border border-gray-200">
				<div class="px-6 py-4 border-b border-gray-200">
					<h2 class="text-lg font-semibold text-gray-900">Contract Provisions Reference</h2>
					<p class="text-sm text-gray-500 mt-1">
						{provisions.provisions.length} provisions from AIA A201, ConsensusDocs, and SCL Protocol
					</p>
				</div>
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Provision</th>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reference</th>
								<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Threshold</th>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each provisions.provisions as p}
								<tr class="hover:bg-gray-50">
									<td class="px-4 py-3 text-sm font-medium text-gray-900">{p.name}</td>
									<td class="px-4 py-3">
										<span class="px-2 py-0.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-full">
											{p.category || 'General'}
										</span>
									</td>
									<td class="px-4 py-3 text-sm text-gray-500 font-mono">{p.reference || '-'}</td>
									<td class="px-4 py-3 text-sm text-right text-gray-700">
										{p.threshold_days > 0 ? `${p.threshold_days}d` : '-'}
									</td>
									<td class="px-4 py-3 text-sm text-gray-600 max-w-xs truncate">{p.description}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	{/if}
</div>
