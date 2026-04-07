<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { supabase } from '$lib/supabase';
	import ScatterChart from '$lib/components/charts/ScatterChart.svelte';
	import HeatMapChart from '$lib/components/charts/HeatMapChart.svelte';

	interface ActivityPrediction {
		activity_id: string;
		activity_name: string;
		risk_score: number;
		risk_level: string;
		top_factors: { factor: string; weight: number }[];
		predicted_delay_days: number;
	}

	interface DelayPredictionResult {
		total_activities: number;
		at_risk_count: number;
		high_risk_count: number;
		predictions: ActivityPrediction[];
		model_type: string;
		methodology: string;
	}

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let modelType: string = $state('rules');
	let result = $state<DelayPredictionResult | null>(null);
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
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/delay-prediction?model=${modelType}`, { headers });
			if (!res.ok) throw new Error(await res.text());
			result = await res.json();
			toastSuccess(`${result!.high_risk_count} high-risk activities identified`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	const riskColor = (level: string) => {
		if (level === 'high') return 'bg-red-100 text-red-800';
		if (level === 'medium') return 'bg-amber-100 text-amber-800';
		return 'bg-green-100 text-green-800';
	};

	const scatterPoints = $derived(
		result ? result.predictions.map(p => ({
			x: p.predicted_delay_days,
			y: p.risk_score,
			label: p.activity_name || p.activity_id,
		})) : []
	);

	const heatItems = $derived(
		result ? result.predictions.filter(p => p.risk_level !== 'low').map(p => ({
			x: p.predicted_delay_days,
			y: p.risk_score,
			label: p.activity_name || p.activity_id,
		})) : []
	);
</script>

<svelte:head>
	<title>Delay Prediction - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900">Delay Prediction</h1>
		<p class="text-gray-500 mt-1">Activity-level risk scoring with explainable factors (Gondia et al. 2021)</p>
	</div>

	<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
		<div class="flex items-end gap-4">
			<div class="flex-1">
				<label for="project" class="block text-sm font-medium text-gray-700 mb-1">{$t('common.project')}</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<div class="w-36">
				<label for="model" class="block text-sm font-medium text-gray-700 mb-1">Model</label>
				<select id="model" bind:value={modelType} class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
					<option value="rules">Rule-Based</option>
					<option value="ml">ML Ensemble</option>
				</select>
			</div>
			<button onclick={analyze} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Predicting...' : 'Predict Delays'}
			</button>
			{#if selectedProject}
				<a href="/schedule?project={selectedProject}" class="px-3 py-2 text-xs text-teal-600 hover:text-teal-800 font-medium">View Schedule</a>
			{/if}
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
				<p class="text-xs text-gray-500 uppercase">Activities</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-amber-600">{result.at_risk_count}</p>
				<p class="text-xs text-gray-500 uppercase">At Risk</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-red-600">{result.high_risk_count}</p>
				<p class="text-xs text-gray-500 uppercase">High Risk</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-blue-600 capitalize">{result.model_type}</p>
				<p class="text-xs text-gray-500 uppercase">Model</p>
			</div>
		</div>

		<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
			<ScatterChart
				data={scatterPoints}
				title="Delay Risk Scatter"
				xLabel="Predicted Delay (days)"
				yLabel="Risk Score"
			/>
			<HeatMapChart
				items={heatItems}
				title="Risk Heat Map (Medium + High)"
			/>
		</div>

		{#if result.predictions.length > 0}
			<div class="bg-white rounded-lg border border-gray-200 p-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-3">Predictions ({result.predictions.length})</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-200">
								<th class="text-left py-2 px-3">Activity</th>
								<th class="text-left py-2 px-3">Risk Level</th>
								<th class="text-right py-2 px-3">Score</th>
								<th class="text-right py-2 px-3">Predicted Delay</th>
								<th class="text-left py-2 px-3">Top Factors</th>
							</tr>
						</thead>
						<tbody>
							{#each result.predictions.slice(0, 50) as p}
								<tr class="border-b border-gray-100 hover:bg-gray-50">
									<td class="py-2 px-3 font-mono text-xs">{p.activity_name || p.activity_id}</td>
									<td class="py-2 px-3">
										<span class="px-2 py-0.5 rounded text-xs font-medium {riskColor(p.risk_level)}">{p.risk_level}</span>
									</td>
									<td class="py-2 px-3 text-right font-mono">{p.risk_score.toFixed(2)}</td>
									<td class="py-2 px-3 text-right font-mono">{p.predicted_delay_days.toFixed(1)}d</td>
									<td class="py-2 px-3 text-xs text-gray-600">
										{#if p.top_factors}
											{p.top_factors.slice(0, 3).map(f => f.factor).join(', ')}
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
					{#if result.predictions.length > 50}
						<p class="text-xs text-gray-400 mt-2">Showing top 50 of {result.predictions.length}</p>
					{/if}
				</div>
				<p class="text-xs text-gray-400 mt-3">{result.methodology}</p>
			</div>
		{/if}
	{/if}
</main>
