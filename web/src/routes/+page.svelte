<script lang="ts">
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { getProjects, getDashboard, getProjectHealth } from '$lib/api';
	import { isAuthenticated, isLoading as authLoading } from '$lib/auth';
	import type { ProjectListItem, DashboardKPIs } from '$lib/types';

	let projects: ProjectListItem[] = $state([]);
	let dashboard: DashboardKPIs | null = $state(null);
	let healthScores: Record<string, { overall: number; rating: string; trend_arrow: string }> = $state({});
	let loading = $state(true);
	let error = $state('');
	let authenticated = $state(false);

	onMount(async () => {
		const unsub = authLoading.subscribe((val) => {
			if (!val) {
				authenticated = get(isAuthenticated);
				if (authenticated) {
					loadData();
				} else {
					loading = false;
				}
				unsub();
			}
		});
	});

	async function loadData() {
		try {
			const [projRes, dashRes] = await Promise.all([
				getProjects(),
				getDashboard().catch(() => null)
			]);
			projects = projRes.projects;
			dashboard = dashRes;

			// Load health scores for each project
			for (const p of projects) {
				try {
					const health = await getProjectHealth(p.project_id);
					healthScores[p.project_id] = {
						overall: health.overall,
						rating: health.rating,
						trend_arrow: health.trend_arrow
					};
					healthScores = { ...healthScores };
				} catch {
					// Skip projects where health calc fails
				}
			}
		} catch (e: unknown) {
			error = '';
		} finally {
			loading = false;
		}
	}

	function ratingColor(rating: string): string {
		if (rating === 'excellent') return 'text-green-600 bg-green-50 border-green-200';
		if (rating === 'good') return 'text-blue-600 bg-blue-50 border-blue-200';
		if (rating === 'fair') return 'text-yellow-600 bg-yellow-50 border-yellow-200';
		return 'text-red-600 bg-red-50 border-red-200';
	}

	function scoreColor(score: number): string {
		if (score >= 85) return 'text-green-600';
		if (score >= 70) return 'text-blue-600';
		if (score >= 50) return 'text-yellow-600';
		return 'text-red-600';
	}

	function scoreBgColor(score: number): string {
		if (score >= 85) return 'bg-green-500';
		if (score >= 70) return 'bg-blue-500';
		if (score >= 50) return 'bg-yellow-500';
		return 'bg-red-500';
	}

	function scoreCircleBg(score: number): string {
		if (score >= 85) return 'bg-green-100 text-green-700 border-green-300';
		if (score >= 70) return 'bg-blue-100 text-blue-700 border-blue-300';
		if (score >= 50) return 'bg-yellow-100 text-yellow-700 border-yellow-300';
		return 'bg-red-100 text-red-700 border-red-300';
	}

	// Find the most critical project from our loaded scores
	const mostCriticalProject = $derived.by(() => {
		if (!dashboard?.most_critical_project) return null;
		const proj = projects.find(p => p.project_id === dashboard!.most_critical_project);
		return proj ? proj.name || proj.project_id : dashboard!.most_critical_project;
	});
</script>

<svelte:head>
	<title>MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<div class="mb-10">
		<h1 class="text-3xl font-bold text-gray-900">MeridianIQ — Schedule Intelligence Platform</h1>
		<p class="mt-2 text-lg text-gray-600">
			Open-source Primavera P6 schedule validation, comparison, and forensic analysis
		</p>
	</div>

	{#if !authenticated && !loading}
		<div class="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-10">
			<h2 class="text-lg font-semibold text-blue-900 mb-2">Welcome to MeridianIQ</h2>
			<p class="text-sm text-blue-700 mb-4">Sign in to upload and analyze your Primavera P6 schedules. Your data is private and encrypted.</p>
			<a href="/login" class="inline-block bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors">Sign in to get started</a>
		</div>
	{/if}

	<!-- Dashboard KPIs -->
	{#if dashboard && authenticated}
		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
			<div class="bg-white border border-gray-200 rounded-lg p-5">
				<p class="text-sm text-gray-500">Total Projects</p>
				<p class="text-3xl font-bold text-gray-900">{dashboard.total_projects}</p>
				<p class="text-xs text-gray-400 mt-1">Uploaded schedules</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-5">
				<p class="text-sm text-gray-500">Avg Health Score</p>
				<div class="flex items-center gap-3 mt-1">
					<p class="text-3xl font-bold {scoreColor(dashboard.avg_health_score)}">{dashboard.avg_health_score.toFixed(0)}</p>
					<div class="flex-1">
						<div class="h-2 rounded-full bg-gray-100 overflow-hidden">
							<div class="h-full rounded-full {scoreBgColor(dashboard.avg_health_score)}" style="width: {dashboard.avg_health_score}%"></div>
						</div>
					</div>
				</div>
				<p class="text-xs text-gray-400 mt-1">Portfolio average (0-100)</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-5">
				<p class="text-sm text-gray-500">Active Alerts</p>
				<p class="text-3xl font-bold {dashboard.active_alerts > 0 ? 'text-red-600' : 'text-green-600'}">{dashboard.active_alerts}</p>
				<p class="text-xs text-gray-400 mt-1">{dashboard.active_alerts === 0 ? 'No active warnings' : 'Requires attention'}</p>
			</div>
			{#if dashboard.most_critical_project}
				<div class="bg-red-50 border border-red-200 rounded-lg p-5">
					<p class="text-sm text-red-600 font-medium">Most Critical Project</p>
					<p class="text-lg font-bold text-red-700 truncate mt-1">{mostCriticalProject || dashboard.most_critical_project}</p>
					{#if dashboard.most_critical_score !== null && dashboard.most_critical_score !== undefined}
						<div class="flex items-center gap-2 mt-1">
							<div class="h-1.5 flex-1 rounded-full bg-red-100 overflow-hidden">
								<div class="h-full rounded-full bg-red-500" style="width: {dashboard.most_critical_score}%"></div>
							</div>
							<span class="text-sm font-bold text-red-600">{dashboard.most_critical_score.toFixed(0)}</span>
						</div>
					{/if}
				</div>
			{:else}
				<div class="bg-green-50 border border-green-200 rounded-lg p-5">
					<p class="text-sm text-green-600 font-medium">Portfolio Status</p>
					<p class="text-lg font-bold text-green-700 mt-1">All Clear</p>
					<p class="text-xs text-green-500 mt-1">No critical issues detected</p>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Action Cards -->
	<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
		<a
			href="/upload"
			class="block bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md hover:border-blue-300 transition-all"
		>
			<div class="flex items-center gap-4">
				<div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
					<svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
					</svg>
				</div>
				<div>
					<h2 class="text-lg font-semibold text-gray-900">Upload XER File</h2>
					<p class="text-sm text-gray-500">Parse and analyze a Primavera P6 schedule export</p>
				</div>
			</div>
		</a>
		<a
			href="/compare"
			class="block bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md hover:border-blue-300 transition-all"
		>
			<div class="flex items-center gap-4">
				<div class="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
					<svg class="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
					</svg>
				</div>
				<div>
					<h2 class="text-lg font-semibold text-gray-900">Compare Schedules</h2>
					<p class="text-sm text-gray-500">Detect changes and manipulation between schedule versions</p>
				</div>
			</div>
		</a>
	</div>

	<!-- Project Summary with Health Scores -->
	{#if loading}
		<div class="flex items-center gap-2 text-gray-500">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			Loading projects...
		</div>
	{:else if error}
		<div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800">
			Could not connect to backend: {error}
		</div>
	{:else if projects.length > 0}
		<div class="bg-white rounded-lg border border-gray-200 p-6">
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-lg font-semibold text-gray-900">Uploaded Projects</h2>
				<span class="text-sm text-gray-400">{projects.length} project{projects.length !== 1 ? 's' : ''}</span>
			</div>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
				{#each projects as project}
					<a
						href="/projects/{project.project_id}"
						class="block border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-md transition-all group"
					>
						<div class="flex items-start justify-between">
							<h3 class="font-medium text-gray-900 truncate flex-1 group-hover:text-blue-700 transition-colors">{project.name || project.project_id}</h3>
							{#if healthScores[project.project_id]}
								{@const hs = healthScores[project.project_id]}
								<div class="ml-2 w-10 h-10 rounded-full border-2 flex items-center justify-center text-sm font-bold {scoreCircleBg(hs.overall)}">
									{hs.overall.toFixed(0)}
								</div>
							{/if}
						</div>
						{#if healthScores[project.project_id]}
							{@const hs = healthScores[project.project_id]}
							<div class="mt-2 flex items-center gap-2">
								<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border {ratingColor(hs.rating)}">
									{hs.rating} {hs.trend_arrow}
								</span>
							</div>
						{/if}
						<div class="mt-3 flex gap-4 text-xs text-gray-500">
							<span class="flex items-center gap-1">
								<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
								{project.activity_count} activities
							</span>
							<span class="flex items-center gap-1">
								<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
								{project.relationship_count} rels
							</span>
						</div>
						{#if healthScores[project.project_id]}
							<div class="mt-3">
								<div class="h-1.5 rounded-full bg-gray-100 overflow-hidden">
									<div
										class="h-full rounded-full transition-all {scoreBgColor(healthScores[project.project_id].overall)}"
										style="width: {healthScores[project.project_id].overall}%"
									></div>
								</div>
							</div>
						{/if}
					</a>
				{/each}
			</div>
		</div>
	{:else}
		<div class="bg-white rounded-lg border border-gray-200 p-6 text-center text-gray-500">
			<p>No projects uploaded yet. Start by uploading an XER file.</p>
		</div>
	{/if}
</div>
