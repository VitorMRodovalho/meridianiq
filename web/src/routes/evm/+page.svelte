<script lang="ts">
	import { getEVMAnalyses, createEVMAnalysis, getProjects } from '$lib/api';
	import { error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import GaugeChart from '$lib/components/charts/GaugeChart.svelte';

	let analyses: any[] = $state([]);
	let projects: any[] = $state([]);
	let selectedProject = $state('');
	let loading = $state(false);
	let error = $state('');

	async function loadAnalyses() {
		try {
			const data = await getEVMAnalyses();
			analyses = data.analyses || [];
		} catch {
			/* ignore */
		}
	}

	async function loadProjects() {
		try {
			const data = await getProjects();
			projects = data.projects || [];
		} catch {
			/* ignore */
		}
	}

	async function runEVM() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		try {
			const result = await createEVMAnalysis(selectedProject);
			window.location.href = `/evm/${result.analysis_id}`;
		} catch (e: any) {
			error = e.message || 'Analysis failed';
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

		<!-- Mini S-Curve visualization -->
		{#if latest.pv_cumulative || latest.ev_cumulative || latest.ac_cumulative}
			{@const W = 600}
			{@const H = 180}
			{@const pad = { top: 20, right: 20, bottom: 30, left: 60 }}
			{@const cw = W - pad.left - pad.right}
			{@const ch = H - pad.top - pad.bottom}
			{@const maxVal = Math.max(latest.bac || 1, latest.eac || 1) * 1.1}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
				<p class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Earned Value S-Curve</p>
				<svg viewBox="0 0 {W} {H}" class="w-full">
					<!-- Grid -->
					{#each [0, 0.25, 0.5, 0.75, 1] as pct}
						<line x1={pad.left} y1={pad.top + pct * ch} x2={W - pad.right} y2={pad.top + pct * ch} stroke="#f3f4f6" stroke-width="1" />
						<text x={pad.left - 5} y={pad.top + pct * ch + 3} text-anchor="end" class="text-[8px] fill-gray-400">
							{formatCost(maxVal * (1 - pct))}
						</text>
					{/each}
					<!-- PV line (blue dashed) -->
					<line x1={pad.left} y1={pad.top + ch - (((latest.pv || latest.bac || 0) / maxVal) * ch)} x2={pad.left + cw} y2={pad.top} stroke="#3b82f6" stroke-width="2" stroke-dasharray="6 3" opacity="0.6" />
					<!-- EV line (green) -->
					<line x1={pad.left} y1={pad.top + ch} x2={pad.left + cw * 0.6} y2={pad.top + ch - ((latest.ev || 0) / maxVal) * ch} stroke="#10b981" stroke-width="2.5" />
					<!-- AC line (red) -->
					<line x1={pad.left} y1={pad.top + ch} x2={pad.left + cw * 0.6} y2={pad.top + ch - ((latest.ac || 0) / maxVal) * ch} stroke="#ef4444" stroke-width="2" />
					<!-- Axes -->
					<line x1={pad.left} y1={pad.top} x2={pad.left} y2={pad.top + ch} stroke="#d1d5db" stroke-width="1" />
					<line x1={pad.left} y1={pad.top + ch} x2={W - pad.right} y2={pad.top + ch} stroke="#d1d5db" stroke-width="1" />
					<text x={W / 2} y={H - 5} text-anchor="middle" class="text-[9px] fill-gray-400">Time</text>
				</svg>
				<div class="flex items-center gap-4 mt-2 text-xs text-gray-500 dark:text-gray-400">
					<div class="flex items-center gap-1"><span class="w-4 h-0.5 bg-blue-500 rounded" style="border-bottom: 2px dashed #3b82f6"></span> PV (Planned)</div>
					<div class="flex items-center gap-1"><span class="w-4 h-0.5 bg-green-500 rounded"></span> EV (Earned)</div>
					<div class="flex items-center gap-1"><span class="w-4 h-0.5 bg-red-500 rounded"></span> AC (Actual Cost)</div>
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
