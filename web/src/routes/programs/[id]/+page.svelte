<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { getProgramDetail, getProgramTrends } from '$lib/api';
	import TrendChart from '$lib/components/TrendChart.svelte';
	import type { ProgramTrends } from '$lib/types';

	const programId = $derived($page.params.id);

	let program: Record<string, unknown> | null = $state(null);
	let revisions: Record<string, unknown>[] = $state([]);
	let trends: ProgramTrends | null = $state(null);
	let loading = $state(true);
	let error = $state('');

	onMount(async () => {
		try {
			const id = $page.params.id;
			const [detailRes, trendsRes] = await Promise.allSettled([
				getProgramDetail(id),
				getProgramTrends(id)
			]);

			if (detailRes.status === 'fulfilled') {
				program = detailRes.value.program;
				revisions = detailRes.value.revisions ?? [];
			} else {
				error = 'Program not found';
			}

			if (trendsRes.status === 'fulfilled') {
				trends = trendsRes.value;
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load program';
		} finally {
			loading = false;
		}
	});

	function healthScoreColor(score: number | null | undefined): string {
		if (score === null || score === undefined) return 'bg-gray-100 text-gray-500 border-gray-200';
		if (score >= 85) return 'bg-green-100 text-green-700 border-green-300';
		if (score >= 70) return 'bg-blue-100 text-blue-700 border-blue-300';
		if (score >= 50) return 'bg-yellow-100 text-yellow-700 border-yellow-300';
		return 'bg-red-100 text-red-700 border-red-300';
	}

	function formatDate(dateStr: string | null | undefined): string {
		if (!dateStr) return '—';
		try {
			return new Date(dateStr).toLocaleDateString(undefined, {
				year: 'numeric',
				month: 'short',
				day: 'numeric'
			});
		} catch {
			return dateStr;
		}
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
	<title>{program ? String(program.name ?? 'Program') : 'Loading...'} — MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<!-- Back navigation -->
	<div class="mb-6">
		<a href="/" class="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 transition-colors">
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
			</svg>
			Back to Dashboard
		</a>
	</div>

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			Loading program...
		</div>
	{:else if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-6 text-red-700">
			<p class="font-semibold">Error</p>
			<p class="text-sm mt-1">{error}</p>
		</div>
	{:else if program}
		<!-- Program Header -->
		<div class="mb-8">
			<div class="flex items-start justify-between">
				<div>
					<h1 class="text-2xl font-bold text-gray-900">{String(program.name ?? 'Unnamed Program')}</h1>
					{#if program.description}
						<p class="mt-1 text-sm text-gray-500">{String(program.description)}</p>
					{/if}
				</div>
				<div class="flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-lg px-4 py-2">
					<svg class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
					</svg>
					<span class="text-sm font-semibold text-blue-700">
						{revisions.length} revision{revisions.length !== 1 ? 's' : ''}
					</span>
				</div>
			</div>
		</div>

		<!-- Trend Charts (only if ≥2 revisions) -->
		{#if trends && trends.revision_count >= 2}
			<div class="mb-8">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">Trend Analysis</h2>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
					<TrendChart
						data={trends.health_scores}
						labels={trends.labels}
						title="Health Score"
						color="#3b82f6"
						height={200}
						formatValue={(v) => v.toFixed(0)}
					/>
					<TrendChart
						data={trends.dcma_scores}
						labels={trends.labels}
						title="DCMA Compliance"
						color="#8b5cf6"
						height={200}
						formatValue={(v) => v.toFixed(1)}
					/>
					<TrendChart
						data={trends.alert_counts}
						labels={trends.labels}
						title="Alert Count"
						color="#ef4444"
						height={200}
						formatValue={(v) => v.toFixed(0)}
					/>
					<TrendChart
						data={trends.activity_counts}
						labels={trends.labels}
						title="Activity Count"
						color="#10b981"
						height={200}
						formatValue={(v) => v.toFixed(0)}
					/>
				</div>
			</div>
		{:else if trends && trends.revision_count === 1}
			<div class="mb-8 bg-blue-50 border border-blue-200 rounded-lg p-5 flex items-center gap-3">
				<svg class="w-5 h-5 text-blue-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
				</svg>
				<p class="text-sm text-blue-700">Upload a second revision to see trends across schedule updates.</p>
			</div>
		{/if}

		<!-- Revisions Table -->
		<div class="bg-white border border-gray-200 rounded-lg overflow-hidden">
			<div class="px-6 py-4 border-b border-gray-100">
				<h2 class="text-lg font-semibold text-gray-900">Revisions</h2>
			</div>
			{#if revisions.length === 0}
				<div class="px-6 py-8 text-center text-gray-400 text-sm">No revisions found.</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-100 bg-gray-50">
								<th class="text-left px-6 py-3 font-medium text-gray-500">#</th>
								<th class="text-left px-6 py-3 font-medium text-gray-500">Data Date</th>
								<th class="text-left px-6 py-3 font-medium text-gray-500">Filename</th>
								<th class="text-left px-6 py-3 font-medium text-gray-500">Activities</th>
								<th class="text-left px-6 py-3 font-medium text-gray-500">Health Score</th>
								<th class="text-left px-6 py-3 font-medium text-gray-500">Uploaded</th>
								<th class="px-6 py-3"></th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-50">
							{#each revisions as rev}
								{@const revObj = rev as Record<string, unknown>}
								{@const healthScore = getRevisionHealthScore(String(revObj.id ?? ''))}
								<tr class="hover:bg-gray-50 transition-colors">
									<td class="px-6 py-4 font-medium text-gray-900">
										Rev {revObj.revision_number ?? '?'}
									</td>
									<td class="px-6 py-4 text-gray-600">
										{formatDate(revObj.data_date as string | null)}
									</td>
									<td class="px-6 py-4 text-gray-600 font-mono text-xs">
										{String(revObj.filename ?? '—')}
									</td>
									<td class="px-6 py-4 text-gray-600">
										{revObj.activity_count ?? '—'}
									</td>
									<td class="px-6 py-4">
										{#if healthScore !== null}
											<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border {healthScoreColor(healthScore)}">
												{healthScore.toFixed(0)}
											</span>
										{:else}
											<span class="text-gray-400 text-xs">—</span>
										{/if}
									</td>
									<td class="px-6 py-4 text-gray-500 text-xs">
										{formatDate(revObj.uploaded_at as string | null)}
									</td>
									<td class="px-6 py-4">
										<a
											href="/projects/{revObj.id}"
											class="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 text-xs font-medium transition-colors"
										>
											Analyze
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
