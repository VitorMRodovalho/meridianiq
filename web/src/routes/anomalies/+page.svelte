<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { supabase } from '$lib/supabase';
	import ScatterChart from '$lib/components/charts/ScatterChart.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';

	interface Anomaly {
		activity_id: string;
		activity_name: string;
		anomaly_type: string;
		severity: string;
		value: number;
		expected_range: { low: number; high: number };
		z_score: number;
		description: string;
	}

	interface AnomalyResult {
		total_activities: number;
		anomalies: Anomaly[];
		summary: Record<string, number>;
		methodology: string;
	}

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let result = $state<AnomalyResult | null>(null);
	let loading: boolean = $state(false);
	let error: string = $state('');

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
		}
	}

	async function analyze() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		result = null;
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = session?.access_token
				? { Authorization: `Bearer ${session.access_token}` }
				: {};
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/anomalies`, { headers });
			if (!res.ok) throw new Error(await res.text());
			result = await res.json();
			toastSuccess(`Found ${result!.anomalies.length} anomalies in ${result!.total_activities} activities`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	const severityColor = (s: string) => {
		if (s === 'high') return 'bg-red-100 text-red-800';
		if (s === 'medium') return 'bg-amber-100 text-amber-800';
		return 'bg-green-100 text-green-800';
	};

	const scatterData = $derived(
		result ? result.anomalies.map(a => ({
			x: a.value,
			y: Math.abs(a.z_score),
			label: a.activity_name || a.activity_id,
		})) : []
	);

	const typeCounts = $derived(
		result ? Object.entries(result.summary).map(([label, value]) => ({ label, value })) : []
	);
</script>

<svelte:head>
	<title>Anomaly Detection - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900">Anomaly Detection</h1>
		<p class="text-gray-500 mt-1">Statistical outlier detection using IQR and z-score methods</p>
	</div>

	<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
		<div class="flex items-end gap-4">
			<div class="flex-1">
				<label for="project" class="block text-sm font-medium text-gray-700 mb-1">Project</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
					<option value="">Choose project...</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<button onclick={analyze} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Scanning...' : 'Detect Anomalies'}
			</button>
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
			<p class="text-red-700 text-sm">{error}</p>
		</div>
	{/if}

	{#if result}
		<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-gray-900">{result.total_activities}</p>
				<p class="text-xs text-gray-500 uppercase">Activities Scanned</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-red-600">{result.anomalies.length}</p>
				<p class="text-xs text-gray-500 uppercase">Anomalies Found</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-amber-600">{result.anomalies.filter(a => a.severity === 'high').length}</p>
				<p class="text-xs text-gray-500 uppercase">High Severity</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-blue-600">{Object.keys(result.summary).length}</p>
				<p class="text-xs text-gray-500 uppercase">Anomaly Types</p>
			</div>
		</div>

		{#if result.anomalies.length > 0}
			<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
				<ScatterChart
					data={scatterData}
					title="Anomaly Value vs Z-Score"
					xLabel="Value"
					yLabel="|Z-Score|"
				/>
				<BarChart
					data={typeCounts}
					title="Anomalies by Type"
				/>
			</div>

			<div class="bg-white rounded-lg border border-gray-200 p-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-3">Anomalies ({result.anomalies.length})</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-200">
								<th class="text-left py-2 px-3">Activity</th>
								<th class="text-left py-2 px-3">Type</th>
								<th class="text-left py-2 px-3">Severity</th>
								<th class="text-right py-2 px-3">Value</th>
								<th class="text-right py-2 px-3">Z-Score</th>
								<th class="text-left py-2 px-3">Description</th>
							</tr>
						</thead>
						<tbody>
							{#each result.anomalies as a}
								<tr class="border-b border-gray-100 hover:bg-gray-50">
									<td class="py-2 px-3 font-mono text-xs">{a.activity_name || a.activity_id}</td>
									<td class="py-2 px-3 capitalize">{a.anomaly_type}</td>
									<td class="py-2 px-3">
										<span class="px-2 py-0.5 rounded text-xs font-medium {severityColor(a.severity)}">{a.severity}</span>
									</td>
									<td class="py-2 px-3 text-right font-mono">{a.value.toFixed(1)}</td>
									<td class="py-2 px-3 text-right font-mono">{a.z_score.toFixed(2)}</td>
									<td class="py-2 px-3 text-gray-600 text-xs">{a.description}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<p class="text-xs text-gray-400 mt-3">{result.methodology}</p>
			</div>
		{/if}
	{/if}
</main>
