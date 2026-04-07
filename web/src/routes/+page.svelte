<script lang="ts">
	import { onMount } from 'svelte';
	import { getProjects, getDashboard, getProjectHealth, getPrograms } from '$lib/api';
	import { supabase } from '$lib/supabase';
	import type { ProjectListItem, DashboardKPIs, ProgramListItem } from '$lib/types';
	import { t } from '$lib/i18n';
	import PieChart from '$lib/components/charts/PieChart.svelte';
	import GaugeChart from '$lib/components/charts/GaugeChart.svelte';

	let projects: ProjectListItem[] = $state([]);
	let programs: ProgramListItem[] = $state([]);
	let dashboard: DashboardKPIs | null = $state(null);
	let healthScores: Record<string, { overall: number; rating: string; trend_arrow: string }> = $state({});
	let loading = $state(true);
	let error = $state('');
	let authenticated = $state(false);

	onMount(async () => {
		try {
			const { data: { session } } = await supabase.auth.getSession();
			authenticated = !!session;
			if (authenticated) {
				await loadData();
			} else {
				loading = false;
			}
		} catch {
			authenticated = false;
			loading = false;
		}
	});

	async function loadData() {
		try {
			const [projRes, dashRes, progRes] = await Promise.all([
				getProjects(),
				getDashboard().catch(() => null),
				getPrograms().catch(() => ({ programs: [] }))
			]);
			projects = projRes.projects;
			dashboard = dashRes;
			programs = progRes.programs;

			for (const p of projects) {
				if (!p.activity_count) continue;
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
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to connect to backend';
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

	const mostCriticalProject = $derived.by(() => {
		if (!dashboard?.most_critical_project) return null;
		const proj = projects.find(p => p.project_id === dashboard!.most_critical_project);
		return proj ? proj.name || proj.project_id : dashboard!.most_critical_project;
	});

	// Health distribution for portfolio chart
	const healthDistribution = $derived.by(() => {
		const scores = Object.values(healthScores);
		if (scores.length === 0) return [];
		let excellent = 0, good = 0, fair = 0, poor = 0;
		for (const hs of scores) {
			if (hs.overall >= 85) excellent++;
			else if (hs.overall >= 70) good++;
			else if (hs.overall >= 50) fair++;
			else poor++;
		}
		return [
			{ label: 'Excellent', value: excellent, color: '#10b981' },
			{ label: 'Good', value: good, color: '#3b82f6' },
			{ label: 'Fair', value: fair, color: '#f59e0b' },
			{ label: 'Poor', value: poor, color: '#ef4444' },
		].filter((d) => d.value > 0);
	});

	const capabilities = [
		{ title: 'DCMA 14-Point', desc: 'Automated schedule assessment per DCMA EVMS guidelines', tag: 'Validation', color: 'bg-blue-500' },
		{ title: 'Critical Path', desc: 'NetworkX CPM engine with forward/backward pass and float', tag: 'Analysis', color: 'bg-green-500' },
		{ title: 'Schedule Compare', desc: 'Multi-layer matching with manipulation detection', tag: 'Comparison', color: 'bg-purple-500' },
		{ title: 'Forensic CPA', desc: 'Window analysis and delay waterfall per AACE RP 29R-03', tag: 'Claims', color: 'bg-orange-500' },
		{ title: 'Time Impact Analysis', desc: 'Delay fragments, impacted CPM per AACE RP 52R-06', tag: 'Claims', color: 'bg-orange-500' },
		{ title: 'Earned Value', desc: 'SPI, CPI, EAC, S-Curve per ANSI/EIA-748', tag: 'Controls', color: 'bg-cyan-500' },
		{ title: 'Monte Carlo QSRA', desc: '1,000-iteration risk simulation per AACE RP 57R-09', tag: 'Risk', color: 'bg-red-500' },
		{ title: 'What-If Simulator', desc: 'Scenario analysis with deterministic and probabilistic modes', tag: 'Intelligence', color: 'bg-indigo-500' },
		{ title: 'Schedule Optimizer', desc: 'Evolution Strategies for RCPSP makespan optimization', tag: 'Intelligence', color: 'bg-indigo-500' },
		{ title: 'ML Delay Prediction', desc: 'Activity-level risk scoring with explainable factors', tag: 'AI', color: 'bg-violet-500' },
		{ title: 'Duration Prediction', desc: 'RF + GB ensemble trained on benchmark database', tag: 'AI', color: 'bg-violet-500' },
		{ title: 'Anomaly Detection', desc: 'Statistical outlier detection using IQR and z-score methods', tag: 'AI', color: 'bg-violet-500' },
		{ title: 'Root Cause Analysis', desc: 'Backwards network trace to delay origin via NetworkX', tag: 'Forensic', color: 'bg-orange-500' },
		{ title: 'Benchmarks', desc: 'Cross-project percentile ranking against 100+ anonymized schedules', tag: 'Intelligence', color: 'bg-indigo-500' },
		{ title: 'Schedule Builder', desc: 'Generate schedules from NLP descriptions or project templates', tag: 'AI', color: 'bg-violet-500' },
		{ title: 'Calendar Validation', desc: 'Work calendar integrity checks per DCMA #13 with scoring', tag: 'Validation', color: 'bg-blue-500' },
		{ title: 'Delay Attribution', desc: 'Party breakdown: Owner vs Contractor excusable/non-excusable', tag: 'Claims', color: 'bg-orange-500' },
		{ title: 'Interactive Gantt', desc: 'WBS tree, baseline comparison, float bars, dependency lines, search & filter', tag: 'Visualization', color: 'bg-teal-500' },
		{ title: 'Schedule Trends', desc: 'Period-over-period evolution tracking with auto-insights per AACE RP 29R-03', tag: 'Intelligence', color: 'bg-indigo-500' },
		{ title: 'Metadata Intelligence', desc: 'Auto-detect update number, revision, type, baseline from XER data', tag: 'Intelligence', color: 'bg-indigo-500' },
	];
</script>

<svelte:head>
	<title>MeridianIQ — {$t('landing.title')}</title>
</svelte:head>

<div class="max-w-6xl mx-auto">
	<!-- HERO — unauthenticated landing -->
	{#if !authenticated && !loading}
		<div class="px-8 pt-16 pb-12">
			<div class="text-center max-w-3xl mx-auto">
				<p class="text-sm font-semibold text-blue-600 uppercase tracking-wide mb-3">{$t('landing.badge')}</p>
				<h1 class="text-4xl sm:text-5xl font-bold text-gray-900 leading-tight">
					{$t('landing.title')}
				</h1>
				<p class="mt-6 text-lg text-gray-600 leading-relaxed">
					{$t('landing.subtitle')}
				</p>
				<div class="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
					<a
						href="/login"
						class="px-8 py-3 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 shadow-sm transition-colors"
					>
						{$t('landing.cta.start')}
					</a>
					<a
						href="/demo"
						class="px-8 py-3 bg-white text-gray-700 text-sm font-semibold rounded-lg border border-gray-300 hover:border-gray-400 hover:bg-gray-50 shadow-sm transition-colors"
					>
						{$t('landing.cta.demo')}
					</a>
				</div>
				<p class="mt-4 text-center">
					<a
						href="https://github.com/VitorMRodovalho/meridianiq"
						target="_blank"
						rel="noopener"
						class="text-sm text-gray-400 hover:text-gray-600 transition-colors"
					>
						{$t('landing.cta.github')}
					</a>
				</p>
			</div>

			<!-- Key numbers -->
			<div class="mt-16 grid grid-cols-2 sm:grid-cols-4 gap-6 text-center">
				<div>
					<p class="text-3xl font-bold text-gray-900">35</p>
					<p class="text-sm text-gray-500 mt-1">{$t('landing.stats.engines')}</p>
				</div>
				<div>
					<p class="text-3xl font-bold text-gray-900">82</p>
					<p class="text-sm text-gray-500 mt-1">{$t('landing.stats.endpoints')}</p>
				</div>
				<div>
					<p class="text-3xl font-bold text-gray-900">792+</p>
					<p class="text-sm text-gray-500 mt-1">{$t('landing.stats.tests')}</p>
				</div>
				<div>
					<p class="text-3xl font-bold text-gray-900">$0</p>
					<p class="text-sm text-gray-500 mt-1">{$t('landing.stats.cost')}</p>
				</div>
			</div>
		</div>

		<!-- Capabilities grid -->
		<div class="px-8 pb-12">
			<h2 class="text-2xl font-bold text-gray-900 text-center mb-8">{$t('landing.capabilities.title')}</h2>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
				{#each capabilities as cap}
					<div class="bg-white rounded-lg border border-gray-200 p-5 hover:shadow-md transition-shadow">
						<div class="flex items-center gap-2 mb-2">
							<span class="inline-block w-2 h-2 rounded-full {cap.color}"></span>
							<span class="text-xs font-medium text-gray-500 uppercase">{cap.tag}</span>
						</div>
						<h3 class="font-semibold text-gray-900">{cap.title}</h3>
						<p class="text-sm text-gray-600 mt-1">{cap.desc}</p>
					</div>
				{/each}
			</div>
		</div>

		<!-- Standards -->
		<div class="px-8 pb-16">
			<div class="bg-gray-900 rounded-2xl p-8 sm:p-12 text-center">
				<h2 class="text-2xl font-bold text-white mb-4">{$t('landing.standards.title')}</h2>
				<p class="text-gray-400 text-sm max-w-2xl mx-auto mb-8">
					{$t('landing.standards.subtitle')}
				</p>
				<div class="flex flex-wrap justify-center gap-3">
					{#each ['AACE RP 29R-03', 'AACE RP 49R-06', 'AACE RP 52R-06', 'AACE RP 57R-09', 'ANSI/EIA-748', 'DCMA EVMS', 'GAO Schedule Guide', 'ISO 31000', 'SCL Protocol'] as std}
						<span class="px-3 py-1.5 bg-gray-800 text-gray-300 text-xs font-mono rounded-full">{std}</span>
					{/each}
				</div>
			</div>
		</div>

	<!-- DASHBOARD — authenticated users -->
	{:else if authenticated}
		<div class="p-8">
			<div class="mb-10">
				<h1 class="text-3xl font-bold text-gray-900">{$t('dashboard.title')}</h1>
				<p class="mt-2 text-gray-600">{$t('dashboard.subtitle')}</p>
			</div>

			<!-- Dashboard KPIs -->
			{#if dashboard}
				<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
					<div class="bg-white border border-gray-200 rounded-lg p-5">
						<p class="text-sm text-gray-500">{$t('dashboard.total_projects')}</p>
						<p class="text-3xl font-bold text-gray-900">{dashboard.total_projects}</p>
						<p class="text-xs text-gray-400 mt-1">Uploaded schedules</p>
					</div>
					<div class="bg-white border border-gray-200 rounded-lg p-5">
						<p class="text-sm text-gray-500">{$t('dashboard.avg_health')}</p>
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
						<p class="text-sm text-gray-500">{$t('dashboard.active_alerts')}</p>
						<p class="text-3xl font-bold {dashboard.active_alerts > 0 ? 'text-red-600' : 'text-green-600'}">{dashboard.active_alerts}</p>
						<p class="text-xs text-gray-400 mt-1">{dashboard.active_alerts === 0 ? 'No active warnings' : 'Requires attention'}</p>
					</div>
					{#if dashboard.most_critical_project}
						<div class="bg-red-50 border border-red-200 rounded-lg p-5">
							<p class="text-sm text-red-600 font-medium">{$t('dashboard.most_critical')}</p>
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
							<p class="text-sm text-green-600 font-medium">{$t('dashboard.portfolio_status')}</p>
							<p class="text-lg font-bold text-green-700 mt-1">{$t('dashboard.all_clear')}</p>
							<p class="text-xs text-green-500 mt-1">No critical issues detected</p>
						</div>
					{/if}
				</div>
			{/if}

			<!-- Portfolio Charts -->
			{#if healthDistribution.length > 0 && dashboard}
				<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
					<GaugeChart
						value={dashboard.avg_health_score}
						title="Portfolio Average Health"
						label="across {Object.keys(healthScores).length} projects"
						size={200}
					/>
					<PieChart
						title="Health Score Distribution"
						size={180}
						data={healthDistribution}
					/>
				</div>
			{/if}

			<!-- Projects at a Glance (top 5 by health score, lowest first) -->
			{#if projects.length > 0 && Object.keys(healthScores).length > 0}
				<div class="bg-white border border-gray-200 rounded-lg p-5 mb-10">
					<h2 class="text-sm font-semibold text-gray-900 mb-3">Projects at a Glance</h2>
					<div class="space-y-2">
						{#each projects
							.filter(p => healthScores[p.project_id])
							.sort((a, b) => (healthScores[a.project_id]?.overall || 0) - (healthScores[b.project_id]?.overall || 0))
							.slice(0, 6) as project}
							{@const hs = healthScores[project.project_id]}
							<a href="/projects/{project.project_id}" class="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 transition-colors group">
								<div class="w-9 h-9 rounded-full border-2 flex items-center justify-center text-xs font-bold shrink-0 {hs.overall >= 85 ? 'border-green-300 bg-green-50 text-green-700' : hs.overall >= 70 ? 'border-blue-300 bg-blue-50 text-blue-700' : hs.overall >= 50 ? 'border-amber-300 bg-amber-50 text-amber-700' : 'border-red-300 bg-red-50 text-red-700'}">
									{hs.overall.toFixed(0)}
								</div>
								<div class="flex-1 min-w-0">
									<p class="text-sm font-medium text-gray-900 truncate group-hover:text-blue-700">{project.name || project.project_id}</p>
									<div class="flex items-center gap-2 text-xs text-gray-500">
										<span>{project.activity_count} activities</span>
										<span class="capitalize">{hs.rating} {hs.trend_arrow}</span>
									</div>
								</div>
								<div class="w-20">
									<div class="h-1.5 rounded-full bg-gray-100 overflow-hidden">
										<div class="h-full rounded-full {hs.overall >= 85 ? 'bg-green-500' : hs.overall >= 70 ? 'bg-blue-500' : hs.overall >= 50 ? 'bg-amber-500' : 'bg-red-500'}" style="width: {hs.overall}%"></div>
									</div>
								</div>
							</a>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Quick Actions -->
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
				{#each [
					{ href: '/upload', title: 'Upload XER File', desc: 'Parse and analyze a Primavera P6 schedule export', icon: 'M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12', bg: 'bg-blue-100', fg: 'text-blue-600' },
					{ href: '/compare', title: 'Compare Schedules', desc: 'Detect changes and manipulation between versions', icon: 'M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4', bg: 'bg-purple-100', fg: 'text-purple-600' },
					{ href: '/scorecard', title: 'Schedule Scorecard', desc: 'Quick A-F grade across 5 quality dimensions', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z', bg: 'bg-green-100', fg: 'text-green-600' },
					{ href: '/schedule', title: 'Schedule Viewer', desc: 'Interactive Gantt with WBS, baseline, and dependencies', icon: 'M4 6h16M4 10h16M4 14h16M4 18h16', bg: 'bg-teal-100', fg: 'text-teal-600' },
					{ href: '/trends', title: 'Schedule Trends', desc: 'Track evolution across sequential updates', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6', bg: 'bg-indigo-100', fg: 'text-indigo-600' },
					{ href: '/reports', title: 'Reports Hub', desc: 'Generate and download PDF reports', icon: 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z', bg: 'bg-amber-100', fg: 'text-amber-600' },
				] as action}
					<a
						href={action.href}
						class="block bg-white rounded-lg border border-gray-200 p-5 hover:shadow-md hover:border-blue-300 transition-all"
					>
						<div class="flex items-center gap-4">
							<div class="w-11 h-11 {action.bg} rounded-lg flex items-center justify-center shrink-0">
								<svg class="w-5 h-5 {action.fg}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={action.icon} />
								</svg>
							</div>
							<div>
								<h2 class="text-sm font-semibold text-gray-900">{action.title}</h2>
								<p class="text-xs text-gray-500">{action.desc}</p>
							</div>
						</div>
					</a>
				{/each}
			</div>

			<!-- Programs -->
			{#if programs.length > 0}
				<div class="bg-white rounded-lg border border-gray-200 p-6 mb-10">
					<div class="flex items-center justify-between mb-4">
						<h2 class="text-lg font-semibold text-gray-900">Programs</h2>
						<span class="text-sm text-gray-400">{programs.length} program{programs.length !== 1 ? 's' : ''}</span>
					</div>
					<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
						{#each programs as program}
							<a
								href="/programs/{program.id}"
								class="block border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-md transition-all group"
							>
								<h3 class="font-medium text-gray-900 truncate group-hover:text-blue-700 transition-colors">{program.name}</h3>
								<div class="mt-2 flex gap-4 text-xs text-gray-500">
									<span class="flex items-center gap-1">
										<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
										{program.revision_count} revision{program.revision_count !== 1 ? 's' : ''}
									</span>
									{#if program.latest_revision}
										<span class="flex items-center gap-1">
											<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
											{program.latest_revision.activity_count} activities
										</span>
									{/if}
								</div>
								{#if program.description}
									<p class="mt-2 text-xs text-gray-400 truncate">{program.description}</p>
								{/if}
							</a>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Projects with Health Scores -->
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
										<div class="ml-2 w-10 h-10 rounded-full border-2 flex items-center justify-center text-sm font-bold shrink-0 {scoreCircleBg(hs.overall)}">
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
								<div class="mt-3 flex items-center gap-3 text-xs text-gray-500">
									<span>{project.activity_count.toLocaleString()} acts</span>
									<span>{project.relationship_count.toLocaleString()} rels</span>
									{#if project.tags?.length}
										<span class="flex gap-1 ml-auto">
											{#each project.tags.slice(0, 3) as tag}
												<span class="px-1.5 py-0.5 rounded text-[8px] font-medium bg-gray-100 dark:bg-gray-800 text-gray-500">{tag}</span>
											{/each}
										</span>
									{/if}
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
				<!-- Onboarding for first-time authenticated users -->
				<div class="bg-white rounded-lg border border-gray-200 overflow-hidden">
					<div class="bg-gradient-to-r from-blue-600 to-indigo-600 p-8 text-white">
						<h2 class="text-2xl font-bold">Welcome to MeridianIQ</h2>
						<p class="mt-2 text-blue-100">Let's analyze your first schedule. Here's how it works:</p>
					</div>
					<div class="p-8">
						<div class="grid grid-cols-1 md:grid-cols-3 gap-8">
							<div class="text-center">
								<div class="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
									<span class="text-xl font-bold text-blue-600">1</span>
								</div>
								<h3 class="font-semibold text-gray-900 mb-2">Upload</h3>
								<p class="text-sm text-gray-500">Export your schedule from Primavera P6 as an XER file and upload it here. We parse 17+ table types automatically.</p>
							</div>
							<div class="text-center">
								<div class="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
									<span class="text-xl font-bold text-blue-600">2</span>
								</div>
								<h3 class="font-semibold text-gray-900 mb-2">Analyze</h3>
								<p class="text-sm text-gray-500">Instant DCMA 14-Point validation, critical path analysis, float distribution, and health scoring. All automated.</p>
							</div>
							<div class="text-center">
								<div class="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
									<span class="text-xl font-bold text-blue-600">3</span>
								</div>
								<h3 class="font-semibold text-gray-900 mb-2">Compare & Report</h3>
								<p class="text-sm text-gray-500">Upload a second version to unlock comparison, forensic delay analysis, float trends, and early warning alerts.</p>
							</div>
						</div>
						<div class="mt-8 text-center">
							<a href="/upload" class="inline-block px-8 py-3 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 shadow-sm transition-colors">
								Upload your first XER file
							</a>
							<p class="mt-3 text-xs text-gray-400">Supports Primavera P6 XER exports (v7.0+). Max file size depends on server memory.</p>
						</div>
					</div>
				</div>
			{/if}
		</div>
	{:else}
		<!-- Loading state -->
		<div class="flex items-center justify-center h-64">
			<svg class="animate-spin h-8 w-8 text-gray-400" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
		</div>
	{/if}
</div>
