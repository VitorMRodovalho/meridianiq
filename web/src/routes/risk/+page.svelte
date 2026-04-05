<script lang="ts">
	import { getRiskSimulations, createRiskSimulation, getProjects } from '$lib/api';
	import { error as toastError } from '$lib/toast';

	interface SimulationSummary {
		simulation_id: string;
		project_name: string;
		project_id: string;
		iterations: number;
		deterministic_days: number;
		mean_days: number;
		p50_days: number;
		p80_days: number;
	}

	interface ProjectItem {
		project_id: string;
		name: string;
		activity_count: number;
	}

	let simulations: SimulationSummary[] = $state([]);
	let projects: ProjectItem[] = $state([]);
	let loading = $state(false);
	let running = $state(false);
	let error = $state('');

	// Form state
	let selectedProject = $state('');
	let iterations = $state(1000);
	let distributionType = $state('pert');
	let uncertainty = $state(20);
	let seed = $state('');

	async function loadSimulations() {
		loading = true;
		error = '';
		try {
			const data = await getRiskSimulations();
			simulations = data.simulations;
		} catch (e: any) {
			error = e.message;
			toastError(error);
		} finally {
			loading = false;
		}
	}

	async function loadProjects() {
		try {
			const data = await getProjects();
			projects = data.projects;
		} catch { }
	}

	async function runSimulation() {
		if (!selectedProject) return;
		running = true;
		error = '';
		try {
			const body: any = {
				config: {
					iterations,
					default_distribution: distributionType,
					default_uncertainty: uncertainty / 100,
					confidence_levels: [10, 25, 50, 75, 80, 90],
				},
				duration_risks: [],
				risk_events: [],
			};
			if (seed) body.config.seed = parseInt(seed);

			await createRiskSimulation(selectedProject, body);
			await loadSimulations();
		} catch (e: any) {
			error = e.message;
			toastError(error);
		} finally {
			running = false;
		}
	}

	$effect(() => {
		loadSimulations();
		loadProjects();
	});
</script>

<div class="p-8 max-w-6xl mx-auto">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900">Risk Analysis (QSRA)</h1>
		<p class="text-gray-500 mt-1">Monte Carlo schedule risk simulation per AACE RP 57R-09</p>
	</div>

	{#if error}
		<div class="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
	{/if}

	<!-- New Simulation Form -->
	<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-8">
		<h2 class="text-lg font-semibold text-gray-900 mb-4">New Simulation</h2>
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
			<div>
				<label for="project" class="block text-sm font-medium text-gray-700 mb-1">Project</label>
				<select
					id="project"
					bind:value={selectedProject}
					class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
				>
					<option value="">Select project...</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name} ({p.project_id})</option>
					{/each}
				</select>
			</div>
			<div>
				<label for="iterations" class="block text-sm font-medium text-gray-700 mb-1">Iterations</label>
				<input
					id="iterations"
					type="number"
					bind:value={iterations}
					min="100"
					max="10000"
					step="100"
					class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
				/>
			</div>
			<div>
				<label for="dist" class="block text-sm font-medium text-gray-700 mb-1">Distribution</label>
				<select
					id="dist"
					bind:value={distributionType}
					class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
				>
					<option value="pert">PERT-Beta</option>
					<option value="triangular">Triangular</option>
					<option value="uniform">Uniform</option>
					<option value="lognormal">Lognormal</option>
				</select>
			</div>
			<div>
				<label for="uncertainty" class="block text-sm font-medium text-gray-700 mb-1">Uncertainty %</label>
				<input
					id="uncertainty"
					type="number"
					bind:value={uncertainty}
					min="5"
					max="100"
					step="5"
					class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
				/>
			</div>
			<div class="flex items-end">
				<button
					onclick={runSimulation}
					disabled={!selectedProject || running}
					class="w-full bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
				>
					{running ? 'Running...' : 'Run Simulation'}
				</button>
			</div>
		</div>
	</div>

	<!-- Simulations List -->
	<div class="bg-white rounded-lg shadow-sm border border-gray-200">
		<div class="px-6 py-4 border-b border-gray-200">
			<h2 class="text-lg font-semibold text-gray-900">Simulations</h2>
		</div>
		{#if loading}
			<div class="p-8 text-center text-gray-500">Loading...</div>
		{:else if simulations.length === 0}
			<div class="p-8 text-center text-gray-500">No simulations yet. Run one above.</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50">
						<tr>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Project</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Iterations</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Deterministic</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">P50</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">P80</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Mean</th>
							<th class="px-6 py-3"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each simulations as sim}
							<tr class="hover:bg-gray-50">
								<td class="px-6 py-3 text-sm font-mono text-gray-600">{sim.simulation_id}</td>
								<td class="px-6 py-3 text-sm text-gray-900">{sim.project_name}</td>
								<td class="px-6 py-3 text-sm text-right text-gray-600">{sim.iterations.toLocaleString()}</td>
								<td class="px-6 py-3 text-sm text-right text-gray-600">{sim.deterministic_days.toFixed(1)}d</td>
								<td class="px-6 py-3 text-sm text-right font-medium text-blue-600">{sim.p50_days.toFixed(1)}d</td>
								<td class="px-6 py-3 text-sm text-right font-medium text-orange-600">{sim.p80_days.toFixed(1)}d</td>
								<td class="px-6 py-3 text-sm text-right text-gray-600">{sim.mean_days.toFixed(1)}d</td>
								<td class="px-6 py-3 text-right">
									<a
										href="/risk/{sim.simulation_id}"
										class="text-blue-600 hover:text-blue-800 text-sm font-medium"
									>
										View &rarr;
									</a>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
</div>
