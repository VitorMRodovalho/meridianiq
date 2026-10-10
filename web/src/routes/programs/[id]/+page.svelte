<script lang="ts">
	import { page } from '$app/state';
	import {
		getProgramDetail,
		getProgramTrends,
		getProgramRollup,
		type ProgramListItem,
		type ProgramRevision
	} from '$lib/api';
	import TrendChart from '$lib/components/TrendChart.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import { t } from '$lib/i18n';
	import type { ProgramTrends } from '$lib/types';
	import type { ProgramRollup } from '$lib/api';

	const programId = $derived(page.params.id!);

	let program: ProgramListItem | null = $state(null);
	let revisions: ProgramRevision[] = $state([]);
	let trends: ProgramTrends | null = $state(null);

	// The time axis shows the data date only (labels arrive as timestamps).
	function dayLabels(tr: ProgramTrends): string[] {
		return tr.labels.map((l) => l.slice(0, 10));
	}
	let rollup: ProgramRollup | null = $state(null);
	let loading = $state(true);
	let error = $state('');

	// The page shows as soon as the program and its trends arrive; the
	// latest-revision summary fills in when it is ready, so a slow summary
	// never holds the whole page.
	let rollupLoading = $state(false);

	async function load(id: string) {
		loading = true;
		error = '';
		program = null;
		revisions = [];
		trends = null;
		rollup = null;
		rollupLoading = true;
		void loadRollup(id);
		try {
			const [detailRes, trendsRes] = await Promise.allSettled([
				getProgramDetail(id),
				getProgramTrends(id)
			]);
			// A newer navigation owns the page; drop this one's result.
			if (id !== programId) return;

			if (detailRes.status === 'fulfilled') {
				program = detailRes.value.program;
				revisions = detailRes.value.revisions ?? [];
			} else {
				error = $t('program_page.load_failed');
			}

			if (trendsRes.status === 'fulfilled') {
				trends = trendsRes.value;
			}
		} catch (e: unknown) {
			if (id !== programId) return;
			error = e instanceof Error ? e.message : $t('program_page.load_failed');
		} finally {
			if (id === programId) loading = false;
		}
	}

	async function loadRollup(id: string) {
		try {
			const value = await getProgramRollup(id);
			if (id === programId) rollup = value;
		} catch {
			// The summary is optional; the rest of the page stands without it.
		} finally {
			if (id === programId) rollupLoading = false;
		}
	}

	// Reload whenever the route moves to another program.
	$effect(() => {
		load(programId);
	});

	function healthScoreColor(score: number | null | undefined): string {
		if (score === null || score === undefined) return 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 border-gray-200 dark:border-gray-700';
		if (score >= 85) return 'bg-green-100 text-green-700 border-green-300 dark:bg-green-950 dark:text-green-300 dark:border-green-800';
		if (score >= 70) return 'bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800';
		if (score >= 50) return 'bg-yellow-100 text-yellow-700 border-yellow-300 dark:bg-yellow-950 dark:text-yellow-300 dark:border-yellow-800';
		return 'bg-red-100 text-red-700 border-red-300 dark:bg-red-950 dark:text-red-300 dark:border-red-800';
	}

	function formatDate(dateStr: string | null | undefined): string {
		if (!dateStr) return '—';
		try {
			// Data dates are stored as UTC midnight; formatting them in the
			// viewer's zone showed the day before west of Greenwich.
			return new Date(dateStr).toLocaleDateString(undefined, {
				year: 'numeric',
				month: 'short',
				day: 'numeric',
				timeZone: 'UTC'
			});
		} catch {
			return dateStr;
		}
	}

	function revisionCount(n: number): string {
		return n === 1
			? $t('program_pick.revision_one')
			: $t('program_pick.revisions').replace('{n}', String(n));
	}

	// Find health score for a given revision id from trends data
	function getRevisionHealthScore(revId: string): number | null {
		if (!trends) return null;
		const idx = trends.revisions.findIndex((r) => r.id === revId);
		if (idx === -1) return null;
		return trends.health_scores[idx] ?? null;
	}
</script>

<svelte:head>
	<title>{program ? String(program.name || $t('programs.unnamed')) : $t('common.loading')} — MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<!-- Back navigation -->
	<div class="mb-6">
		<a href="/programs" class="inline-flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors">
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
			</svg>
			{$t('program_page.back')}
		</a>
	</div>

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			{$t('program_page.loading')}
		</div>
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-6 text-red-700 dark:text-red-300" role="alert">
			<p class="font-semibold">{$t('program_page.error')}</p>
			<p class="text-sm mt-1">{error}</p>
		</div>
	{:else if program}
		<!-- Program Header -->
		<div class="mb-8">
			<div class="flex items-start justify-between">
				<div>
					<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{String(program.name || $t('programs.unnamed'))}</h1>
					{#if program.description}
						<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">{String(program.description)}</p>
					{/if}
				</div>
				<div class="flex items-center gap-2 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg px-4 py-2">
					<svg class="w-4 h-4 text-blue-600 dark:text-blue-400" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
					</svg>
					<span class="text-sm font-semibold text-blue-700 dark:text-blue-300">
						{revisionCount(revisions.length)}
					</span>
				</div>
			</div>
		</div>

		<!-- Rollup KPIs -->
		{#if rollupLoading && !rollup}
			<div class="mb-8" aria-busy="true">
				<p class="text-sm text-gray-500 dark:text-gray-400 mb-3">{$t('program_page.summary_loading')}</p>
				<div class="grid grid-cols-2 md:grid-cols-4 gap-3" aria-hidden="true">
					{#each Array(8) as _, i (i)}
						<div class="h-20 rounded-lg bg-gray-100 dark:bg-gray-800 animate-pulse"></div>
					{/each}
				</div>
			</div>
		{/if}
		{#if rollup}
			{@const m = rollup.latest_metrics}
			<div class="mb-8">
				<div class="flex items-baseline justify-between mb-4">
					<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
						{$t('program_page.latest_kpis')}
						<span class="text-xs font-normal text-gray-500 dark:text-gray-400 ml-2">
							{$t('program_page.rev').replace('{n}', String(rollup.latest_revision_number ?? '—'))}
							{#if rollup.latest_data_date}· {formatDate(rollup.latest_data_date)}{/if}
						</span>
					</h2>
					{#if rollup.trend_delta !== null}
						<span
							class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold {rollup.trend_direction ===
							'improving'
								? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
								: rollup.trend_direction === 'degrading'
									? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
									: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'}"
						>
							{$t(`program_page.trend_${rollup.trend_direction}`)}
							({rollup.trend_delta > 0 ? '+' : ''}{rollup.trend_delta.toFixed(1)})
						</span>
					{/if}
				</div>
				<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold {m.health_score !== undefined
							? healthScoreColor(m.health_score).split(' ')[1] || 'text-gray-900 dark:text-gray-100'
							: 'text-gray-400'}">
							{m.health_score !== undefined ? m.health_score.toFixed(0) : '—'}
						</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
							{$t('program_page.kpi_health')} {m.health_rating ? `· ${m.health_rating}` : ''}
						</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-purple-600 dark:text-purple-400">
							{m.dcma_score !== undefined ? m.dcma_score.toFixed(0) : '—'}
						</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
							DCMA {m.dcma_passed_count !== undefined
								? $t('program_page.dcma_passed')
										.replace('{p}', String(m.dcma_passed_count))
										.replace('{n}', String((m.dcma_passed_count ?? 0) + (m.dcma_failed_count ?? 0)))
								: ''}
						</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-blue-600 dark:text-blue-400">
							{m.critical_path_length_days !== undefined
								? m.critical_path_length_days.toFixed(1)
								: '—'}
						</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
							{$t('program_page.kpi_cp').replace('{n}', String(m.critical_activities_count ?? '—'))}
						</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p
							class="text-2xl font-bold {(m.negative_float_count ?? 0) > 0
								? 'text-red-600 dark:text-red-400'
								: 'text-gray-500 dark:text-gray-400'}"
						>
							{m.negative_float_count ?? 0}
						</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
							{$t('program_page.kpi_negative_float')}
						</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">
							{m.activity_count ?? '—'}
						</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('program_page.kpi_activities')}</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">
							{m.relationship_count ?? '—'}
						</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('program_page.kpi_relationships')}</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">
							{rollup.revision_count}
						</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('program_page.kpi_revisions')}</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p
							class="text-2xl font-bold {m.has_cycles
								? 'text-red-600 dark:text-red-400'
								: 'text-green-600 dark:text-green-400'}"
						>
							{m.has_cycles ? $t('program_page.yes') : $t('program_page.no')}
						</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('program_page.kpi_cycles')}</p>
					</div>
				</div>
			</div>
		{/if}

		<!-- Trend Charts (only if ≥2 revisions) -->
		{#if trends && trends.revision_count >= 2}
			<div class="mb-8">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{$t('program_page.trends')}</h2>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
					<TrendChart
						data={trends.health_scores}
						labels={dayLabels(trends)}
						title={$t('program_page.chart_health')}
						color="#3b82f6"
						height={200}
						formatValue={(v) => v.toFixed(0)}
					/>
					<TrendChart
						data={trends.dcma_scores}
						labels={dayLabels(trends)}
						title={$t('program_page.chart_dcma')}
						color="#8b5cf6"
						height={200}
						formatValue={(v) => v.toFixed(1)}
					/>
					{#if trends.alert_counts.some((v) => v !== null && v !== undefined)}
						<TrendChart
							data={trends.alert_counts}
							labels={dayLabels(trends)}
							title={$t('program_page.chart_alerts')}
							color="#ef4444"
							height={200}
							formatValue={(v) => v.toFixed(0)}
						/>
					{/if}
					<TrendChart
						data={trends.activity_counts}
						labels={dayLabels(trends)}
						title={$t('program_page.chart_activities')}
						color="#10b981"
						height={200}
						formatValue={(v) => v.toFixed(0)}
					/>
				</div>
			</div>
		{:else if trends && trends.revision_count === 1}
			<div class="mb-8 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-5 flex items-center gap-3">
				<svg class="w-5 h-5 text-blue-500 shrink-0" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
				</svg>
				<p class="text-sm text-blue-700 dark:text-blue-300">{$t('program_page.single_revision')}</p>
			</div>
		{/if}

		<!-- Revisions Table -->
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
			<div class="px-6 py-4 border-b border-gray-100 dark:border-gray-800">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{$t('program_page.revisions')}</h2>
			</div>
			{#if revisions.length === 0}
				<div class="px-6 py-8 text-center text-gray-400 dark:text-gray-500 text-sm">{$t('program_page.no_revisions')}</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800">
								<th class="text-left px-6 py-3 font-medium text-gray-500 dark:text-gray-400">#</th>
								<th class="text-left px-6 py-3 font-medium text-gray-500 dark:text-gray-400">{$t('program_page.col_data_date')}</th>
								<th class="text-left px-6 py-3 font-medium text-gray-500 dark:text-gray-400">{$t('program_page.col_schedule')}</th>
								<th class="text-left px-6 py-3 font-medium text-gray-500 dark:text-gray-400">{$t('program_page.kpi_activities')}</th>
								<th class="text-left px-6 py-3 font-medium text-gray-500 dark:text-gray-400">{$t('projects.col_status')}</th>
								<th class="text-left px-6 py-3 font-medium text-gray-500 dark:text-gray-400">{$t('program_page.col_health')}</th>
								<th class="text-left px-6 py-3 font-medium text-gray-500 dark:text-gray-400">{$t('program_page.col_uploaded')}</th>
								<th class="px-6 py-3"></th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-50 dark:divide-gray-800">
							{#each revisions as rev (rev.id)}
								{@const revObj = rev as unknown as Record<string, unknown>}
								{@const healthScore = getRevisionHealthScore(String(revObj.id ?? ''))}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
									<td class="px-6 py-4 font-medium text-gray-900 dark:text-gray-100">
										{$t('program_page.rev').replace('{n}', String(revObj.revision_number ?? '?'))}
									</td>
									<td class="px-6 py-4 text-gray-600 dark:text-gray-400">
										{formatDate(revObj.data_date as string | null)}
									</td>
									<td class="px-6 py-4 text-gray-600 dark:text-gray-400 text-xs">
										{String(revObj.project_name ?? revObj.filename ?? '—')}
									</td>
									<td class="px-6 py-4 text-gray-600 dark:text-gray-400">
										{revObj.activity_count ?? '—'}
									</td>
									<td class="px-6 py-4">
										<StatusBadge
											status={(revObj.status as 'pending' | 'ready' | 'failed' | undefined) ?? 'ready'}
										/>
									</td>
									<td class="px-6 py-4">
										{#if healthScore !== null}
											<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border {healthScoreColor(healthScore)}">
												{healthScore.toFixed(0)}
											</span>
										{:else}
											<span class="text-gray-400 dark:text-gray-500 text-xs">—</span>
										{/if}
									</td>
									<td class="px-6 py-4 text-gray-500 dark:text-gray-400 text-xs">
										{formatDate((revObj.created_at ?? revObj.uploaded_at) as string | null)}
									</td>
									<td class="px-6 py-4">
										<a
											href="/projects/{revObj.id}"
											class="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 text-xs font-medium transition-colors"
										>
											{$t('program_page.analyze')}
											<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
											</svg>
										</a>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	{/if}
</div>
