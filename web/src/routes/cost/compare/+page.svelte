<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getProjects,
		getCostSnapshots,
		compareCostSnapshots,
		type CostSnapshotSummary,
		type CostCompareResult
	} from '$lib/api';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';
	import { error as toastError } from '$lib/toast';

	interface ProjectOption {
		project_id: string;
		name: string;
	}

	let projects = $state<ProjectOption[]>([]);
	let selectedProject = $state<string>('');
	let snapshots = $state<CostSnapshotSummary[]>([]);
	let snapshotA = $state<string>('');
	let snapshotB = $state<string>('');
	let result = $state<CostCompareResult | null>(null);
	let loading = $state(false);
	let compareLoading = $state(false);
	let loadError = $state('');

	onMount(async () => {
		try {
			const resp = await getProjects();
			projects = resp.projects.map((p) => ({
				project_id: p.project_id,
				name: p.name || p.project_id
			}));
		} catch (e) {
			loadError = e instanceof Error ? e.message : 'Failed to load projects';
		}
	});

	async function loadSnapshots(projectId: string) {
		if (!projectId) {
			snapshots = [];
			return;
		}
		loading = true;
		try {
			const resp = await getCostSnapshots(projectId);
			snapshots = resp.snapshots;
			// Seed default picks from comparable snapshots only (skip empties
			// which otherwise 404 when rehydrated on the backend).
			const pickable = snapshots.filter((s) => s.cbs_element_count > 0);
			snapshotA = pickable.length >= 2 ? pickable[1].snapshot_id : '';
			snapshotB = pickable.length >= 1 ? pickable[0].snapshot_id : '';
			result = null;
		} catch (e) {
			toastError(e instanceof Error ? e.message : 'Failed to load snapshots');
			snapshots = [];
		} finally {
			loading = false;
		}
	}

	// Only snapshots with at least one CBS element can be compared — empty
	// snapshots rehydrate to no rows and the backend returns 404.
	const comparableSnapshots = $derived(
		snapshots.filter((s) => s.cbs_element_count > 0)
	);
	const filteredOutCount = $derived(
		snapshots.length - comparableSnapshots.length
	);

	async function runCompare() {
		if (!selectedProject || !snapshotA || !snapshotB || snapshotA === snapshotB) return;
		compareLoading = true;
		try {
			result = await compareCostSnapshots(selectedProject, snapshotA, snapshotB);
		} catch (e) {
			toastError(e instanceof Error ? e.message : 'Compare failed');
			result = null;
		} finally {
			compareLoading = false;
		}
	}

	$effect(() => {
		loadSnapshots(selectedProject);
	});

	function fmt(n: number): string {
		const sign = n < 0 ? '-' : '';
		const a = Math.abs(n);
		if (a >= 1e9) return `${sign}$${(a / 1e9).toFixed(2)}B`;
		if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(1)}M`;
		if (a >= 1e3) return `${sign}$${(a / 1e3).toFixed(0)}K`;
		return `${sign}$${a.toFixed(0)}`;
	}

	function signed(n: number): string {
		return (n >= 0 ? '+' : '') + fmt(n);
	}

	const l1VarianceChart = $derived.by(() => {
		if (!result) return [];
		const groups = new Map<string, number>();
		for (const d of result.element_deltas) {
			if (!d.cbs_level1) continue;
			groups.set(d.cbs_level1, (groups.get(d.cbs_level1) || 0) + d.budget_delta);
		}
		return [...groups.entries()]
			.filter(([, v]) => Math.abs(v) > 0)
			.sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
			.slice(0, 10)
			.map(([k, v]) => ({ label: k.slice(0, 18), value: Math.round(v / 1e6) }));
	});

	const topMovers = $derived.by(() => {
		if (!result) return [];
		return [...result.element_deltas]
			.filter((d) => d.status !== 'unchanged')
			.sort((a, b) => Math.abs(b.budget_delta) - Math.abs(a.budget_delta))
			.slice(0, 20);
	});

	function statusBadge(status: string): string {
		if (status === 'added') return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300';
		if (status === 'removed') return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300';
		if (status === 'changed') return 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300';
		return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400';
	}

	function deltaColor(delta: number): string {
		if (delta > 0) return 'text-red-600 dark:text-red-400';
		if (delta < 0) return 'text-green-600 dark:text-green-400';
		return 'text-gray-500';
	}
</script>

<svelte:head>
	<title>CBS Snapshot Compare | MeridianIQ</title>
</svelte:head>

<main class="max-w-7xl mx-auto px-4 py-8">
	<div class="mb-6">
		<a
			href="/cost"
			class="text-xs text-blue-600 dark:text-blue-400 hover:underline"
		>← Back to Cost Integration</a>
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1 mb-1">
			CBS Snapshot Comparison
		</h1>
		<p class="text-sm text-gray-500 dark:text-gray-400">
			Element-level variance between two persisted CBS uploads for a project
			(AACE RP 29R-03 §5.3).
		</p>
	</div>

	{#if loadError}
		<div
			class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm mb-4"
		>
			{loadError}
		</div>
	{/if}

	<div
		class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6"
	>
		<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
			<label class="block">
				<span class="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Project</span>
				<select
					bind:value={selectedProject}
					class="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-3 py-2"
				>
					<option value="">Select a project…</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name}</option>
					{/each}
				</select>
			</label>

			<label class="block">
				<span class="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">
					Snapshot A (earlier)
				</span>
				<select
					bind:value={snapshotA}
					disabled={comparableSnapshots.length < 2}
					class="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-3 py-2 disabled:opacity-50"
				>
					<option value="">—</option>
					{#each comparableSnapshots as s}
						<option value={s.snapshot_id}>
							{s.snapshot_id} — {s.source_name} ({fmt(s.total_budget)})
						</option>
					{/each}
				</select>
			</label>

			<label class="block">
				<span class="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">
					Snapshot B (later)
				</span>
				<select
					bind:value={snapshotB}
					disabled={comparableSnapshots.length < 2}
					class="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-sm px-3 py-2 disabled:opacity-50"
				>
					<option value="">—</option>
					{#each comparableSnapshots as s}
						<option value={s.snapshot_id}>
							{s.snapshot_id} — {s.source_name} ({fmt(s.total_budget)})
						</option>
					{/each}
				</select>
			</label>
		</div>

		{#if selectedProject && comparableSnapshots.length < 2}
			<p class="text-xs text-amber-700 dark:text-amber-400 mt-3">
				Need at least two snapshots with parsed CBS elements on this project to compare (currently {comparableSnapshots.length}). Upload more CBS files via <a href="/cost" class="underline">/cost</a> with <code>?project_id={selectedProject}</code>.
			</p>
		{/if}
		{#if filteredOutCount > 0}
			<p class="text-xs text-gray-500 dark:text-gray-500 mt-2">
				{filteredOutCount} snapshot{filteredOutCount === 1 ? '' : 's'} hidden (no parsed CBS elements — would 404 on compare).
			</p>
		{/if}

		<button
			type="button"
			onclick={runCompare}
			disabled={!selectedProject ||
				!snapshotA ||
				!snapshotB ||
				snapshotA === snapshotB ||
				compareLoading}
			class="mt-4 inline-flex items-center px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
		>
			{compareLoading ? 'Comparing…' : 'Compare snapshots'}
		</button>
	</div>

	{#if loading || compareLoading}
		<AnalysisSkeleton />
	{:else if result}
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
			<div
				class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center"
			>
				<p class="text-lg font-bold {deltaColor(result.total_budget_delta)}">
					{signed(result.total_budget_delta)}
				</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">
					Budget Δ ({result.budget_variance_pct >= 0 ? '+' : ''}{result.budget_variance_pct.toFixed(1)}%)
				</p>
			</div>
			<div
				class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center"
			>
				<p class="text-lg font-bold {deltaColor(result.total_contingency_delta)}">
					{signed(result.total_contingency_delta)}
				</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">Contingency Δ</p>
			</div>
			<div
				class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center"
			>
				<p class="text-lg font-bold text-gray-900 dark:text-gray-100">
					{result.changed_count}
				</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">
					Changed · +{result.added_count} / −{result.removed_count}
				</p>
			</div>
			<div
				class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center"
			>
				<p class="text-lg font-bold text-gray-500 dark:text-gray-400">
					{result.unchanged_count}
				</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">Unchanged</p>
			</div>
		</div>

		{#if result.insights.length > 0}
			<div
				class="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6"
			>
				<h3 class="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-2">
					Variance Insights
				</h3>
				<ul class="space-y-1">
					{#each result.insights as i}
						<li class="text-xs text-blue-700 dark:text-blue-400">{i}</li>
					{/each}
				</ul>
			</div>
		{/if}

		{#if l1VarianceChart.length > 0}
			<div
				class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 mb-6"
			>
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
					Budget Δ by CBS Level 1 ($M) — B minus A
				</h3>
				<BarChart data={l1VarianceChart} height={220} />
			</div>
		{/if}

		{#if topMovers.length > 0}
			<div
				class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-x-auto"
			>
				<div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
					<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">
						Top {topMovers.length} Movers by Absolute Budget Delta
					</h3>
				</div>
				<table class="w-full text-xs">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="text-left py-2 px-3 text-gray-500 dark:text-gray-400">CBS</th>
							<th class="text-left py-2 px-3 text-gray-500 dark:text-gray-400">Level 1</th>
							<th class="text-left py-2 px-3 text-gray-500 dark:text-gray-400">Status</th>
							<th class="text-right py-2 px-3 text-gray-500 dark:text-gray-400">Budget A</th>
							<th class="text-right py-2 px-3 text-gray-500 dark:text-gray-400">Budget B</th>
							<th class="text-right py-2 px-3 text-gray-500 dark:text-gray-400">Δ</th>
							<th class="text-right py-2 px-3 text-gray-500 dark:text-gray-400">Δ %</th>
						</tr>
					</thead>
					<tbody>
						{#each topMovers as d}
							<tr class="border-t border-gray-100 dark:border-gray-800">
								<td class="py-1.5 px-3 font-mono text-blue-600 dark:text-blue-400">
									{d.cbs_code}
								</td>
								<td
									class="py-1.5 px-3 text-gray-600 dark:text-gray-400 truncate max-w-40"
								>
									{d.cbs_level1}
								</td>
								<td class="py-1.5 px-3">
									<span
										class="inline-block rounded px-2 py-0.5 text-[10px] font-medium uppercase {statusBadge(
											d.status
										)}"
									>
										{d.status}
									</span>
								</td>
								<td class="py-1.5 px-3 text-right text-gray-700 dark:text-gray-300">
									{fmt(d.budget_a)}
								</td>
								<td class="py-1.5 px-3 text-right text-gray-700 dark:text-gray-300">
									{fmt(d.budget_b)}
								</td>
								<td
									class="py-1.5 px-3 text-right font-medium {deltaColor(d.budget_delta)}"
								>
									{signed(d.budget_delta)}
								</td>
								<td
									class="py-1.5 px-3 text-right {deltaColor(d.budget_delta)}"
								>
									{d.variance_pct >= 0 ? '+' : ''}{d.variance_pct.toFixed(1)}%
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{:else if selectedProject && snapshotA && snapshotB}
		<p class="text-sm text-gray-500 dark:text-gray-400">
			Pick two snapshots and press "Compare snapshots" to see variance.
		</p>
	{/if}
</main>
