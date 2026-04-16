<script lang="ts">
	import ResourceChart from '$lib/components/charts/ResourceChart.svelte';
	import { supabase } from '$lib/supabase';

	interface Props {
		projectId: string;
	}

	interface ResourceProfile {
		rsrc_id: string;
		rsrc_name: string;
		peak_demand: number;
		demand_by_day: number[];
	}

	interface ResourcesResponse {
		project_id: string;
		total_days: number;
		resource_count: number;
		resources: ResourceProfile[];
	}

	let { projectId }: Props = $props();

	let expanded = $state(false);
	let loaded = $state(false);
	let loading = $state(false);
	let error = $state('');
	let resources: ResourceProfile[] = $state([]);
	let totalDays = $state(0);

	async function loadResources() {
		if (loaded || loading || !projectId) return;
		loading = true;
		error = '';
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = {};
			if (session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
			const res = await fetch(
				`${BASE}/api/v1/projects/${projectId}/schedule-view/resources`,
				{ headers }
			);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const payload = (await res.json()) as ResourcesResponse;
			resources = payload.resources || [];
			totalDays = payload.total_days || 0;
			loaded = true;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load resources';
		} finally {
			loading = false;
		}
	}

	function toggle() {
		expanded = !expanded;
		if (expanded) loadResources();
	}

	const hasResources = $derived(resources.length > 0);
</script>

<div class="mt-4 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
	<button
		onclick={toggle}
		class="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
		aria-expanded={expanded}
	>
		<div class="flex items-center gap-2">
			<svg
				class="w-4 h-4 text-gray-500 transition-transform {expanded ? 'rotate-90' : ''}"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
			</svg>
			<span class="text-sm font-semibold text-gray-900 dark:text-gray-100">
				Resource Histograms
			</span>
			{#if loaded}
				<span class="text-xs text-gray-500 dark:text-gray-400">
					({resources.length} resource{resources.length === 1 ? '' : 's'}, {totalDays} days)
				</span>
			{/if}
		</div>
		<span class="text-xs text-gray-500 dark:text-gray-400">
			{expanded ? 'Hide' : 'Show'}
		</span>
	</button>

	{#if expanded}
		<div class="border-t border-gray-200 dark:border-gray-700 p-4">
			{#if loading}
				<div class="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
					Loading resource demand…
				</div>
			{:else if error}
				<div class="py-4 text-sm text-red-600 dark:text-red-400">
					{error}
				</div>
			{:else if !hasResources}
				<div class="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
					No resource assignments found in this schedule.
				</div>
			{:else}
				<p class="text-xs text-gray-500 dark:text-gray-400 mb-3">
					As-scheduled demand curves (no leveling applied). Units distributed
					uniformly across each activity's duration from CPM early dates.
				</p>
				<div class="space-y-4">
					{#each resources as profile}
						<div class="bg-gray-50 dark:bg-gray-800 rounded-md p-3">
							<div class="flex items-center justify-between mb-2">
								<div>
									<p class="text-xs font-semibold text-gray-900 dark:text-gray-100">
										{profile.rsrc_name || profile.rsrc_id}
									</p>
									<p class="text-[10px] text-gray-500 dark:text-gray-400">
										ID: {profile.rsrc_id}
									</p>
								</div>
								<div class="text-right">
									<p class="text-[10px] text-gray-500 dark:text-gray-400">Peak demand</p>
									<p class="text-xs font-semibold text-gray-900 dark:text-gray-100">
										{profile.peak_demand.toFixed(1)}
									</p>
								</div>
							</div>
							<ResourceChart
								demandByDay={profile.demand_by_day}
								maxUnits={profile.peak_demand}
								rsrcName={profile.rsrc_name}
								title=""
								height={180}
							/>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>
