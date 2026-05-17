<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { supabase } from '$lib/supabase';
	import BarChart from '$lib/components/charts/BarChart.svelte';
	import GaugeChart from '$lib/components/charts/GaugeChart.svelte';

	interface PercentileRanking {
		metric_name: string;
		project_value: number;
		percentile: number;
		benchmark_mean: number;
		benchmark_median: number;
		interpretation: string;
	}

	interface CompareResult {
		rankings: PercentileRanking[];
		sample_size: number;
		methodology: string;
	}

	interface SummaryResult {
		total_projects: number;
		avg_activity_count: number;
		avg_duration_days: number;
		avg_dcma_score: number;
		avg_critical_pct: number;
	}

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let compareResult = $state<CompareResult | null>(null);
	let summary = $state<SummaryResult | null>(null);
	let loading: boolean = $state(false);
	let contributing: boolean = $state(false);
	let error: string = $state('');

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load projects';
			toastError(`Could not load projects: ${error}`);
			console.error('loadProjects (benchmarks):', e);
		}
	}

	async function loadSummary() {
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = session?.access_token
				? { Authorization: `Bearer ${session.access_token}` }
				: {};
			const res = await fetch(`${BASE}/api/v1/benchmarks/summary`, {
				headers,
				signal: AbortSignal.timeout(12_000),
			});
			if (res.ok) summary = await res.json();
		} catch { /* ignore — summary is optional context, not load-bearing */ }
	}

	async function compare() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		compareResult = null;
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = session?.access_token
				? { Authorization: `Bearer ${session.access_token}` }
				: {};
			const res = await fetch(`${BASE}/api/v1/benchmarks/compare/${selectedProject}`, {
				headers,
				signal: AbortSignal.timeout(12_000),
			});
			if (!res.ok) throw new Error(await res.text());
			compareResult = await res.json();
			toastSuccess(`Compared against ${compareResult!.sample_size} benchmarks`);
		} catch (e) {
			if ((e as Error)?.name === 'TimeoutError') {
				error = $t('error.request_timeout');
			} else {
				error = e instanceof Error ? e.message : 'Failed';
			}
			toastError(error);
		} finally {
			loading = false;
		}
	}

	async function contribute() {
		if (!selectedProject) return;
		contributing = true;
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = session?.access_token
				? { Authorization: `Bearer ${session.access_token}`, 'Content-Type': 'application/json' }
				: { 'Content-Type': 'application/json' };
			const res = await fetch(`${BASE}/api/v1/benchmarks/contribute?project_id=${selectedProject}`, {
				method: 'POST',
				headers,
				signal: AbortSignal.timeout(12_000),
			});
			if (!res.ok) throw new Error(await res.text());
			toastSuccess('Benchmark contributed (anonymized)');
			loadSummary();
		} catch (e) {
			if ((e as Error)?.name === 'TimeoutError') {
				toastError($t('error.request_timeout'));
			} else {
				toastError(e instanceof Error ? e.message : 'Failed');
			}
		} finally {
			contributing = false;
		}
	}

	$effect(() => { loadProjects(); loadSummary(); });

	const percentileColor = (pct: number) => {
		if (pct >= 75) return 'text-green-600';
		if (pct >= 50) return 'text-blue-600';
		if (pct >= 25) return 'text-amber-600';
		return 'text-red-600';
	};

	const rankingItems = $derived(
		compareResult ? compareResult.rankings.map(r => ({
			label: r.metric_name,
			value: Math.round(r.percentile),
		})) : []
	);
</script>

<svelte:head>
	<title>{$t('page.benchmarks')} - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.benchmarks')}</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">{$t('benchmarks.subtitle')}</p>
	</div>

	{#if summary}
		<div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-gray-900 dark:text-gray-100">{summary.total_projects}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('benchmarks.kpi_projects_db')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-blue-600">{Math.round(summary.avg_activity_count)}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('benchmarks.kpi_avg_activities')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-gray-700 dark:text-gray-300">{Math.round(summary.avg_duration_days)}d</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('benchmarks.kpi_avg_duration')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-green-600">{summary.avg_dcma_score?.toFixed(1) ?? 'N/A'}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('benchmarks.kpi_avg_dcma')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-lg font-bold text-amber-600">{summary.avg_critical_pct?.toFixed(1) ?? 'N/A'}%</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('benchmarks.kpi_avg_critical')}</p>
			</div>
		</div>
	{/if}

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<div class="flex items-end gap-4">
			<div class="flex-1">
				<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('common.project')}</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm">
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<button onclick={compare} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? $t('benchmarks.comparing') : $t('benchmarks.compare_button')}
			</button>
			{#if selectedProject}
				<a href="/schedule?project={selectedProject}" class="px-3 py-2 text-xs text-teal-600 hover:text-teal-800 font-medium">{$t('common.view_schedule')}</a>
			{/if}
			<button onclick={contribute} disabled={!selectedProject || contributing}
				class="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50">
				{contributing ? $t('benchmarks.contributing') : $t('benchmarks.contribute_button')}
			</button>
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 mb-6">
			<p class="text-red-700 text-sm">{error}</p>
		</div>
	{/if}

	{#if compareResult}
		<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
			<BarChart data={rankingItems} title={$t('benchmarks.bar_title')} />
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
				<p class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{$t('benchmarks.sample_prefix')}: {compareResult.sample_size} {$t('benchmarks.sample_suffix')}</p>
				{#each compareResult.rankings as r}
					<div class="flex items-center justify-between py-2 border-b border-gray-100">
						<span class="text-sm text-gray-600 dark:text-gray-400">{r.metric_name}</span>
						<div class="flex items-center gap-3">
							<span class="text-xs text-gray-400">{$t('benchmarks.yours_label')}: {r.project_value.toFixed(1)}</span>
							<span class="text-xs text-gray-400">{$t('benchmarks.median_label')}: {r.benchmark_median.toFixed(1)}</span>
							<span class="text-sm font-bold {percentileColor(r.percentile)}">P{Math.round(r.percentile)}</span>
						</div>
					</div>
				{/each}
			</div>
		</div>

		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">{$t('benchmarks.detail_heading')}</h2>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-200 dark:border-gray-700">
							<th class="text-left py-2 px-3">{$t('benchmarks.col_metric')}</th>
							<th class="text-right py-2 px-3">{$t('benchmarks.col_your_value')}</th>
							<th class="text-right py-2 px-3">{$t('benchmarks.col_mean')}</th>
							<th class="text-right py-2 px-3">{$t('benchmarks.col_median')}</th>
							<th class="text-right py-2 px-3">{$t('benchmarks.col_percentile')}</th>
							<th class="text-left py-2 px-3">{$t('benchmarks.col_interpretation')}</th>
						</tr>
					</thead>
					<tbody>
						{#each compareResult.rankings as r}
							<tr class="border-b border-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800">
								<td class="py-2 px-3 font-medium">{r.metric_name}</td>
								<td class="py-2 px-3 text-right font-mono">{r.project_value.toFixed(2)}</td>
								<td class="py-2 px-3 text-right text-gray-500 dark:text-gray-400">{r.benchmark_mean.toFixed(2)}</td>
								<td class="py-2 px-3 text-right text-gray-500 dark:text-gray-400">{r.benchmark_median.toFixed(2)}</td>
								<td class="py-2 px-3 text-right font-bold {percentileColor(r.percentile)}">P{Math.round(r.percentile)}</td>
								<td class="py-2 px-3 text-xs text-gray-600 dark:text-gray-400">{r.interpretation}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="text-xs text-gray-400 mt-3">{compareResult.methodology}</p>
		</div>
	{/if}
</main>
