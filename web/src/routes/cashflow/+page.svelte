<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { supabase } from '$lib/supabase';

	interface CashFlowPoint {
		day: number;
		planned_cumulative: number;
		actual_cumulative: number;
	}

	interface CashFlowResult {
		total_planned_cost: number;
		total_actual_cost: number;
		total_remaining_cost: number;
		budget_variance: number;
		cost_performance_index: number;
		curve: CashFlowPoint[];
		peak_spend_day: number;
		peak_spend_amount: number;
		methodology: string;
	}

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let result = $state<CashFlowResult | null>(null);
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

	async function loadCashflow() {
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
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/cashflow`, { headers });
			if (!res.ok) throw new Error(await res.text());
			result = await res.json();
			toastSuccess(`Cash flow: $${(result!.total_planned_cost / 1000).toFixed(0)}K planned`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	// S-Curve SVG
	const W = 700;
	const H = 300;
	const PAD = { top: 30, right: 30, bottom: 35, left: 70 };

	function formatCost(v: number): string {
		if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
		if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
		return `$${v.toFixed(0)}`;
	}

	const chartW = $derived(W - PAD.left - PAD.right);
	const chartH = $derived(H - PAD.top - PAD.bottom);

	const maxCost = $derived(
		result ? Math.max(...result.curve.map(p => Math.max(p.planned_cumulative, p.actual_cumulative)), 1) * 1.05 : 1
	);
	const maxDay = $derived(result ? result.curve.length : 1);

	function x(d: number): number { return PAD.left + (d / maxDay) * chartW; }
	function y(c: number): number { return PAD.top + chartH - (c / maxCost) * chartH; }

	const plannedPath = $derived(
		result ? result.curve.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.day)},${y(p.planned_cumulative)}`).join(' ') : ''
	);
	const actualPath = $derived(
		result && result.total_actual_cost > 0
			? result.curve.filter(p => p.actual_cumulative > 0).map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.day)},${y(p.actual_cumulative)}`).join(' ')
			: ''
	);
</script>

<svelte:head>
	<title>Cash Flow Analysis - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900">Cash Flow Analysis</h1>
		<p class="text-gray-500 mt-1">Cost distribution S-Curve (AACE RP 10S-90)</p>
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
			<button onclick={loadCashflow} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Loading...' : 'Analyze'}
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
		<div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-gray-900">{formatCost(result.total_planned_cost)}</p>
				<p class="text-xs text-gray-500 uppercase">Planned</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-blue-600">{formatCost(result.total_actual_cost)}</p>
				<p class="text-xs text-gray-500 uppercase">Actual</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-amber-600">{formatCost(result.total_remaining_cost)}</p>
				<p class="text-xs text-gray-500 uppercase">Remaining</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold {result.budget_variance >= 0 ? 'text-green-600' : 'text-red-600'}">{formatCost(Math.abs(result.budget_variance))}</p>
				<p class="text-xs text-gray-500 uppercase">{result.budget_variance >= 0 ? 'Under' : 'Over'} Budget</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold {result.cost_performance_index >= 1 ? 'text-green-600' : 'text-red-600'}">{result.cost_performance_index.toFixed(2)}</p>
				<p class="text-xs text-gray-500 uppercase">CPI</p>
			</div>
		</div>

		<!-- S-Curve -->
		<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
			<p class="text-sm font-semibold text-gray-700 mb-3">Cumulative Cost S-Curve</p>
			<svg viewBox="0 0 {W} {H}" class="w-full">
				<!-- Grid -->
				{#each [0, 0.25, 0.5, 0.75, 1] as pct}
					<line x1={PAD.left} y1={PAD.top + pct * chartH} x2={W - PAD.right} y2={PAD.top + pct * chartH} stroke="#f3f4f6" stroke-width="1" />
					<text x={PAD.left - 5} y={PAD.top + pct * chartH + 3} text-anchor="end" class="text-[8px] fill-gray-400">
						{formatCost(maxCost * (1 - pct))}
					</text>
				{/each}
				{#each [0, 0.25, 0.5, 0.75, 1] as pct}
					<text x={PAD.left + pct * chartW} y={H - PAD.bottom + 15} text-anchor="middle" class="text-[8px] fill-gray-400">
						D{Math.round(pct * maxDay)}
					</text>
				{/each}

				<!-- Planned curve -->
				{#if plannedPath}
					<path d={plannedPath} fill="none" stroke="#3b82f6" stroke-width="2.5" />
				{/if}

				<!-- Actual curve -->
				{#if actualPath}
					<path d={actualPath} fill="none" stroke="#10b981" stroke-width="2.5" />
				{/if}

				<!-- Axes -->
				<line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={PAD.top + chartH} stroke="#d1d5db" stroke-width="1" />
				<line x1={PAD.left} y1={PAD.top + chartH} x2={W - PAD.right} y2={PAD.top + chartH} stroke="#d1d5db" stroke-width="1" />

				<!-- Labels -->
				<text x={W / 2} y={H - 5} text-anchor="middle" class="text-[9px] fill-gray-400">Project Duration (days)</text>
			</svg>

			<div class="flex items-center gap-4 mt-2 text-xs text-gray-500">
				<div class="flex items-center gap-1"><span class="w-4 h-0.5 bg-blue-500 rounded"></span> Planned (BCWS)</div>
				<div class="flex items-center gap-1"><span class="w-4 h-0.5 bg-green-500 rounded"></span> Actual (ACWP)</div>
				<div class="ml-auto text-gray-400">{result.methodology}</div>
			</div>
		</div>
	{/if}
</main>
