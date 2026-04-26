<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { supabase } from '$lib/supabase';
	import BarChart from '$lib/components/charts/BarChart.svelte';
	import GaugeChart from '$lib/components/charts/GaugeChart.svelte';

	interface EntropyResult {
		entropy: number;
		max_entropy: number;
		normalized_entropy: number;
		bucket_distribution: Record<string, number>;
		interpretation: string;
		methodology: string;
	}

	interface ConstraintResult {
		baseline_constraints: number;
		update_constraints: number;
		added: number;
		removed: number;
		accumulation_rate: number;
		interpretation: string;
		methodology: string;
	}

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let baselineProject: string = $state('');
	let entropy = $state<EntropyResult | null>(null);
	let constraints = $state<ConstraintResult | null>(null);
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
		entropy = null;
		constraints = null;
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = session?.access_token
				? { Authorization: `Bearer ${session.access_token}` }
				: {};

			// Float entropy
			const entropyRes = await fetch(`${BASE}/api/v1/projects/${selectedProject}/float-entropy`, { headers });
			if (entropyRes.ok) entropy = await entropyRes.json();

			// Constraint accumulation (needs baseline)
			if (baselineProject) {
				const constRes = await fetch(`${BASE}/api/v1/projects/${selectedProject}/constraint-accumulation?baseline_id=${baselineProject}`, { headers });
				if (constRes.ok) constraints = await constRes.json();
			}

			toastSuccess(`Float entropy: ${entropy?.normalized_entropy.toFixed(2) ?? 'N/A'}`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	const bucketItems = $derived(
		entropy ? Object.entries(entropy.bucket_distribution).map(([label, value]) => ({ label, value })) : []
	);

	const entropyPct = $derived(entropy ? Math.round(entropy.normalized_entropy * 100) : 0);
</script>

<svelte:head>
	<title>{$t('page.float_trends')} - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.float_trends')}</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">{$t('float_trends.subtitle')}</p>
	</div>

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<div class="flex items-end gap-4 flex-wrap">
			<div class="flex-1 min-w-48">
				<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('float_trends.update_label')}</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm">
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<div class="flex-1 min-w-48">
				<label for="baseline" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('float_trends.baseline_label')}</label>
				<select id="baseline" bind:value={baselineProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm">
					<option value="">{$t('float_trends.baseline_none')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<button onclick={analyze} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? $t('float_trends.analyzing') : $t('float_trends.analyze_button')}
			</button>
			{#if selectedProject}
				<a href="/schedule?project={selectedProject}" class="px-3 py-2 text-xs text-teal-600 hover:text-teal-800 font-medium">{$t('common.view_schedule')}</a>
			{/if}
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 mb-6">
			<p class="text-red-700 text-sm">{error}</p>
		</div>
	{/if}

	{#if entropy}
		<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-blue-600">{entropy.entropy.toFixed(3)}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('float_trends.kpi_shannon')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-gray-900 dark:text-gray-100">{entropy.max_entropy.toFixed(3)}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('float_trends.kpi_max')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold {entropy.normalized_entropy >= 0.7 ? 'text-green-600' : entropy.normalized_entropy >= 0.4 ? 'text-amber-600' : 'text-red-600'}">
					{(entropy.normalized_entropy * 100).toFixed(1)}%
				</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('float_trends.kpi_normalized')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-gray-700 dark:text-gray-300">{Object.keys(entropy.bucket_distribution).length}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('float_trends.kpi_buckets')}</p>
			</div>
		</div>

		<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
				<GaugeChart value={entropyPct} max={100} label={$t('float_trends.gauge_label')} />
				<p class="text-xs text-gray-500 dark:text-gray-400 mt-2 text-center">{entropy.interpretation}</p>
			</div>
			<BarChart data={bucketItems} title={$t('float_trends.bucket_chart_title')} />
		</div>
		<p class="text-xs text-gray-400 mb-6">{entropy.methodology}</p>
	{/if}

	{#if constraints}
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{$t('float_trends.constraints_heading')}</h2>
			<div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
				<div class="text-center">
					<p class="text-lg font-bold text-gray-900 dark:text-gray-100">{constraints.baseline_constraints}</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('float_trends.kpi_baseline')}</p>
				</div>
				<div class="text-center">
					<p class="text-lg font-bold text-gray-900 dark:text-gray-100">{constraints.update_constraints}</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('float_trends.kpi_update')}</p>
				</div>
				<div class="text-center">
					<p class="text-lg font-bold text-green-600">+{constraints.added}</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('float_trends.kpi_added')}</p>
				</div>
				<div class="text-center">
					<p class="text-lg font-bold text-red-600">-{constraints.removed}</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('float_trends.kpi_removed')}</p>
				</div>
				<div class="text-center">
					<p class="text-lg font-bold {constraints.accumulation_rate > 20 ? 'text-red-600' : constraints.accumulation_rate > 10 ? 'text-amber-600' : 'text-green-600'}">
						{constraints.accumulation_rate.toFixed(1)}%
					</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('float_trends.kpi_rate')}</p>
				</div>
			</div>
			<p class="text-sm text-gray-600 dark:text-gray-400">{constraints.interpretation}</p>
			<p class="text-xs text-gray-400 mt-2">{constraints.methodology}</p>
		</div>
	{/if}
</main>
