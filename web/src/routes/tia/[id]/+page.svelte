<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { getTIAAnalysis, contractCheck } from '$lib/api';
	import type { TIAAnalysisSchema, ContractCheckResponse } from '$lib/types';

	let analysisId = $derived($page.params.id!);
	let analysis: TIAAnalysisSchema | null = $state(null);
	let compliance: ContractCheckResponse | null = $state(null);
	let loading = $state(true);
	let complianceLoading = $state(false);
	let error = $state('');

	onMount(async () => {
		try {
			analysis = await getTIAAnalysis(analysisId);
		} catch {
			error = 'Failed to load TIA analysis';
		} finally {
			loading = false;
		}
	});

	async function runComplianceCheck() {
		if (!analysis) return;
		complianceLoading = true;
		try {
			compliance = await contractCheck(analysis.analysis_id);
		} catch {
			error = 'Failed to run compliance check';
		} finally {
			complianceLoading = false;
		}
	}

	function partyColor(party: string): string {
		switch (party) {
			case 'owner':
				return 'text-blue-600';
			case 'contractor':
				return 'text-red-600';
			case 'shared':
				return 'text-yellow-600';
			case 'force_majeure':
				return 'text-gray-600 dark:text-gray-400';
			case 'third_party':
				return 'text-purple-600';
			default:
				return 'text-gray-500 dark:text-gray-400';
		}
	}

	function partyBgColor(party: string): string {
		switch (party) {
			case 'owner':
				return 'bg-blue-500';
			case 'contractor':
				return 'bg-red-500';
			case 'shared':
				return 'bg-yellow-500';
			case 'force_majeure':
				return 'bg-gray-500';
			case 'third_party':
				return 'bg-purple-500';
			default:
				return 'bg-gray-300';
		}
	}

	function statusBadge(status: string): string {
		switch (status) {
			case 'pass':
				return 'bg-green-100 text-green-800';
			case 'fail':
				return 'bg-red-100 text-red-800';
			case 'warning':
				return 'bg-yellow-100 text-yellow-800';
			default:
				return 'bg-gray-100 dark:bg-gray-800 text-gray-800';
		}
	}

	// Compute waterfall chart data
	let waterfallData = $derived.by(() => {
		if (!analysis) return [];
		const entries: { label: string; value: number; color: string }[] = [];

		if (analysis.total_owner_delay > 0) {
			entries.push({
				label: 'Owner',
				value: analysis.total_owner_delay,
				color: '#3B82F6'
			});
		}
		if (analysis.total_contractor_delay > 0) {
			entries.push({
				label: 'Contractor',
				value: analysis.total_contractor_delay,
				color: '#EF4444'
			});
		}
		if (analysis.total_shared_delay > 0) {
			entries.push({
				label: 'Shared/FM',
				value: analysis.total_shared_delay,
				color: '#F59E0B'
			});
		}
		return entries;
	});

	let maxDelay = $derived(
		waterfallData.length > 0 ? Math.max(...waterfallData.map((d) => d.value)) : 1
	);
</script>

<svelte:head>
	<title>TIA Analysis {analysisId} - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-7xl mx-auto">
	<div class="mb-6">
		<a href="/tia" class="text-sm text-blue-600 hover:underline">&larr; Back to TIA</a>
	</div>

	{#if loading}
		<p class="text-gray-500 dark:text-gray-400">Loading analysis...</p>
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 text-sm text-red-700">{error}</div>
	{:else if analysis}
		<div class="flex items-center justify-between mb-6">
			<div>
				<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">TIA: {analysis.analysis_id}</h1>
				<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
					{analysis.project_name} | {analysis.fragments.length} fragment{analysis.fragments
						.length !== 1
						? 's'
						: ''}
				</p>
			</div>
			<button
				onclick={runComplianceCheck}
				disabled={complianceLoading}
				class="bg-green-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
			>
				{complianceLoading ? 'Checking...' : 'Run Compliance Check'}
			</button>
		</div>

		<!-- Summary Cards -->
		<div class="grid grid-cols-4 gap-4 mb-6">
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase font-medium">Total Owner Delay</p>
				<p class="text-2xl font-bold text-blue-600 mt-1">
					{analysis.total_owner_delay.toFixed(1)}d
				</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase font-medium">Total Contractor Delay</p>
				<p class="text-2xl font-bold text-red-600 mt-1">
					{analysis.total_contractor_delay.toFixed(1)}d
				</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase font-medium">Total Shared Delay</p>
				<p class="text-2xl font-bold text-yellow-600 mt-1">
					{analysis.total_shared_delay.toFixed(1)}d
				</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase font-medium">Net Delay</p>
				<p
					class="text-2xl font-bold mt-1 {analysis.net_delay > 0
						? 'text-red-600'
						: 'text-green-600'}"
				>
					{analysis.net_delay > 0 ? '+' : ''}{analysis.net_delay.toFixed(1)}d
				</p>
			</div>
		</div>

		<!-- Responsibility Waterfall Chart -->
		{#if waterfallData.length > 0}
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Delay by Responsibility</h2>
				<svg viewBox="0 0 500 180" class="w-full max-w-xl">
					{#each waterfallData as bar, i}
						{@const barWidth = (bar.value / maxDelay) * 350}
						{@const y = i * 50 + 10}
						<text x="0" y={y + 22} class="text-xs" fill="#6B7280" font-size="13">
							{bar.label}
						</text>
						<rect x="80" y={y} width={barWidth} height="32" rx="4" fill={bar.color} />
						<text
							x={80 + barWidth + 8}
							y={y + 22}
							fill="#374151"
							font-size="13"
							font-weight="600"
						>
							{bar.value.toFixed(1)}d
						</text>
					{/each}
				</svg>
			</div>
		{/if}

		<!-- Per-fragment Results Table -->
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg mb-6">
			<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">Fragment Results</h2>
			</div>
			<div class="overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200 text-sm">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase"
								>Fragment</th
							>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase"
								>Responsibility</th
							>
							<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase"
								>Delay Days</th
							>
							<th class="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase"
								>On CP?</th
							>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase"
								>Type</th
							>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase"
								>Concurrent With</th
							>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each analysis.results as r}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
								<td class="px-4 py-3">
									<span class="font-medium text-gray-900 dark:text-gray-100">{r.fragment_name}</span>
									<span class="text-xs text-gray-400 ml-1">({r.fragment_id})</span>
								</td>
								<td class="px-4 py-3">
									<span
										class="inline-flex items-center gap-1.5 text-sm font-medium {partyColor(
											r.responsible_party
										)}"
									>
										<span
											class="w-2 h-2 rounded-full {partyBgColor(r.responsible_party)}"
										></span>
										{r.responsible_party}
									</span>
								</td>
								<td
									class="px-4 py-3 text-right font-medium {r.delay_days > 0
										? 'text-red-600'
										: 'text-gray-500 dark:text-gray-400'}"
								>
									{r.delay_days > 0 ? '+' : ''}{r.delay_days.toFixed(1)}
								</td>
								<td class="px-4 py-3 text-center">
									{#if r.critical_path_affected}
										<span
											class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800"
										>
											Yes
										</span>
									{:else}
										<span
											class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
										>
											No
										</span>
									{/if}
								</td>
								<td class="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
									{r.delay_type.replace(/_/g, ' ')}
								</td>
								<td class="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
									{r.concurrent_with.length > 0 ? r.concurrent_with.join(', ') : '-'}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>

		<!-- Compliance Check Results -->
		{#if compliance}
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg">
				<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
					<div class="flex items-center justify-between">
						<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">Contract Compliance</h2>
						<div class="flex gap-3 text-xs">
							<span class="text-gray-500 dark:text-gray-400">{compliance.total_checks} checks</span>
							{#if compliance.warnings > 0}
								<span class="text-yellow-600">{compliance.warnings} warnings</span>
							{/if}
							{#if compliance.failures > 0}
								<span class="text-red-600">{compliance.failures} failures</span>
							{/if}
						</div>
					</div>
				</div>
				<div class="divide-y divide-gray-100">
					{#each compliance.checks as check}
						<div class="px-6 py-4">
							<div class="flex items-start gap-3">
								<span
									class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium {statusBadge(
										check.status
									)}"
								>
									{check.status}
								</span>
								<div class="flex-1 min-w-0">
									<div class="flex items-center gap-2 mb-1">
										<span class="text-sm font-medium text-gray-900 dark:text-gray-100"
											>{check.provision_name}</span
										>
										<span class="text-xs text-gray-400">({check.fragment_name})</span
										>
									</div>
									<p class="text-sm text-gray-600 dark:text-gray-400">{check.finding}</p>
									{#if check.recommendation}
										<p class="text-xs text-gray-400 mt-1 italic">
											{check.recommendation}
										</p>
									{/if}
								</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	{/if}
</div>
