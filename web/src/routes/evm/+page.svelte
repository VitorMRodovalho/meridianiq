<script lang="ts">
	import { getEVMAnalyses, createEVMAnalysis, getProjects } from '$lib/api';

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
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadAnalyses();
		loadProjects();
	});
</script>

<div class="p-8 max-w-5xl mx-auto">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900">Earned Value Management</h1>
		<p class="text-sm text-gray-500 mt-1">SPI/CPI analysis per ANSI/EIA-748</p>
	</div>

	<!-- Run EVM -->
	<div class="bg-white rounded-lg shadow p-6 mb-8">
		<h2 class="text-lg font-semibold text-gray-800 mb-4">Run EVM Analysis</h2>
		<div class="flex items-end gap-4">
			<div class="flex-1">
				<label for="project" class="block text-sm font-medium text-gray-700 mb-1">Select Project</label>
				<select
					id="project"
					bind:value={selectedProject}
					class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
				>
					<option value="">-- Choose a project --</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id} ({p.activity_count} activities)</option>
					{/each}
				</select>
			</div>
			<button
				onclick={runEVM}
				disabled={!selectedProject || loading}
				class="px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
			>
				{loading ? 'Analyzing...' : 'Run EVM'}
			</button>
		</div>
		{#if error}
			<p class="mt-3 text-sm text-red-600">{error}</p>
		{/if}
	</div>

	<!-- Analyses List -->
	{#if analyses.length > 0}
		<div class="bg-white rounded-lg shadow">
			<div class="px-6 py-4 border-b border-gray-200">
				<h2 class="text-lg font-semibold text-gray-800">Previous Analyses</h2>
			</div>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead class="bg-gray-50">
						<tr>
							<th class="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">ID</th>
							<th class="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">Project</th>
							<th class="px-6 py-3 text-right font-medium text-gray-500 uppercase tracking-wider">BAC</th>
							<th class="px-6 py-3 text-center font-medium text-gray-500 uppercase tracking-wider">SPI</th>
							<th class="px-6 py-3 text-center font-medium text-gray-500 uppercase tracking-wider">CPI</th>
							<th class="px-6 py-3 text-center font-medium text-gray-500 uppercase tracking-wider">Schedule</th>
							<th class="px-6 py-3 text-center font-medium text-gray-500 uppercase tracking-wider">Cost</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each analyses as a}
							<tr class="hover:bg-gray-50 cursor-pointer" onclick={() => window.location.href = `/evm/${a.analysis_id}`}>
								<td class="px-6 py-4 font-mono text-xs text-blue-600">{a.analysis_id}</td>
								<td class="px-6 py-4">{a.project_name || a.project_id}</td>
								<td class="px-6 py-4 text-right font-mono">${a.bac?.toLocaleString()}</td>
								<td class="px-6 py-4 text-center">
									<span class="inline-flex items-center gap-1">
										<span class="w-2 h-2 rounded-full {a.schedule_health === 'good' ? 'bg-green-500' : a.schedule_health === 'watch' ? 'bg-yellow-500' : 'bg-red-500'}"></span>
										{a.spi?.toFixed(2)}
									</span>
								</td>
								<td class="px-6 py-4 text-center">
									<span class="inline-flex items-center gap-1">
										<span class="w-2 h-2 rounded-full {a.cost_health === 'good' ? 'bg-green-500' : a.cost_health === 'watch' ? 'bg-yellow-500' : 'bg-red-500'}"></span>
										{a.cpi?.toFixed(2)}
									</span>
								</td>
								<td class="px-6 py-4 text-center capitalize text-xs font-medium
									{a.schedule_health === 'good' ? 'text-green-700' : a.schedule_health === 'watch' ? 'text-yellow-700' : 'text-red-700'}">
									{a.schedule_health}
								</td>
								<td class="px-6 py-4 text-center capitalize text-xs font-medium
									{a.cost_health === 'good' ? 'text-green-700' : a.cost_health === 'watch' ? 'text-yellow-700' : 'text-red-700'}">
									{a.cost_health}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{:else}
		<div class="bg-white rounded-lg shadow p-8 text-center text-gray-500">
			<p>No EVM analyses yet. Upload a project with resource cost data and run an analysis above.</p>
		</div>
	{/if}
</div>
