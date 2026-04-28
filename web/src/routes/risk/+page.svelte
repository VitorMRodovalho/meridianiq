<script lang="ts">
	import {
		getRiskSimulations,
		createRiskSimulation,
		getRiskSimulationByJob,
		getProjects,
		type RiskSimulationSummary,
		type RiskSimulationRunConfig
	} from '$lib/api';
	import { error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { useWebSocketProgress } from '$lib/composables/useWebSocketProgress';

	interface ProjectItem {
		project_id: string;
		name: string;
		activity_count: number;
	}

	let simulations: RiskSimulationSummary[] = $state([]);
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

	// Live progress channel (W5/W6 Cycle 1 v4.0 — ADR-0013 publisher consumed here).
	// `progressState` is the composable's readable store; the template
	// auto-subscribes via the `$progressState` sigil so every WebSocket
	// frame triggers a re-render without manual polling.
	//
	// ADR-0019 §"W1 — D4" recoveryPoller — on transient WS disconnect
	// (TLS hiccup, Fly.io single-instance restart blip, ~5–15s) the
	// composable enters `recovering` state and polls this function on
	// 5s cadence within a 60s window. The poller hits the by-job
	// endpoint that resolves to `simulation_id` once the backend has
	// stored the result, OR returns null while still running. A
	// non-null result flips the composable to `done` without spurious
	// `error`. Authoritative close codes (4401/4403/4404) bypass the
	// recovery — those are deliberate server decisions, not blips.
	async function riskRecoveryPoller(jobId: string): Promise<string | null> {
		const result = await getRiskSimulationByJob(jobId);
		return result.simulation_id;
	}
	const progress = useWebSocketProgress({ recoveryPoller: riskRecoveryPoller });
	const progressState = progress.state;

	async function loadSimulations() {
		loading = true;
		error = '';
		try {
			const data = await getRiskSimulations();
			simulations = data.simulations;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load simulations';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	async function loadProjects() {
		try {
			const data = await getProjects();
			projects = data.projects;
		} catch (e) {
			const msg = e instanceof Error ? e.message : 'Failed to load projects';
			toastError(`Could not load projects: ${msg}`);
			console.error('loadProjects (risk):', e);
		}
	}

	async function runSimulation() {
		if (!selectedProject) return;
		running = true;
		error = '';
		progress.reset();

		try {
			// Start the progress channel first so the backend publishes
			// into an already-open socket rather than a queue nobody is
			// draining. `start()` resolves only after the WS accepted.
			const jobId = await progress.start();

			const body: RiskSimulationRunConfig = {
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

			const result = await createRiskSimulation(selectedProject, body, jobId);
			// Authoritative completion signal from the HTTP response —
			// avoids the race where the REST roundtrip finishes before
			// the terminal WS frame, which would otherwise flip a
			// successful run to `cancelled` (end-of-wave review P1).
			progress.markDone(result.simulation_id);
			await loadSimulations();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Simulation failed';
			progress.markError(error);
			toastError(error);
		} finally {
			progress.close();
			running = false;
		}
	}

	$effect(() => {
		loadSimulations();
		loadProjects();
	});
</script>

<svelte:head>
	<title>Risk (QSRA) | MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Risk Analysis (QSRA)</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">Monte Carlo schedule risk simulation per AACE RP 57R-09</p>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="mb-6 p-4 bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
	{/if}

	<!-- New Simulation Form -->
	<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-8">
		<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">New Simulation</h2>
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
			<div>
				<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('common.project')}</label>
				<select
					id="project"
					bind:value={selectedProject}
					class="w-full border border-gray-300 dark:border-gray-600 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
				>
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name} ({p.project_id})</option>
					{/each}
				</select>
			</div>
			<div>
				<label for="iterations" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Iterations</label>
				<input
					id="iterations"
					type="number"
					bind:value={iterations}
					min="100"
					max="10000"
					step="100"
					class="w-full border border-gray-300 dark:border-gray-600 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
				/>
			</div>
			<div>
				<label for="dist" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Distribution</label>
				<select
					id="dist"
					bind:value={distributionType}
					class="w-full border border-gray-300 dark:border-gray-600 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
				>
					<option value="pert">PERT-Beta</option>
					<option value="triangular">Triangular</option>
					<option value="uniform">Uniform</option>
					<option value="lognormal">Lognormal</option>
				</select>
			</div>
			<div>
				<label for="uncertainty" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Uncertainty %</label>
				<input
					id="uncertainty"
					type="number"
					bind:value={uncertainty}
					min="5"
					max="100"
					step="5"
					class="w-full border border-gray-300 dark:border-gray-600 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
				/>
			</div>
			<div class="flex items-end gap-2">
				<button
					onclick={runSimulation}
					disabled={!selectedProject || running}
					class="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
				>
					{running ? 'Running...' : 'Run Simulation'}
				</button>
				{#if selectedProject}
					<a href="/schedule?project={selectedProject}" class="px-3 py-2 text-xs text-teal-600 hover:text-teal-800 font-medium whitespace-nowrap">Schedule</a>
				{/if}
			</div>

			{#if $progressState.status !== 'idle'}
				<div class="md:col-span-2 lg:col-span-5 pt-2">
					<div
						class="h-2 w-full bg-gray-100 dark:bg-gray-800 rounded overflow-hidden"
						role="progressbar"
						aria-valuenow={Math.round($progressState.pct)}
						aria-valuemin={0}
						aria-valuemax={100}
						aria-label={$t('risk.progress.label')}
					>
						<div
							class="h-full transition-all duration-300 {$progressState.status === 'error'
								? 'bg-red-500'
								: $progressState.status === 'done'
									? 'bg-green-600'
									: $progressState.status === 'recovering'
										? 'bg-amber-500 animate-pulse'
										: 'bg-blue-600'}"
							style="width: {$progressState.status === 'done' ? 100 : $progressState.pct}%"
						></div>
					</div>
					<p
						class="mt-1 text-xs text-gray-500 dark:text-gray-400"
						aria-live="polite"
					>
						{#if $progressState.status === 'starting'}
							{$t('risk.progress.starting')}
						{:else if $progressState.status === 'connecting'}
							{$t('risk.progress.connecting')}
						{:else if $progressState.status === 'running'}
							{$t('risk.progress.running')} — {Math.round($progressState.pct)}% ({$progressState.done.toLocaleString()} / {$progressState.total.toLocaleString()})
						{:else if $progressState.status === 'recovering'}
							{$t('risk.progress.recovering')}
						{:else if $progressState.status === 'done'}
							{$t('risk.progress.running')} — 100%
						{:else if $progressState.status === 'error'}
							{#if $progressState.error === 'connection_lost' || $progressState.error === 'connection_failed' || $progressState.error === 'auth_expired' || $progressState.error === 'forbidden' || $progressState.error === 'job_not_found'}
								{$t('risk.progress.connection_lost')}
							{:else}
								{$t('risk.progress.failed')}
							{/if}
						{/if}
					</p>
				</div>
			{/if}
		</div>
	</div>

	<!-- Simulations List -->
	<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
		<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">Simulations</h2>
		</div>
		{#if loading}
			<div class="p-8 text-center text-gray-500 dark:text-gray-400">Loading...</div>
		{:else if simulations.length === 0}
			<div class="p-8 text-center text-gray-500 dark:text-gray-400">No simulations yet. Run one above.</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">ID</th>
							<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Project</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Iterations</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Deterministic</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">P50</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">P80</th>
							<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Mean</th>
							<th class="px-6 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Det vs P80</th>
							<th class="px-6 py-3"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each simulations as sim}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
								<td class="px-6 py-3 text-sm font-mono text-gray-600 dark:text-gray-400">{sim.simulation_id}</td>
								<td class="px-6 py-3 text-sm text-gray-900 dark:text-gray-100">{sim.project_name}</td>
								<td class="px-6 py-3 text-sm text-right text-gray-600 dark:text-gray-400">{sim.iterations.toLocaleString()}</td>
								<td class="px-6 py-3 text-sm text-right text-gray-600 dark:text-gray-400">{sim.deterministic_days.toFixed(1)}d</td>
								<td class="px-6 py-3 text-sm text-right font-medium text-blue-600">{sim.p50_days.toFixed(1)}d</td>
								<td class="px-6 py-3 text-sm text-right font-medium text-orange-600">{sim.p80_days.toFixed(1)}d</td>
								<td class="px-6 py-3 text-sm text-right text-gray-600 dark:text-gray-400">{sim.mean_days.toFixed(1)}d</td>
								<td class="px-6 py-3 w-32">
									<div class="flex items-center gap-0.5 h-3">
										<div class="h-full rounded bg-blue-400 opacity-40" style="width: {(sim.deterministic_days / Math.max(sim.p80_days, sim.deterministic_days, 1)) * 100}%"></div>
									</div>
									<div class="flex items-center gap-0.5 h-3 -mt-0.5">
										<div class="h-full rounded bg-orange-500 opacity-60" style="width: {(sim.p80_days / Math.max(sim.p80_days, sim.deterministic_days, 1)) * 100}%"></div>
									</div>
								</td>
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
