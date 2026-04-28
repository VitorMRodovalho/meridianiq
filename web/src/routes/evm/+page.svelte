<script lang="ts">
	import {
		getEVMAnalyses,
		createEVMAnalysis,
		getProjects,
		type EVMAnalysisSummary
	} from '$lib/api';
	import type { ProjectListItem } from '$lib/types';
	import { error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import GaugeChart from '$lib/components/charts/GaugeChart.svelte';
	import EVMSCurveChart from '$lib/components/charts/EVMSCurveChart.svelte';

	let analyses: EVMAnalysisSummary[] = $state([]);
	let projects: ProjectListItem[] = $state([]);
	let selectedProject = $state('');
	let loading = $state(false);
	let error = $state('');

	async function loadAnalyses() {
		try {
			const data = await getEVMAnalyses();
			analyses = data.analyses || [];
		} catch (e) {
			console.error('loadEVMAnalyses:', e);
			// Non-blocking: empty list is acceptable initial state
		}
	}

	async function loadProjects() {
		try {
			const data = await getProjects();
			projects = data.projects || [];
		} catch (e) {
			const msg = e instanceof Error ? e.message : 'Failed to load projects';
			toastError(`Could not load projects: ${msg}`);
			console.error('loadProjects (evm):', e);
		}
	}

	async function runEVM() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		try {
			const result = await createEVMAnalysis(selectedProject);
			window.location.href = `/evm/${result.analysis_id}`;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Analysis failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadAnalyses();
		loadProjects();
	});

	function spiColor(spi: number): string {
		if (spi >= 0.95) return 'text-green-600';
		if (spi >= 0.85) return 'text-amber-600';
		return 'text-red-600';
	}

	function cpiColor(cpi: number): string {
		if (cpi >= 0.95) return 'text-green-600';
		if (cpi >= 0.85) return 'text-amber-600';
		return 'text-red-600';
	}

	function formatCost(v: number): string {
		if (!v) return '$0';
		if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
		if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
		return `$${v.toFixed(0)}`;
	}

	// Latest analysis for summary gauges
	const latest = $derived(analyses.length > 0 ? analyses[0] : null);
</script>

<svelte:head>
	<title>Earned Value (EVM) | MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.evm')}</h1>
		<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">SPI/CPI analysis per ANSI/EIA-748</p>
	</div>

	<!-- Run EVM -->
	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<div class="flex items-end gap-4">
			<div class="flex-1">
				<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('common.project')}</label>
				<select
					id="project"
					bind:value={selectedProject}
					class="w-full border border-gray-300 dark:border-gray-600 rounded-md px-3 py-2 text-sm"
				>
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id} ({p.activity_count} activities)</option>
					{/each}
				</select>
			</div>
			<button
				onclick={runEVM}
				disabled={!selectedProject || loading}
				class="px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
			>
				{loading ? 'Analyzing...' : 'Run EVM'}
			</button>
			{#if selectedProject}
				<a href="/schedule?project={selectedProject}" class="px-3 py-2 text-xs text-teal-600 hover:text-teal-800 font-medium">View Schedule</a>
			{/if}
		</div>
		{#if loading}
			<AnalysisSkeleton />
		{:else if error}
			<p class="mt-3 text-sm text-red-600">{error}</p>
		{/if}
	</div>

	<!-- Latest Analysis Summary Gauges -->
	{#if latest}
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
				<p class="text-3xl font-bold {spiColor(latest.spi || 0)}">{latest.spi?.toFixed(2) || 'N/A'}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase mt-1">SPI</p>
				<div class="mt-2 h-1.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
					<div class="h-full rounded-full {latest.spi >= 0.95 ? 'bg-green-500' : latest.spi >= 0.85 ? 'bg-amber-500' : 'bg-red-500'}" style="width: {Math.min(100, (latest.spi || 0) * 100)}%"></div>
				</div>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
				<p class="text-3xl font-bold {cpiColor(latest.cpi || 0)}">{latest.cpi?.toFixed(2) || 'N/A'}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase mt-1">CPI</p>
				<div class="mt-2 h-1.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
					<div class="h-full rounded-full {latest.cpi >= 0.95 ? 'bg-green-500' : latest.cpi >= 0.85 ? 'bg-amber-500' : 'bg-red-500'}" style="width: {Math.min(100, (latest.cpi || 0) * 100)}%"></div>
				</div>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{formatCost(latest.bac || 0)}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase mt-1">BAC</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{formatCost(latest.eac || 0)}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase mt-1">EAC</p>
				{#if latest.bac && latest.eac}
					<p class="text-xs mt-1 {latest.eac > latest.bac ? 'text-red-600' : 'text-green-600'}">
						{latest.eac > latest.bac ? '+' : ''}{formatCost(latest.eac - latest.bac)} variance
					</p>
				{/if}
			</div>
		</div>

		<!-- S-Curve Chart -->
		{#if latest.s_curve && latest.s_curve.length >= 2}
			<div class="mb-6">
				<EVMSCurveChart
					data={latest.s_curve}
					dataDate={latest.data_date || ''}
					bac={latest.bac || 0}
					eac={latest.eac || 0}
					spi={latest.spi || 0}
					cpi={latest.cpi || 0}
					sv={(latest.ev || 0) - (latest.pv || 0)}
					cv={(latest.ev || 0) - (latest.ac || 0)}
				/>
			</div>
		{:else if latest.ev > 0 || latest.ac > 0}
			<!-- Fallback: simple PV/EV/AC summary when no S-Curve data -->
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
				<p class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Earned Value Summary</p>
				<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
					<div>
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">PV (Planned)</p>
						<p class="text-lg font-bold text-blue-600">{formatCost(latest.pv || 0)}</p>
					</div>
					<div>
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">EV (Earned)</p>
						<p class="text-lg font-bold text-green-600">{formatCost(latest.ev || 0)}</p>
					</div>
					<div>
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">AC (Actual Cost)</p>
						<p class="text-lg font-bold text-red-600">{formatCost(latest.ac || 0)}</p>
					</div>
				</div>
			</div>
		{/if}
	{/if}

	<!-- Analyses List -->
	{#if analyses.length > 0}
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
			<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
				<h2 class="text-lg font-semibold text-gray-800">Previous Analyses ({analyses.length})</h2>
			</div>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400 uppercase text-xs">Project</th>
							<th class="px-4 py-3 text-right font-medium text-gray-500 dark:text-gray-400 uppercase text-xs">BAC</th>
							<th class="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400 uppercase text-xs">SPI</th>
							<th class="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400 uppercase text-xs">CPI</th>
							<th class="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400 uppercase text-xs">Schedule</th>
							<th class="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400 uppercase text-xs">Cost</th>
							<th class="px-4 py-3 text-right font-medium text-gray-500 dark:text-gray-400 uppercase text-xs">EAC</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each analyses as a}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer" onclick={() => window.location.href = `/evm/${a.analysis_id}`}>
								<td class="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{a.project_name || a.project_id}</td>
								<td class="px-4 py-3 text-right font-mono text-gray-500 dark:text-gray-400">{formatCost(a.bac || 0)}</td>
								<td class="px-4 py-3 text-center">
									<span class="inline-flex items-center gap-1.5 font-bold {spiColor(a.spi || 0)}">
										<span class="w-2 h-2 rounded-full {a.spi >= 0.95 ? 'bg-green-500' : a.spi >= 0.85 ? 'bg-amber-500' : 'bg-red-500'}"></span>
										{a.spi?.toFixed(2)}
									</span>
								</td>
								<td class="px-4 py-3 text-center">
									<span class="inline-flex items-center gap-1.5 font-bold {cpiColor(a.cpi || 0)}">
										<span class="w-2 h-2 rounded-full {a.cpi >= 0.95 ? 'bg-green-500' : a.cpi >= 0.85 ? 'bg-amber-500' : 'bg-red-500'}"></span>
										{a.cpi?.toFixed(2)}
									</span>
								</td>
								<td class="px-4 py-3 text-center">
									<span class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase
										{a.schedule_health === 'good' ? 'bg-green-100 text-green-700' : a.schedule_health === 'watch' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}">
										{a.schedule_health}
									</span>
								</td>
								<td class="px-4 py-3 text-center">
									<span class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase
										{a.cost_health === 'good' ? 'bg-green-100 text-green-700' : a.cost_health === 'watch' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}">
										{a.cost_health}
									</span>
								</td>
								<td class="px-4 py-3 text-right font-mono text-gray-500 dark:text-gray-400">{formatCost(a.eac || 0)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{:else}
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center text-gray-500 dark:text-gray-400">
			<p>No EVM analyses yet. Upload a project with resource cost data and run an analysis above.</p>
		</div>
	{/if}
</div>
