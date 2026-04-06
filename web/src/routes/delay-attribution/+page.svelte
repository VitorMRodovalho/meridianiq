<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { supabase } from '$lib/supabase';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import PieChart from '$lib/components/charts/PieChart.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';
	import WaterfallChart from '$lib/components/charts/WaterfallChart.svelte';

	interface PartyDelay {
		party: string;
		delay_days: number;
		pct_of_total: number;
		activity_count: number;
		top_activities: string[];
	}

	interface AttributionResult {
		parties: PartyDelay[];
		total_delay_days: number;
		excusable_days: number;
		non_excusable_days: number;
		concurrent_days: number;
		data_source: string;
		methodology: string;
	}

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let baselineProject: string = $state('');
	let result = $state<AttributionResult | null>(null);
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
		result = null;
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = session?.access_token
				? { Authorization: `Bearer ${session.access_token}` }
				: {};
			const params = baselineProject ? `?baseline_id=${baselineProject}` : '';
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/delay-attribution${params}`, { headers });
			if (!res.ok) throw new Error(await res.text());
			result = await res.json();
			toastSuccess(`Total delay: ${result!.total_delay_days}d (${result!.data_source})`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	const partyColor: Record<string, string> = {
		'Owner': '#3b82f6',
		'Contractor': '#ef4444',
		'Shared': '#f59e0b',
		'Third Party': '#8b5cf6',
		'Force Majeure': '#6b7280',
		'None': '#10b981',
	};

	const pieData = $derived(
		result ? result.parties.map(p => ({
			label: p.party,
			value: p.delay_days,
			color: partyColor[p.party] || '#94a3b8',
		})) : []
	);

	const barData = $derived(
		result ? result.parties.map(p => ({
			label: p.party,
			value: p.delay_days,
			color: partyColor[p.party] || '#94a3b8',
		})) : []
	);

	const waterfallData = $derived(
		result ? [
			...result.parties.map(p => ({
				label: p.party,
				value: p.delay_days,
			})),
			{ label: 'Total', value: result.total_delay_days },
		] : []
	);
</script>

<svelte:head>
	<title>Delay Attribution - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900">Delay Attribution Summary</h1>
		<p class="text-gray-500 mt-1">Aggregate delay by responsible party (AACE RP 29R-03, SCL Protocol)</p>
	</div>

	<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
		<div class="flex items-end gap-4 flex-wrap">
			<div class="flex-1 min-w-48">
				<label for="project" class="block text-sm font-medium text-gray-700 mb-1">{$t('common.project')} (Update)</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<div class="flex-1 min-w-48">
				<label for="baseline" class="block text-sm font-medium text-gray-700 mb-1">Baseline (optional)</label>
				<select id="baseline" bind:value={baselineProject} class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
					<option value="">None — use heuristics</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<button onclick={analyze} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Analyzing...' : 'Compute Attribution'}
			</button>
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton cards={5} />
	{:else if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
			<p class="text-red-700 text-sm">{error}</p>
		</div>
	{/if}

	{#if result}
		<!-- Summary Cards -->
		<div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-gray-900">{result.total_delay_days}d</p>
				<p class="text-xs text-gray-500 uppercase">Total Delay</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-blue-600">{result.excusable_days}d</p>
				<p class="text-xs text-gray-500 uppercase">Excusable</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-red-600">{result.non_excusable_days}d</p>
				<p class="text-xs text-gray-500 uppercase">Non-Excusable</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-amber-600">{result.concurrent_days}d</p>
				<p class="text-xs text-gray-500 uppercase">Concurrent</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-gray-600 capitalize">{result.data_source}</p>
				<p class="text-xs text-gray-500 uppercase">Data Source</p>
			</div>
		</div>

		<!-- Excusable vs Non-excusable bar -->
		{#if result.total_delay_days > 0}
			<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
				<p class="text-sm font-semibold text-gray-700 mb-3">Excusable vs Non-Excusable</p>
				<div class="h-8 rounded-lg overflow-hidden flex">
					{#if result.excusable_days > 0}
						<div
							class="bg-blue-500 flex items-center justify-center text-xs text-white font-bold"
							style="width: {(result.excusable_days / result.total_delay_days) * 100}%"
						>
							{result.excusable_days}d
						</div>
					{/if}
					{#if result.non_excusable_days > 0}
						<div
							class="bg-red-500 flex items-center justify-center text-xs text-white font-bold"
							style="width: {(result.non_excusable_days / result.total_delay_days) * 100}%"
						>
							{result.non_excusable_days}d
						</div>
					{/if}
					{#if result.concurrent_days > 0}
						<div
							class="bg-amber-500 flex items-center justify-center text-xs text-white font-bold"
							style="width: {(result.concurrent_days / result.total_delay_days) * 100}%"
						>
							{result.concurrent_days}d
						</div>
					{/if}
				</div>
				<div class="flex items-center gap-4 mt-2 text-xs text-gray-500">
					<div class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-blue-500"></span> Excusable</div>
					<div class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-red-500"></span> Non-Excusable</div>
					<div class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-amber-500"></span> Concurrent</div>
				</div>
			</div>
		{/if}

		<!-- Charts -->
		<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
			{#if pieData.length > 0}
				<PieChart data={pieData} title="Delay by Party" size={180} />
			{/if}
			{#if barData.length > 0}
				<BarChart data={barData} title="Delay Days by Party" />
			{/if}
		</div>

		<!-- Party Detail Cards -->
		{#if result.parties.length > 0}
			<div class="space-y-4">
				{#each result.parties as party}
					<div class="bg-white rounded-lg border border-gray-200 p-5">
						<div class="flex items-center justify-between mb-3">
							<div class="flex items-center gap-3">
								<span class="w-4 h-4 rounded-full" style="background-color: {partyColor[party.party] || '#94a3b8'}"></span>
								<h3 class="text-lg font-semibold text-gray-900">{party.party}</h3>
							</div>
							<div class="flex items-center gap-4">
								<span class="text-2xl font-bold text-gray-900">{party.delay_days}d</span>
								<span class="px-2 py-1 rounded-full text-xs font-bold bg-gray-100 text-gray-700">{party.pct_of_total}%</span>
							</div>
						</div>
						{#if party.activity_count > 0}
							<p class="text-sm text-gray-500 mb-2">{party.activity_count} driving activities</p>
						{/if}
						{#if party.top_activities.length > 0}
							<div class="flex flex-wrap gap-1">
								{#each party.top_activities as act}
									<span class="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600">{act}</span>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{:else}
			<div class="bg-green-50 border border-green-200 rounded-lg p-4">
				<p class="text-green-700 text-sm font-medium">No delay detected. Schedule is on track.</p>
			</div>
		{/if}

		<p class="text-xs text-gray-400 mt-6">{result.methodology}</p>
	{/if}
</main>
