<script lang="ts">
	import { getProjects, getRevisionTrends } from '$lib/api';
	import type { RevisionTrendsResponse } from '$lib/types';
	import { error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import MultiRevisionSCurveChart from '$lib/components/charts/MultiRevisionSCurveChart.svelte';

	let projects = $state<{ project_id: string; name: string }[]>([]);
	let selectedProject = $state<string>('');
	let trends = $state<RevisionTrendsResponse | null>(null);
	let loading = $state<boolean>(false);
	let errMsg = $state<string>('');

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			errMsg = e instanceof Error ? e.message : String(e);
		}
	}

	async function analyze() {
		if (!selectedProject) return;
		loading = true;
		errMsg = '';
		trends = null;
		try {
			trends = await getRevisionTrends(selectedProject);
		} catch (e) {
			errMsg = e instanceof Error ? e.message : String(e);
			toastError(errMsg);
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadProjects();
	});

	const hasExecuted = $derived(trends?.curves.some((c) => c.is_executed) ?? false);
	const isSingleRev = $derived(trends !== null && trends.curves.length === 1);
	const isEmpty = $derived(trends !== null && trends.curves.length === 0);

	// True when at least one curve is missing data_date — chart falls back to
	// pooled day_offset axis (NOT calendar-aligned per AACE 29R-03 Window
	// Analysis); page surfaces a disclosure. DA exit-council finding P1#4.
	const isCalendarAligned = $derived.by(() => {
		if (trends === null || trends.curves.length === 0) return true;
		return trends.curves.every((c) => c.data_date != null && c.data_date !== '');
	});

	// CI-aware slope coloring — red ONLY when CI is fully > 0 (significantly
	// delayed); green ONLY when CI fully < 0 (significantly accelerating);
	// neutral gray when CI straddles zero (noise within uncertainty). DA
	// exit-council finding P1#1: simple sign-based >= 0 painted noise as
	// alarmist red and rendered slope=0 as delayed.
	function slopeColorClass(b: { ci_lower: number; ci_upper: number }): string {
		if (b.ci_lower > 0) return 'text-red-600 dark:text-red-400';
		if (b.ci_upper < 0) return 'text-green-600 dark:text-green-400';
		return 'text-gray-700 dark:text-gray-300';
	}

	// Lookup the human-friendly revision label (R{revision_number}) for a
	// change-point entry, with fallback to revision_index. DA exit-council
	// finding P1#2: chart and list previously used divergent identifiers
	// when revision_number was sparse.
	function changePointLabel(cp: { revision_index: number }): string {
		if (trends == null) return `#${cp.revision_index}`;
		const c = trends.curves[cp.revision_index];
		if (c?.revision_number != null) return `R${c.revision_number}`;
		return `#${cp.revision_index}`;
	}

	// Methodology cite-or-fail. Frontend hardcodes the AACE 29R-03 reference
	// as a defensive fallback; if the backend response ships an empty
	// methodology field (regression / refactor), the page still cites the
	// standard rather than silently rendering a generic dashboard. DA exit-
	// council finding P1#5.
	const METHODOLOGY_FALLBACK =
		'AACE RP 29R-03 §"Window analysis" (multi-revision overlay primitive). CUSUM change-point per Page (1954, Biometrika 41) — applied as a separate exploratory SPC layer.';
	const methodologyText = $derived(
		trends?.methodology && trends.methodology.length > 0
			? trends.methodology
			: METHODOLOGY_FALLBACK
	);
</script>

<svelte:head>
	<title>{$t('page.revision_trends')} - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">
			{$t('page.revision_trends')}
		</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">
			{$t('revision_trends.subtitle')}
		</p>
	</div>

	<div
		class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6"
	>
		<div class="flex items-end gap-4 flex-wrap">
			<div class="flex-1 min-w-48">
				<label
					for="project"
					class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
				>
					{$t('revision_trends.project_label')}
				</label>
				<select
					id="project"
					bind:value={selectedProject}
					class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
				>
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<button
				onclick={analyze}
				disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
			>
				{loading ? $t('revision_trends.analyzing') : $t('revision_trends.analyze_button')}
			</button>
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if errMsg}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-900 rounded-lg p-4 mb-6">
			<p class="text-red-700 dark:text-red-400 text-sm">{errMsg}</p>
		</div>
	{/if}

	{#if trends && !loading}
		{#if isEmpty}
			<div
				class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-8 mb-6 text-center"
			>
				<p class="text-gray-500 dark:text-gray-400 text-sm">
					{$t('revision_trends.empty_no_revisions')}
				</p>
			</div>
		{:else}
			{#if trends.slope_band}
				{@const sb = trends.slope_band}
				<div
					class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-6"
				>
					<p class="text-xs uppercase text-gray-500 dark:text-gray-400 mb-2">
						{$t('revision_trends.slope_metric_label')}
					</p>
					<div class="flex items-baseline gap-3 flex-wrap">
						<span class="text-2xl font-bold {slopeColorClass(sb)}">
							{sb.slope_days_per_revision > 0 ? '+' : ''}{sb.slope_days_per_revision.toFixed(1)}
						</span>
						<span class="text-sm text-gray-600 dark:text-gray-400">
							{$t('revision_trends.slope_unit')}
						</span>
						<span class="text-sm text-gray-500 dark:text-gray-500">
							{$t('revision_trends.slope_ci_prefix')}
							[{sb.ci_lower.toFixed(1)}, {sb.ci_upper.toFixed(1)}]
						</span>
						<span class="text-xs text-gray-400 dark:text-gray-500">
							n={sb.horizon_revisions}
						</span>
					</div>
				</div>
			{/if}

			<MultiRevisionSCurveChart
				curves={trends.curves}
				changePoints={trends.change_points}
				title={$t('revision_trends.chart_title')}
				ariaLabel={$t('revision_trends.chart_aria_label')}
				executedLabel={$t('revision_trends.executed_curve_label')}
				changePointLabel={$t('revision_trends.change_point_label')}
			/>

			{#if isSingleRev && !hasExecuted}
				<p class="text-xs text-gray-400 dark:text-gray-500 mt-3 italic">
					{$t('revision_trends.empty_single_revision')}
				</p>
			{/if}

			{#if trends.change_points.length > 0}
				<div
					class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mt-6"
				>
					<p class="text-xs uppercase text-gray-500 dark:text-gray-400 mb-2">
						{$t('revision_trends.change_points_heading')}
					</p>
					<ul class="space-y-1">
						{#each trends.change_points as cp}
							<li class="text-sm text-gray-700 dark:text-gray-300 flex gap-2">
								<span class="text-red-500 dark:text-red-400 font-medium min-w-12">
									{changePointLabel(cp)}
								</span>
								<span>{cp.description}</span>
							</li>
						{/each}
					</ul>
				</div>
			{/if}

			{#if !isCalendarAligned}
				<p class="text-xs text-amber-700 dark:text-amber-400 mt-3 italic">
					{$t('revision_trends.axis_not_calendar_disclosure')}
				</p>
			{/if}

			<p class="text-xs text-gray-500 dark:text-gray-400 mt-6">
				<span class="font-medium">{$t('revision_trends.methodology_label')}:</span>
				{methodologyText}
			</p>

			{#if trends.notes.length > 0}
				<ul class="text-xs text-gray-500 dark:text-gray-500 mt-2 list-disc pl-5 space-y-0.5">
					{#each trends.notes as note}
						<li>{note}</li>
					{/each}
				</ul>
			{/if}
		{/if}
	{/if}
</main>
