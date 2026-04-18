<script lang="ts">
	import { getProjects, getProjectAlerts } from '$lib/api';
	import { error as toastError, success as toastSuccess } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';
	import type { AlertsResponse } from '$lib/types';

	let projects: { project_id: string; name: string; activity_count?: number }[] = $state([]);
	let selectedProject = $state('');
	let baselineProject = $state('');
	let result = $state<AlertsResponse | null>(null);
	let loading = $state(false);
	let error = $state('');

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch { /* ignore */ }
	}

	async function analyze() {
		if (!selectedProject || !baselineProject) return;
		loading = true;
		error = '';
		result = null;
		try {
			result = await getProjectAlerts(selectedProject, baselineProject);
			toastSuccess(`Found ${result.total_alerts} alerts`);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Analysis failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	function severityBadge(sev: string): string {
		if (sev === 'critical') return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300';
		if (sev === 'warning') return 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300';
		return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300';
	}

	function severityIcon(sev: string): string {
		if (sev === 'critical') return '!!';
		if (sev === 'warning') return '!';
		return 'i';
	}

	const impactChart = $derived(
		result ? result.alerts
			.filter(a => a.projected_impact_days > 0)
			.sort((a, b) => b.projected_impact_days - a.projected_impact_days)
			.slice(0, 10)
			.map(a => ({
				label: a.title.length > 25 ? a.title.slice(0, 25) + '...' : a.title,
				value: a.projected_impact_days,
				color: a.severity === 'critical' ? '#ef4444' : a.severity === 'warning' ? '#f59e0b' : '#3b82f6',
			})) : []
	);
</script>

<svelte:head>
	<title>{$t('page.alerts')} | MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.alerts')}</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">12-rule early warning engine based on GAO Schedule Assessment Guide</p>
	</div>

	<!-- Controls -->
	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<div class="flex items-end gap-4 flex-wrap">
			<div class="flex-1 min-w-[200px]">
				<label for="baseline" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Baseline Schedule</label>
				<select id="baseline" bind:value={baselineProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 px-3 py-2 text-sm">
					<option value="">Select baseline...</option>
					{#each projects.filter(p => p.project_id !== selectedProject) as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<div class="flex-1 min-w-[200px]">
				<label for="update" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Update Schedule</label>
				<select id="update" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 px-3 py-2 text-sm">
					<option value="">Select update...</option>
					{#each projects.filter(p => p.project_id !== baselineProject) as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<button onclick={analyze} disabled={!selectedProject || !baselineProject || loading}
				class="px-6 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Scanning...' : 'Run Early Warning'}
			</button>
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6">
			<p class="text-red-700 dark:text-red-400 text-sm">{error}</p>
		</div>
	{/if}

	{#if result}
		<!-- Summary KPIs -->
		<div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{result.total_alerts}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Total Alerts</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-2xl font-bold text-red-600">{result.critical_count}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Critical</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-2xl font-bold text-amber-600">{result.warning_count}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Warning</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-2xl font-bold text-blue-600">{result.info_count}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Info</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
				<p class="text-2xl font-bold {result.aggregate_score > 70 ? 'text-red-600' : result.aggregate_score > 40 ? 'text-amber-600' : 'text-green-600'}">{result.aggregate_score.toFixed(0)}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Risk Score</p>
			</div>
		</div>

		<!-- Impact Chart -->
		{#if impactChart.length > 0}
			<div class="mb-6">
				<BarChart data={impactChart} title="Projected Impact (days)" horizontal height={Math.max(180, impactChart.length * 32)} />
			</div>
		{/if}

		<!-- Alert Cards -->
		{#if result.alerts.length > 0}
			<div class="space-y-3">
				{#each result.alerts.sort((a, b) => b.alert_score - a.alert_score) as alert}
					<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
						<div class="flex items-start gap-3">
							<span class="mt-0.5 w-6 h-6 flex items-center justify-center rounded-full text-[10px] font-bold {severityBadge(alert.severity)}">
								{severityIcon(alert.severity)}
							</span>
							<div class="flex-1 min-w-0">
								<div class="flex items-center gap-2 mb-1">
									<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{alert.title}</h3>
									<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase {severityBadge(alert.severity)}">{alert.severity}</span>
									<span class="text-[10px] text-gray-400 font-mono">{alert.rule_id}</span>
								</div>
								<p class="text-sm text-gray-600 dark:text-gray-400">{alert.description}</p>
								<div class="flex items-center gap-4 mt-2 text-xs text-gray-500 dark:text-gray-400">
									<span>{alert.affected_activities.length} activities affected</span>
									{#if alert.projected_impact_days > 0}
										<span class="text-red-500 font-semibold">+{alert.projected_impact_days}d projected impact</span>
									{/if}
									<span>Confidence: {(alert.confidence * 100).toFixed(0)}%</span>
									<span>Score: {alert.alert_score.toFixed(1)}</span>
								</div>
							</div>
						</div>
					</div>
				{/each}
			</div>
		{:else}
			<div class="bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg p-6 text-center">
				<p class="text-green-700 dark:text-green-300 font-semibold">No alerts detected</p>
				<p class="text-sm text-green-600 dark:text-green-400 mt-1">The schedule comparison shows no early warning indicators</p>
			</div>
		{/if}
	{/if}
</main>
