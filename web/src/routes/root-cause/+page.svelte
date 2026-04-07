<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { supabase } from '$lib/supabase';
	import TimelineChart from '$lib/components/charts/TimelineChart.svelte';

	interface RootCauseStep {
		activity_id: string;
		activity_name: string;
		total_float: number;
		duration: number;
		early_start: string;
		early_finish: string;
		relationship_type: string;
		is_critical: boolean;
	}

	interface RootCauseResult {
		target_activity: string;
		target_name: string;
		root_cause_activity: string;
		root_cause_name: string;
		chain_length: number;
		total_delay_days: number;
		trace: RootCauseStep[];
		methodology: string;
	}

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let activityId: string = $state('');
	let result = $state<RootCauseResult | null>(null);
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
			const params = activityId ? `?activity_id=${activityId}` : '';
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/root-cause${params}`, { headers });
			if (!res.ok) throw new Error(await res.text());
			result = await res.json();
			toastSuccess(`Root cause: ${result!.root_cause_name} (${result!.chain_length} steps)`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	const timelineItems = $derived(
		result ? result.trace.map(s => ({
			label: s.activity_name || s.activity_id,
			start: s.early_start,
			end: s.early_finish,
			color: s.is_critical ? '#ef4444' : '#3b82f6',
		})) : []
	);
</script>

<svelte:head>
	<title>Root Cause Analysis - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900">Root Cause Analysis</h1>
		<p class="text-gray-500 mt-1">Backwards network trace to delay origin via NetworkX</p>
	</div>

	<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
		<div class="flex items-end gap-4">
			<div class="flex-1">
				<label for="project" class="block text-sm font-medium text-gray-700 mb-1">{$t('common.project')}</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<div class="w-48">
				<label for="activity" class="block text-sm font-medium text-gray-700 mb-1">Activity ID (optional)</label>
				<input id="activity" bind:value={activityId} placeholder="Auto-detect" class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" />
			</div>
			<button onclick={analyze} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Tracing...' : 'Trace Root Cause'}
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
		<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-gray-900">{result.chain_length}</p>
				<p class="text-xs text-gray-500 uppercase">Chain Length</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-red-600">{result.total_delay_days}d</p>
				<p class="text-xs text-gray-500 uppercase">Total Delay</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-sm font-bold text-blue-600 truncate" title={result.root_cause_name}>{result.root_cause_name}</p>
				<p class="text-xs text-gray-500 uppercase">Root Cause</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-sm font-bold text-gray-700 truncate" title={result.target_name}>{result.target_name}</p>
				<p class="text-xs text-gray-500 uppercase">Target</p>
			</div>
		</div>

		<!-- Dependency chain -->
		<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
			<h2 class="text-lg font-semibold text-gray-900 mb-4">Dependency Chain</h2>
			<div class="space-y-2">
				{#each result.trace as step, i}
					<div class="flex items-center gap-3">
						<div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold {step.is_critical ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}">
							{i + 1}
						</div>
						<div class="flex-1 bg-gray-50 rounded-lg p-3">
							<div class="flex items-center justify-between">
								<p class="text-sm font-medium text-gray-900">{step.activity_name || step.activity_id}</p>
								<div class="flex items-center gap-2 text-xs text-gray-500">
									<span>TF: {step.total_float}d</span>
									<span>Dur: {step.duration}d</span>
									{#if step.relationship_type}
										<span class="px-1.5 py-0.5 bg-gray-200 rounded">{step.relationship_type}</span>
									{/if}
								</div>
							</div>
							<p class="text-xs text-gray-400 mt-0.5">{step.early_start} — {step.early_finish}</p>
						</div>
						{#if i < result.trace.length - 1}
							<svg class="w-4 h-4 text-gray-300 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
							</svg>
						{/if}
					</div>
				{/each}
			</div>
			<p class="text-xs text-gray-400 mt-4">{result.methodology}</p>
		</div>

		{#if timelineItems.length > 0}
			<div class="bg-white rounded-lg border border-gray-200 p-6">
				<TimelineChart data={timelineItems} title="Trace Timeline" />
			</div>
		{/if}
	{/if}
</main>
