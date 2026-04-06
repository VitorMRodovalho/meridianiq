<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { supabase } from '$lib/supabase';
	import GaugeChart from '$lib/components/charts/GaugeChart.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';

	interface FeatureImportance {
		feature: string;
		importance: number;
	}

	interface DurationResult {
		predicted_duration_days: number;
		confidence_low: number;
		confidence_high: number;
		actual_duration_days: number;
		accuracy_pct: number;
		feature_importances: FeatureImportance[];
		model_type: string;
		methodology: string;
	}

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let result = $state<DurationResult | null>(null);
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
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/duration-prediction`, { headers });
			if (!res.ok) throw new Error(await res.text());
			result = await res.json();
			toastSuccess(`Predicted: ${result!.predicted_duration_days} days (${result!.confidence_low}-${result!.confidence_high})`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	const featureItems = $derived(
		result?.feature_importances
			? result.feature_importances.slice(0, 10).map(f => ({
				label: f.feature,
				value: Math.round(f.importance * 100),
			}))
			: []
	);

	const gaugeValue = $derived(result ? Math.min(result.accuracy_pct || 0, 100) : 0);

	const rangeTotal = $derived(result ? (result.confidence_high * 1.2) || 1 : 1);
	const rangeLowPct = $derived(result ? (result.confidence_low / rangeTotal) * 100 : 0);
	const rangeWidthPct = $derived(result ? ((result.confidence_high - result.confidence_low) / rangeTotal) * 100 : 0);
	const rangePredictPct = $derived(result ? (result.predicted_duration_days / rangeTotal) * 100 : 0);
	const rangeActualPct = $derived(result ? (result.actual_duration_days / rangeTotal) * 100 : 0);
</script>

<svelte:head>
	<title>Duration Prediction - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900">Duration Prediction</h1>
		<p class="text-gray-500 mt-1">ML ensemble trained on benchmark data (AbdElMottaleb 2025, Breiman 2001)</p>
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
				{loading ? 'Predicting...' : 'Predict Duration'}
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
				<p class="text-lg font-bold text-blue-600">{result.predicted_duration_days}d</p>
				<p class="text-xs text-gray-500 uppercase">Predicted</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-gray-900">{result.actual_duration_days}d</p>
				<p class="text-xs text-gray-500 uppercase">Actual</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-green-600">{result.confidence_low}d — {result.confidence_high}d</p>
				<p class="text-xs text-gray-500 uppercase">95% Confidence</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold capitalize text-gray-700">{result.model_type}</p>
				<p class="text-xs text-gray-500 uppercase">Model</p>
			</div>
		</div>

		<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
			<div class="bg-white rounded-lg border border-gray-200 p-6">
				<GaugeChart value={gaugeValue} max={100} label="Accuracy" />
			</div>
			{#if featureItems.length > 0}
				<BarChart data={featureItems} title="Top Feature Importances (%)" />
			{/if}
		</div>

		<!-- Duration range visual -->
		<div class="bg-white rounded-lg border border-gray-200 p-6">
			<h2 class="text-lg font-semibold text-gray-900 mb-4">Duration Range</h2>
			<div class="relative h-12 bg-gray-100 rounded-lg overflow-hidden">
				<div class="absolute top-0 h-full bg-blue-100 rounded" style="left: {rangeLowPct}%; width: {rangeWidthPct}%"></div>
				<div class="absolute top-0 h-full w-0.5 bg-blue-600" style="left: {rangePredictPct}%" title="Predicted"></div>
				{#if result.actual_duration_days > 0}
					<div class="absolute top-0 h-full w-0.5 bg-green-600" style="left: {rangeActualPct}%" title="Actual"></div>
				{/if}
			</div>
			<div class="flex justify-between mt-2 text-xs text-gray-500">
				<span>{result.confidence_low}d (low)</span>
				<span class="text-blue-600 font-medium">{result.predicted_duration_days}d predicted</span>
				<span>{result.confidence_high}d (high)</span>
			</div>
			<p class="text-xs text-gray-400 mt-3">{result.methodology}</p>
		</div>
	{/if}
</main>
