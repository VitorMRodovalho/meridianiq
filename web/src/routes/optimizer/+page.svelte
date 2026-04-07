<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { supabase } from '$lib/supabase';
	import BarChart from '$lib/components/charts/BarChart.svelte';

	interface ConvergencePoint {
		generation: number;
		best_fitness: number;
		mean_fitness: number;
	}

	interface OptimizeResult {
		original_makespan: number;
		optimized_makespan: number;
		improvement_pct: number;
		generations: number;
		convergence: ConvergencePoint[];
		best_priority_rule: string;
		shifted_activities: { activity_id: string; activity_name: string; shift_days: number }[];
		methodology: string;
	}

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let generations: number = $state(50);
	let populationSize: number = $state(20);
	let result = $state<OptimizeResult | null>(null);
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

	async function optimize() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		result = null;
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = {
				'Content-Type': 'application/json',
				...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
			};
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/optimize`, {
				method: 'POST',
				headers,
				body: JSON.stringify({ generations, population_size: populationSize }),
			});
			if (!res.ok) throw new Error(await res.text());
			result = await res.json();
			toastSuccess(`Optimized: ${result!.improvement_pct.toFixed(1)}% improvement`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	// Convergence curve SVG
	const W = 700;
	const H = 250;
	const PAD = { top: 25, right: 25, bottom: 35, left: 65 };

	const chartW = $derived(W - PAD.left - PAD.right);
	const chartH = $derived(H - PAD.top - PAD.bottom);

	const maxGen = $derived(result ? Math.max(...result.convergence.map(c => c.generation), 1) : 1);
	const maxFit = $derived(result ? Math.max(...result.convergence.map(c => Math.max(c.best_fitness, c.mean_fitness)), 1) * 1.05 : 1);

	function cx(g: number): number { return PAD.left + (g / maxGen) * chartW; }
	function cy(f: number): number { return PAD.top + chartH - (f / maxFit) * chartH; }

	const bestPath = $derived(
		result ? result.convergence.map((c, i) => `${i === 0 ? 'M' : 'L'}${cx(c.generation)},${cy(c.best_fitness)}`).join(' ') : ''
	);
	const meanPath = $derived(
		result ? result.convergence.map((c, i) => `${i === 0 ? 'M' : 'L'}${cx(c.generation)},${cy(c.mean_fitness)}`).join(' ') : ''
	);

	const shiftItems = $derived(
		result ? result.shifted_activities.slice(0, 15).map(a => ({
			label: a.activity_name || a.activity_id,
			value: a.shift_days,
		})) : []
	);
</script>

<svelte:head>
	<title>Schedule Optimizer - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900">Schedule Optimizer</h1>
		<p class="text-gray-500 mt-1">Evolution Strategies for RCPSP optimization (Loncar 2023, Beyer & Schwefel 2002)</p>
	</div>

	<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
		<div class="flex items-end gap-4 flex-wrap">
			<div class="flex-1 min-w-48">
				<label for="project" class="block text-sm font-medium text-gray-700 mb-1">{$t('common.project')}</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<div class="w-32">
				<label for="gens" class="block text-sm font-medium text-gray-700 mb-1">Generations</label>
				<input id="gens" type="number" min="10" max="500" bind:value={generations} class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" />
			</div>
			<div class="w-32">
				<label for="pop" class="block text-sm font-medium text-gray-700 mb-1">Population</label>
				<input id="pop" type="number" min="10" max="200" bind:value={populationSize} class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" />
			</div>
			<button onclick={optimize} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Optimizing...' : 'Optimize'}
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
		<div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-gray-900">{result.original_makespan}d</p>
				<p class="text-xs text-gray-500 uppercase">Original</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-green-600">{result.optimized_makespan}d</p>
				<p class="text-xs text-gray-500 uppercase">Optimized</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-blue-600">{result.improvement_pct.toFixed(1)}%</p>
				<p class="text-xs text-gray-500 uppercase">Improvement</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-gray-700">{result.generations}</p>
				<p class="text-xs text-gray-500 uppercase">Generations</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-sm font-bold text-gray-700 capitalize">{result.best_priority_rule}</p>
				<p class="text-xs text-gray-500 uppercase">Best Rule</p>
			</div>
		</div>

		<!-- Convergence chart -->
		{#if result.convergence.length > 1}
			<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
				<p class="text-sm font-semibold text-gray-700 mb-3">Convergence Curve</p>
				<svg viewBox="0 0 {W} {H}" class="w-full">
					{#each [0, 0.25, 0.5, 0.75, 1] as pct}
						<line x1={PAD.left} y1={PAD.top + pct * chartH} x2={W - PAD.right} y2={PAD.top + pct * chartH} stroke="#f3f4f6" stroke-width="1" />
						<text x={PAD.left - 5} y={PAD.top + pct * chartH + 3} text-anchor="end" class="text-[8px] fill-gray-400">
							{Math.round(maxFit * (1 - pct))}
						</text>
					{/each}
					{#each [0, 0.25, 0.5, 0.75, 1] as pct}
						<text x={PAD.left + pct * chartW} y={H - PAD.bottom + 15} text-anchor="middle" class="text-[8px] fill-gray-400">
							G{Math.round(pct * maxGen)}
						</text>
					{/each}

					{#if bestPath}<path d={bestPath} fill="none" stroke="#10b981" stroke-width="2.5" />{/if}
					{#if meanPath}<path d={meanPath} fill="none" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4" />{/if}

					<line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={PAD.top + chartH} stroke="#d1d5db" stroke-width="1" />
					<line x1={PAD.left} y1={PAD.top + chartH} x2={W - PAD.right} y2={PAD.top + chartH} stroke="#d1d5db" stroke-width="1" />
					<text x={W / 2} y={H - 5} text-anchor="middle" class="text-[9px] fill-gray-400">Generation</text>
				</svg>
				<div class="flex items-center gap-4 mt-2 text-xs text-gray-500">
					<div class="flex items-center gap-1"><span class="w-4 h-0.5 bg-green-500 rounded"></span> Best Fitness</div>
					<div class="flex items-center gap-1"><span class="w-4 h-0.5 bg-amber-500 rounded border-dashed"></span> Mean Fitness</div>
				</div>
			</div>
		{/if}

		<!-- Shifted activities -->
		{#if result.shifted_activities.length > 0}
			<div class="grid grid-cols-1 md:grid-cols-2 gap-6">
				<BarChart data={shiftItems} title="Activity Shifts (days)" />
				<div class="bg-white rounded-lg border border-gray-200 p-6">
					<h2 class="text-sm font-semibold text-gray-700 mb-3">Shifted Activities ({result.shifted_activities.length})</h2>
					<div class="overflow-y-auto max-h-64 space-y-1">
						{#each result.shifted_activities as a}
							<div class="flex items-center justify-between py-1.5 border-b border-gray-100">
								<span class="text-xs text-gray-600 truncate">{a.activity_name || a.activity_id}</span>
								<span class="text-xs font-mono font-bold {a.shift_days > 0 ? 'text-amber-600' : 'text-green-600'}">
									{a.shift_days > 0 ? '+' : ''}{a.shift_days}d
								</span>
							</div>
						{/each}
					</div>
				</div>
			</div>
		{/if}

		<p class="text-xs text-gray-400 mt-4">{result.methodology}</p>
	{/if}
</main>
