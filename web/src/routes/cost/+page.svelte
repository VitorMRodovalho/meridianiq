<script lang="ts">
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';
	import PieChart from '$lib/components/charts/PieChart.svelte';
	import { supabase } from '$lib/supabase';

	let data: CostData | null = $state(null);
	let loading = $state(false);
	let error = $state('');

	interface CBSElement {
		cbs_code: string;
		cbs_level1: string;
		cbs_level2: string;
		scope: string;
		wbs_code: string;
		estimate: number;
		contingency: number;
		budget: number;
	}

	interface CostData {
		filename: string;
		budget_date: string;
		total_budget: number;
		total_contingency: number;
		total_escalation: number;
		program_total: number;
		cbs_element_count: number;
		wbs_budget_count: number;
		mapping_count: number;
		insights: string[];
		cbs_elements: CBSElement[];
		wbs_budgets: { wbs_code: string; total_budget: number }[];
		cbs_wbs_mappings: { cost_category: string; cbs_code: string; wbs_level1: string; notes: string }[];
	}

	async function handleUpload(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		loading = true;
		error = '';
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = session?.access_token
				? { Authorization: `Bearer ${session.access_token}` }
				: {};
			const formData = new FormData();
			formData.append('file', file);
			const res = await fetch(`${BASE}/api/v1/cost/upload`, { method: 'POST', headers, body: formData });
			if (!res.ok) throw new Error(await res.text());
			data = await res.json();
			toastSuccess(`Parsed ${data!.cbs_element_count} CBS elements`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	const wbsChart = $derived.by(() => {
		if (!data) return [];
		return data.wbs_budgets
			.filter(w => w.total_budget > 1_000_000)
			.sort((a, b) => b.total_budget - a.total_budget)
			.slice(0, 10)
			.map(w => ({ label: w.wbs_code.slice(0, 15), value: Math.round(w.total_budget / 1e6) }));
	});

	const cbsL1Chart = $derived.by(() => {
		if (!data) return [];
		const groups = new Map<string, number>();
		for (const e of data.cbs_elements) {
			if (!e.cbs_level1 || e.cbs_level1 === 'Total') continue;
			groups.set(e.cbs_level1, (groups.get(e.cbs_level1) || 0) + e.estimate);
		}
		return [...groups.entries()]
			.filter(([, v]) => v > 0)
			.sort((a, b) => b[1] - a[1])
			.map(([k, v]) => ({ label: k, value: Math.round(v / 1e6) }));
	});

	function fmt(n: number): string {
		if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
		if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
		return `$${n.toLocaleString()}`;
	}
</script>

<svelte:head>
	<title>Cost Integration | MeridianIQ</title>
</svelte:head>

<main class="max-w-7xl mx-auto px-4 py-8">
	<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-1">Cost-Schedule Integration</h1>
	<p class="text-sm text-gray-500 dark:text-gray-400 mb-6">CBS/WBS correlation — upload program budget Excel to analyze cost breakdown (AACE RP 10S-90)</p>

	<!-- Upload -->
	<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
		<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Upload CBS Excel (.xlsx)</label>
		<input type="file" accept=".xlsx,.xls" onchange={handleUpload} class="block w-full text-sm text-gray-500 dark:text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-blue-50 dark:file:bg-blue-950 file:text-blue-700 dark:file:text-blue-300 hover:file:bg-blue-100" />
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm">{error}</div>
	{:else if data}
		<!-- KPI Cards -->
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-xl font-bold text-gray-900 dark:text-gray-100">{fmt(data.total_budget)}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">Total Estimate</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-xl font-bold text-amber-600">{fmt(data.total_contingency)}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">Contingency</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-xl font-bold text-blue-600">{data.cbs_element_count}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">CBS Elements</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-xl font-bold text-purple-600">{data.mapping_count}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400">CBS-WBS Mappings</p>
			</div>
		</div>

		<!-- Insights -->
		{#if data.insights.length > 0}
			<div class="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6">
				<h3 class="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-2">Cost Insights</h3>
				<ul class="space-y-1">
					{#each data.insights as insight}
						<li class="text-xs text-blue-700 dark:text-blue-400">{insight}</li>
					{/each}
				</ul>
			</div>
		{/if}

		<!-- Charts -->
		<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
			{#if wbsChart.length > 0}
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
					<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Top WBS by Budget ($M)</h3>
					<BarChart data={wbsChart} height={200} />
				</div>
			{/if}
			{#if cbsL1Chart.length > 0}
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
					<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">CBS Level 1 ($M)</h3>
					<BarChart data={cbsL1Chart} height={200} />
				</div>
			{/if}
		</div>

		<!-- CBS-WBS Mapping Table -->
		{#if data.cbs_wbs_mappings.length > 0}
			<details class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg mb-6">
				<summary class="px-4 py-3 cursor-pointer text-sm font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
					CBS → WBS Mappings ({data.cbs_wbs_mappings.length})
				</summary>
				<table class="w-full text-xs">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="text-left py-2 px-3 text-gray-500 dark:text-gray-400">Cost Category</th>
							<th class="text-left py-2 px-3 text-gray-500 dark:text-gray-400">CBS Code</th>
							<th class="text-left py-2 px-3 text-gray-500 dark:text-gray-400">WBS Level 1</th>
						</tr>
					</thead>
					<tbody>
						{#each data.cbs_wbs_mappings as m}
							<tr class="border-t border-gray-100 dark:border-gray-800">
								<td class="py-1.5 px-3 text-gray-900 dark:text-gray-100">{m.cost_category}</td>
								<td class="py-1.5 px-3 font-mono text-blue-600 dark:text-blue-400">{m.cbs_code}</td>
								<td class="py-1.5 px-3 text-gray-600 dark:text-gray-400 truncate max-w-48">{m.wbs_level1}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</details>
		{/if}

		<!-- WBS Budgets Table -->
		<details class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg">
			<summary class="px-4 py-3 cursor-pointer text-sm font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
				WBS Budgets ({data.wbs_budgets.length})
			</summary>
			<table class="w-full text-xs">
				<thead class="bg-gray-50 dark:bg-gray-800">
					<tr>
						<th class="text-left py-2 px-3 text-gray-500 dark:text-gray-400">WBS Code</th>
						<th class="text-right py-2 px-3 text-gray-500 dark:text-gray-400">Budget</th>
					</tr>
				</thead>
				<tbody>
					{#each data.wbs_budgets.sort((a, b) => b.total_budget - a.total_budget) as w}
						<tr class="border-t border-gray-100 dark:border-gray-800">
							<td class="py-1.5 px-3 text-gray-900 dark:text-gray-100 truncate max-w-64">{w.wbs_code}</td>
							<td class="py-1.5 px-3 text-right font-mono text-gray-700 dark:text-gray-300">{fmt(w.total_budget)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</details>
	{:else}
		<div class="text-center py-12 text-gray-400 dark:text-gray-600">
			<p class="text-lg mb-2">Upload a CBS Excel file to analyze cost breakdown</p>
			<p class="text-sm">Supports program budget workbooks with CBS/WBS summary sheets</p>
		</div>
	{/if}
</main>
