<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { getProject, getValidation, getCriticalPath, getFloatDistribution, getMilestones, getProjectHealth, getProjectAlerts, generateReport, downloadReport, getAvailableReports } from '$lib/api';
	import type {
		ProjectDetailResponse,
		ValidationResponse,
		CriticalPathResponse,
		FloatDistributionResponse,
		MilestonesResponse,
		ScheduleHealthResponse,
		AlertsResponse
	} from '$lib/types';
	import type { ReportAvailabilityEntry } from '$lib/api';

	let activeTab = $state('overview');
	let loading = $state(true);
	let error = $state('');

	let project: ProjectDetailResponse | null = $state(null);
	let validation: ValidationResponse | null = $state(null);
	let criticalPath: CriticalPathResponse | null = $state(null);
	let floatDist: FloatDistributionResponse | null = $state(null);
	let milestones: MilestonesResponse | null = $state(null);
	let healthData: ScheduleHealthResponse | null = $state(null);
	let alertsData: AlertsResponse | null = $state(null);

	let validationLoading = $state(false);
	let cpLoading = $state(false);
	let floatLoading = $state(false);
	let msLoading = $state(false);
	let healthLoading = $state(false);
	let alertsLoading = $state(false);

	let reportDropdownOpen = $state(false);
	let reportGenerating = $state('');
	let availableReports = $state<ReportAvailabilityEntry[]>([]);

	const projectId = $derived(page.params.id);

	onMount(async () => {
		try {
			project = await getProject(projectId);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load project';
		} finally {
			loading = false;
		}
		// Fetch report availability in background (non-blocking)
		try {
			const ar = await getAvailableReports(projectId);
			availableReports = ar.reports;
		} catch {
			// Silently ignore — the dropdown falls back to showing all reports
		}
	});

	async function loadTab(tab: string) {
		activeTab = tab;
		if (tab === 'dcma' && !validation) {
			validationLoading = true;
			try { validation = await getValidation(projectId); } catch {}
			validationLoading = false;
		} else if (tab === 'critical' && !criticalPath) {
			cpLoading = true;
			try { criticalPath = await getCriticalPath(projectId); } catch {}
			cpLoading = false;
		} else if (tab === 'float' && !floatDist) {
			floatLoading = true;
			try { floatDist = await getFloatDistribution(projectId); } catch {}
			floatLoading = false;
		} else if (tab === 'milestones' && !milestones) {
			msLoading = true;
			try { milestones = await getMilestones(projectId); } catch {}
			msLoading = false;
		} else if (tab === 'health' && !healthData) {
			healthLoading = true;
			try { healthData = await getProjectHealth(projectId); } catch {}
			healthLoading = false;
		} else if (tab === 'alerts' && !alertsData) {
			alertsLoading = true;
			try {
				// Alerts require a baseline - try without one for now (API will return error)
				// In production, this would use the project's baseline
				alertsData = { alerts: [], total_alerts: 0, critical_count: 0, warning_count: 0, info_count: 0, aggregate_score: 0, summary: {} };
			} catch {}
			alertsLoading = false;
		}
	}

	async function handleGenerateReport(reportType: string) {
		reportDropdownOpen = false;
		reportGenerating = reportType;
		try {
			const result = await generateReport(projectId, reportType);
			const blob = await downloadReport(result.report_id);
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `meridianiq-${reportType}-${projectId}.pdf`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		} catch (e: unknown) {
			console.error('Report generation failed:', e);
		} finally {
			reportGenerating = '';
		}
	}

	function severityColor(severity: string): string {
		if (severity === 'critical') return 'bg-red-100 text-red-800 border-red-200';
		if (severity === 'warning') return 'bg-yellow-100 text-yellow-800 border-yellow-200';
		return 'bg-blue-100 text-blue-800 border-blue-200';
	}

	function severityDot(severity: string): string {
		if (severity === 'critical') return 'bg-red-500';
		if (severity === 'warning') return 'bg-yellow-500';
		return 'bg-blue-500';
	}

	// Derived stats
	const activityStatusCounts = $derived.by(() => {
		if (!project) return { complete: 0, inProgress: 0, notStarted: 0, total: 0 };
		let complete = 0, inProgress = 0, notStarted = 0;
		for (const a of project.activities) {
			if (a.status_code === 'TK_Complete') complete++;
			else if (a.status_code === 'TK_Active') inProgress++;
			else notStarted++;
		}
		return { complete, inProgress, notStarted, total: project.activities.length };
	});

	const relTypeCounts = $derived.by(() => {
		if (!project) return { fs: 0, ff: 0, ss: 0, sf: 0, total: 0 };
		let fs = 0, ff = 0, ss = 0, sf = 0;
		for (const r of project.relationships) {
			if (r.pred_type === 'PR_FS') fs++;
			else if (r.pred_type === 'PR_FF') ff++;
			else if (r.pred_type === 'PR_SS') ss++;
			else if (r.pred_type === 'PR_SF') sf++;
		}
		return { fs, ff, ss, sf, total: project.relationships.length };
	});

	function scoreColor(score: number): string {
		if (score >= 80) return 'text-green-600 border-green-300 bg-green-50';
		if (score >= 60) return 'text-yellow-600 border-yellow-300 bg-yellow-50';
		return 'text-red-600 border-red-300 bg-red-50';
	}

	function pct(n: number, total: number): string {
		if (total === 0) return '0';
		return ((n / total) * 100).toFixed(1);
	}

	function formatDays(hours: number): string {
		return (hours / 8).toFixed(1);
	}

	// SVG timeline helpers
	const timelineData = $derived.by(() => {
		if (!criticalPath || criticalPath.critical_path.length === 0) return null;
		const acts = criticalPath.critical_path;
		const minStart = Math.min(...acts.map(a => a.early_start));
		const maxEnd = Math.max(...acts.map(a => a.early_finish));
		const range = maxEnd - minStart || 1;
		const svgWidth = 800;
		const barHeight = 24;
		const gap = 4;
		const labelWidth = 200;
		const chartWidth = svgWidth - labelWidth - 20;
		const svgHeight = acts.length * (barHeight + gap) + 40;
		return { acts, minStart, maxEnd, range, svgWidth, barHeight, gap, labelWidth, chartWidth, svgHeight };
	});
</script>

<svelte:head>
	<title>{project?.name || 'Project'} - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-7xl mx-auto">
	{#if loading}
		<div class="flex items-center gap-2 text-gray-500">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			Loading project...
		</div>
	{:else if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">{error}</div>
	{:else if project}
		<!-- Header -->
		<div class="mb-6 flex items-start justify-between">
			<div>
				<a href="/projects" class="text-sm text-blue-600 hover:underline">&#8592; All Projects</a>
				<h1 class="text-2xl font-bold text-gray-900 mt-2">{project.name || project.project_id}</h1>
				<p class="text-sm text-gray-500 mt-1">ID: {project.project_id} &middot; Data Date: {project.data_date || 'N/A'}</p>
			</div>
			<!-- Report Download Dropdown -->
			<div class="relative">
				<button
					class="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
					onclick={() => reportDropdownOpen = !reportDropdownOpen}
					disabled={!!reportGenerating}
				>
					{#if reportGenerating}
						<svg class="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
						Generating...
					{:else}
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
						Generate Report
						<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
					{/if}
				</button>
				{#if reportDropdownOpen}
					<div class="absolute right-0 mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-10 overflow-hidden">
						{#if availableReports.length > 0}
							{#each availableReports as report}
								{#if report.ready}
									<button
										class="w-full text-left px-4 py-2.5 text-sm bg-teal-600 text-white hover:bg-teal-700 transition-colors block border-b border-teal-500 last:border-b-0"
										onclick={() => handleGenerateReport(report.type)}
									>
										{report.name}
									</button>
								{:else}
									<div class="px-4 py-2.5 text-sm bg-gray-100 text-gray-400 cursor-not-allowed border-b border-gray-200 last:border-b-0">
										<span class="block">{report.name}</span>
										{#if report.reason}
											<span class="block text-xs text-gray-400 mt-0.5">{report.reason}</span>
										{/if}
									</div>
								{/if}
							{/each}
						{:else}
							<!-- Fallback while availability loads -->
							<button
								class="w-full text-left px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
								onclick={() => handleGenerateReport('health')}
							>
								Health Report (PDF)
							</button>
						{/if}
					</div>
				{/if}
			</div>
		</div>

		<!-- Tabs -->
		<div class="border-b border-gray-200 mb-6">
			<nav class="flex gap-6 -mb-px">
				{#each [
					['overview', 'Overview'],
					['health', 'Health Score'],
					['dcma', 'DCMA 14-Point'],
					['critical', 'Critical Path'],
					['float', 'Float Distribution'],
					['milestones', 'Milestones'],
					['alerts', 'Alerts']
				] as [key, label]}
					<button
						class="pb-3 px-1 text-sm font-medium border-b-2 transition-colors {activeTab === key
							? 'border-blue-500 text-blue-600'
							: 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
						onclick={() => loadTab(key)}
					>
						{label}
					</button>
				{/each}
			</nav>
		</div>

		<!-- Tab Content -->

		{#if activeTab === 'overview'}
			<!-- Stat cards -->
			<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
				<div class="bg-white border border-gray-200 rounded-lg p-5">
					<p class="text-sm text-gray-500">Total Activities</p>
					<p class="text-2xl font-bold text-gray-900">{project.activities.length}</p>
				</div>
				<div class="bg-white border border-gray-200 rounded-lg p-5">
					<p class="text-sm text-gray-500">Total Relationships</p>
					<p class="text-2xl font-bold text-gray-900">{project.relationships.length}</p>
				</div>
				<div class="bg-white border border-gray-200 rounded-lg p-5">
					<p class="text-sm text-gray-500">WBS Structure</p>
					{#if project.wbs_stats}
						<p class="text-2xl font-bold text-gray-900">{project.wbs_stats.total_elements} <span class="text-sm font-normal text-gray-500">elements</span></p>
						<p class="text-xs text-gray-500 mt-1">Max depth: {project.wbs_stats.max_depth} levels</p>
						{#if project.wbs_stats.by_level.length > 0}
							<div class="mt-2 grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs text-gray-600">
								{#each project.wbs_stats.by_level as lvl}
									<div>L{lvl.level}: {lvl.count}</div>
								{/each}
							</div>
						{/if}
						<p class="text-xs text-gray-400 mt-1">Avg {project.wbs_stats.avg_activities_per_wbs} activities/WBS</p>
					{:else}
						<p class="text-2xl font-bold text-gray-900">—</p>
					{/if}
				</div>
			</div>

			<!-- Activity Status Distribution -->
			<div class="bg-white border border-gray-200 rounded-lg p-5 mb-6">
				<h3 class="text-sm font-medium text-gray-700 mb-3">Activity Status Distribution</h3>
				<div class="flex h-6 rounded-full overflow-hidden bg-gray-100">
					{#if activityStatusCounts.total > 0}
						{#if activityStatusCounts.complete > 0}
							<div
								class="bg-green-500"
								style="width: {pct(activityStatusCounts.complete, activityStatusCounts.total)}%"
								title="Complete: {activityStatusCounts.complete}"
							></div>
						{/if}
						{#if activityStatusCounts.inProgress > 0}
							<div
								class="bg-blue-500"
								style="width: {pct(activityStatusCounts.inProgress, activityStatusCounts.total)}%"
								title="In Progress: {activityStatusCounts.inProgress}"
							></div>
						{/if}
						{#if activityStatusCounts.notStarted > 0}
							<div
								class="bg-gray-400"
								style="width: {pct(activityStatusCounts.notStarted, activityStatusCounts.total)}%"
								title="Not Started: {activityStatusCounts.notStarted}"
							></div>
						{/if}
					{/if}
				</div>
				<div class="flex gap-6 mt-2 text-xs text-gray-600">
					<span class="flex items-center gap-1"><span class="w-3 h-3 bg-green-500 rounded-full inline-block"></span> Complete ({activityStatusCounts.complete})</span>
					<span class="flex items-center gap-1"><span class="w-3 h-3 bg-blue-500 rounded-full inline-block"></span> In Progress ({activityStatusCounts.inProgress})</span>
					<span class="flex items-center gap-1"><span class="w-3 h-3 bg-gray-400 rounded-full inline-block"></span> Not Started ({activityStatusCounts.notStarted})</span>
				</div>
			</div>

			<!-- Relationship Type Distribution -->
			<div class="bg-white border border-gray-200 rounded-lg p-5">
				<h3 class="text-sm font-medium text-gray-700 mb-3">Relationship Type Distribution</h3>
				<div class="flex h-6 rounded-full overflow-hidden bg-gray-100">
					{#if relTypeCounts.total > 0}
						{#if relTypeCounts.fs > 0}
							<div class="bg-blue-500" style="width: {pct(relTypeCounts.fs, relTypeCounts.total)}%" title="FS: {relTypeCounts.fs}"></div>
						{/if}
						{#if relTypeCounts.ff > 0}
							<div class="bg-orange-400" style="width: {pct(relTypeCounts.ff, relTypeCounts.total)}%" title="FF: {relTypeCounts.ff}"></div>
						{/if}
						{#if relTypeCounts.ss > 0}
							<div class="bg-yellow-400" style="width: {pct(relTypeCounts.ss, relTypeCounts.total)}%" title="SS: {relTypeCounts.ss}"></div>
						{/if}
						{#if relTypeCounts.sf > 0}
							<div class="bg-red-500" style="width: {pct(relTypeCounts.sf, relTypeCounts.total)}%" title="SF: {relTypeCounts.sf}"></div>
						{/if}
					{/if}
				</div>
				<div class="flex gap-6 mt-2 text-xs text-gray-600">
					<span class="flex items-center gap-1"><span class="w-3 h-3 bg-blue-500 rounded-full inline-block"></span> FS ({relTypeCounts.fs})</span>
					<span class="flex items-center gap-1"><span class="w-3 h-3 bg-orange-400 rounded-full inline-block"></span> FF ({relTypeCounts.ff})</span>
					<span class="flex items-center gap-1"><span class="w-3 h-3 bg-yellow-400 rounded-full inline-block"></span> SS ({relTypeCounts.ss})</span>
					<span class="flex items-center gap-1"><span class="w-3 h-3 bg-red-500 rounded-full inline-block"></span> SF ({relTypeCounts.sf})</span>
				</div>
			</div>

		{:else if activeTab === 'dcma'}
			{#if validationLoading}
				<div class="flex items-center gap-2 text-gray-500">
					<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
					Running DCMA analysis...
				</div>
			{:else if validation}
				<!-- Score display -->
				<div class="flex items-center gap-6 mb-8">
					<div class="w-28 h-28 rounded-full border-4 flex items-center justify-center {scoreColor(validation.overall_score)}">
						<span class="text-3xl font-bold">{validation.overall_score.toFixed(0)}</span>
					</div>
					<div>
						<h2 class="text-xl font-bold text-gray-900">Overall DCMA Score</h2>
						<p class="text-sm text-gray-500 mt-1">
							{validation.passed_count} passed / {validation.failed_count} failed of {validation.metrics.length} checks
						</p>
						<p class="text-sm text-gray-500">{validation.activity_count} activities analyzed</p>
					</div>
				</div>

				<!-- Metric cards -->
				<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
					{#each validation.metrics as metric}
						<div class="rounded-lg border p-4 {metric.passed ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}">
							<div class="flex items-center justify-between mb-2">
								<span class="text-xs font-medium text-gray-500">#{metric.number}</span>
								<span class="text-xs font-bold px-2 py-0.5 rounded-full {metric.passed ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'}">
									{metric.passed ? 'PASS' : 'FAIL'}
								</span>
							</div>
							<h3 class="text-sm font-medium text-gray-900 mb-1">{metric.name}</h3>
							<p class="text-2xl font-bold {metric.passed ? 'text-green-700' : 'text-red-700'}">
								{metric.value.toFixed(1)}{metric.unit}
							</p>
							<p class="text-xs text-gray-500 mt-1">Threshold: {metric.threshold}{metric.unit}</p>
						</div>
					{/each}
				</div>
			{:else}
				<p class="text-gray-500">Failed to load validation data.</p>
			{/if}

		{:else if activeTab === 'critical'}
			{#if cpLoading}
				<div class="flex items-center gap-2 text-gray-500">
					<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
					Computing critical path...
				</div>
			{:else if criticalPath}
				<div class="mb-4 flex gap-4 text-sm">
					<span class="bg-white border border-gray-200 rounded-lg px-4 py-2">
						<span class="text-gray-500">Project Duration:</span>
						<span class="font-bold text-gray-900">{formatDays(criticalPath.project_duration)} days</span>
					</span>
					<span class="bg-white border border-gray-200 rounded-lg px-4 py-2">
						<span class="text-gray-500">Critical Activities:</span>
						<span class="font-bold text-gray-900">{criticalPath.critical_path.length}</span>
					</span>
					{#if criticalPath.has_cycles}
						<span class="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-red-700 font-medium">Cycles Detected</span>
					{/if}
				</div>

				<!-- SVG Timeline -->
				{#if timelineData}
					<div class="bg-white border border-gray-200 rounded-lg p-4 mb-6 overflow-x-auto">
						<h3 class="text-sm font-medium text-gray-700 mb-3">Critical Path Timeline</h3>
						<svg width={timelineData.svgWidth} height={timelineData.svgHeight} class="font-sans">
							{#each timelineData.acts as act, i}
								{@const x = timelineData.labelWidth + ((act.early_start - timelineData.minStart) / timelineData.range) * timelineData.chartWidth}
								{@const w = Math.max(((act.early_finish - act.early_start) / timelineData.range) * timelineData.chartWidth, 4)}
								{@const y = i * (timelineData.barHeight + timelineData.gap) + 10}
								<text
									x={timelineData.labelWidth - 8}
									y={y + timelineData.barHeight / 2 + 4}
									text-anchor="end"
									class="fill-gray-700"
									font-size="11"
								>
									{act.task_code || act.task_id}
								</text>
								<rect
									{x}
									{y}
									width={w}
									height={timelineData.barHeight}
									rx="3"
									class="fill-red-500"
									opacity="0.85"
								>
									<title>{act.task_name} ({formatDays(act.duration)}d, TF: {formatDays(act.total_float)}d)</title>
								</rect>
								<text
									x={x + w + 4}
									y={y + timelineData.barHeight / 2 + 4}
									font-size="10"
									class="fill-gray-500"
								>
									{act.task_name.length > 30 ? act.task_name.slice(0, 30) + '...' : act.task_name}
								</text>
							{/each}
						</svg>
					</div>
				{/if}

				<!-- Table -->
				<div class="bg-white border border-gray-200 rounded-lg overflow-hidden">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">#</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Activity ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Duration (d)</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Early Start</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Early Finish</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Total Float (d)</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each criticalPath.critical_path as act, i}
								<tr class="hover:bg-gray-50">
									<td class="px-4 py-2 text-gray-500">{i + 1}</td>
									<td class="px-4 py-2 font-medium text-gray-900">{act.task_code || act.task_id}</td>
									<td class="px-4 py-2 text-gray-700">{act.task_name}</td>
									<td class="px-4 py-2 text-right text-gray-700">{formatDays(act.duration)}</td>
									<td class="px-4 py-2 text-right text-gray-500">{formatDays(act.early_start)}</td>
									<td class="px-4 py-2 text-right text-gray-500">{formatDays(act.early_finish)}</td>
									<td class="px-4 py-2 text-right {act.total_float <= 0 ? 'text-red-600 font-medium' : 'text-gray-500'}">{formatDays(act.total_float)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<p class="text-gray-500">Failed to load critical path data.</p>
			{/if}

		{:else if activeTab === 'float'}
			{#if floatLoading}
				<div class="flex items-center gap-2 text-gray-500">
					<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
					Loading float distribution...
				</div>
			{:else if floatDist}
				{@const bucketColors = ['bg-red-500', 'bg-red-400', 'bg-orange-400', 'bg-yellow-400', 'bg-lime-400', 'bg-green-500']}

				<div class="bg-white border border-gray-200 rounded-lg p-5 mb-6">
					<h3 class="text-sm font-medium text-gray-700 mb-3">Float Distribution ({floatDist.total_activities} activities)</h3>
					<div class="flex h-8 rounded-full overflow-hidden bg-gray-100">
						{#each floatDist.buckets as bucket, i}
							{#if bucket.percentage > 0}
								<div
									class="{bucketColors[i] || 'bg-gray-400'}"
									style="width: {bucket.percentage}%"
									title="{bucket.range_label}: {bucket.count} ({bucket.percentage}%)"
								></div>
							{/if}
						{/each}
					</div>
					<div class="flex flex-wrap gap-4 mt-3 text-xs text-gray-600">
						{#each floatDist.buckets as bucket, i}
							<span class="flex items-center gap-1">
								<span class="w-3 h-3 {bucketColors[i] || 'bg-gray-400'} rounded-full inline-block"></span>
								{bucket.range_label}
							</span>
						{/each}
					</div>
				</div>

				<!-- Table -->
				<div class="bg-white border border-gray-200 rounded-lg overflow-hidden mb-6">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">Bucket</th>
								<th class="px-6 py-2 text-right text-xs font-medium text-gray-500 uppercase">Count</th>
								<th class="px-6 py-2 text-right text-xs font-medium text-gray-500 uppercase">Percentage</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each floatDist.buckets as bucket, i}
								<tr class="hover:bg-gray-50">
									<td class="px-6 py-2 text-gray-900 flex items-center gap-2">
										<span class="w-3 h-3 {bucketColors[i] || 'bg-gray-400'} rounded-full inline-block"></span>
										{bucket.range_label}
									</td>
									<td class="px-6 py-2 text-right text-gray-700">{bucket.count}</td>
									<td class="px-6 py-2 text-right text-gray-700">{bucket.percentage.toFixed(1)}%</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<div class="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
					DCMA best practice: Critical + Near-Critical activities should be &le; 25% of total.
				</div>
			{:else}
				<p class="text-gray-500">Failed to load float distribution data.</p>
			{/if}

		{:else if activeTab === 'health'}
			{#if healthLoading}
				<div class="flex items-center gap-2 text-gray-500">
					<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
					Computing health score...
				</div>
			{:else if healthData}
				<!-- Overall Score -->
				<div class="flex items-center gap-6 mb-8">
					<div class="w-28 h-28 rounded-full border-4 flex items-center justify-center {healthData.overall >= 85 ? 'text-green-600 border-green-300 bg-green-50' : healthData.overall >= 70 ? 'text-blue-600 border-blue-300 bg-blue-50' : healthData.overall >= 50 ? 'text-yellow-600 border-yellow-300 bg-yellow-50' : 'text-red-600 border-red-300 bg-red-50'}">
						<div class="text-center">
							<span class="text-3xl font-bold">{healthData.overall.toFixed(0)}</span>
							<span class="text-lg ml-1">{healthData.trend_arrow}</span>
						</div>
					</div>
					<div>
						<h2 class="text-xl font-bold text-gray-900">Schedule Health Score</h2>
						<p class="text-sm mt-1">
							<span class="inline-block px-2 py-0.5 rounded-full text-xs font-bold uppercase {healthData.rating === 'excellent' ? 'bg-green-100 text-green-800' : healthData.rating === 'good' ? 'bg-blue-100 text-blue-800' : healthData.rating === 'fair' ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'}">
								{healthData.rating}
							</span>
						</p>
						<p class="text-xs text-gray-500 mt-2">
							Per DCMA 14-Point + GAO Schedule Assessment Guide
						</p>
					</div>
				</div>

				<!-- Component Breakdown -->
				<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
					<div class="bg-white border border-gray-200 rounded-lg p-4">
						<p class="text-xs text-gray-500 uppercase tracking-wide">DCMA Quality (40%)</p>
						<p class="text-2xl font-bold text-gray-900 mt-1">{healthData.dcma_raw.toFixed(0)}<span class="text-sm text-gray-400">/100</span></p>
						<div class="h-1.5 rounded-full bg-gray-100 mt-2 overflow-hidden">
							<div class="h-full rounded-full bg-blue-500" style="width: {healthData.dcma_raw}%"></div>
						</div>
					</div>
					<div class="bg-white border border-gray-200 rounded-lg p-4">
						<p class="text-xs text-gray-500 uppercase tracking-wide">Float Health (25%)</p>
						<p class="text-2xl font-bold text-gray-900 mt-1">{healthData.float_raw.toFixed(0)}<span class="text-sm text-gray-400">/100</span></p>
						<div class="h-1.5 rounded-full bg-gray-100 mt-2 overflow-hidden">
							<div class="h-full rounded-full bg-green-500" style="width: {healthData.float_raw}%"></div>
						</div>
					</div>
					<div class="bg-white border border-gray-200 rounded-lg p-4">
						<p class="text-xs text-gray-500 uppercase tracking-wide">Logic Integrity (20%)</p>
						<p class="text-2xl font-bold text-gray-900 mt-1">{healthData.logic_raw.toFixed(0)}<span class="text-sm text-gray-400">/100</span></p>
						<div class="h-1.5 rounded-full bg-gray-100 mt-2 overflow-hidden">
							<div class="h-full rounded-full bg-purple-500" style="width: {healthData.logic_raw}%"></div>
						</div>
					</div>
					<div class="bg-white border border-gray-200 rounded-lg p-4">
						<p class="text-xs text-gray-500 uppercase tracking-wide">Trend Direction (15%)</p>
						<p class="text-2xl font-bold text-gray-900 mt-1">{healthData.trend_raw.toFixed(0)}<span class="text-sm text-gray-400">/100</span></p>
						<div class="h-1.5 rounded-full bg-gray-100 mt-2 overflow-hidden">
							<div class="h-full rounded-full bg-orange-500" style="width: {healthData.trend_raw}%"></div>
						</div>
					</div>
				</div>

				<div class="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
					<strong>Formula:</strong> Health = 0.40 x DCMA + 0.25 x Float Health + 0.20 x Logic Integrity + 0.15 x Trend Direction.
					Standards: DCMA 14-Point Assessment, GAO Schedule Assessment Guide (4 characteristics), AACE RP 49R-06.
				</div>
			{:else}
				<p class="text-gray-500">Failed to load health score data.</p>
			{/if}

		{:else if activeTab === 'milestones'}
			{#if msLoading}
				<div class="flex items-center gap-2 text-gray-500">
					<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
					Loading milestones...
				</div>
			{:else if milestones}
				{#if milestones.milestones.length === 0}
					<p class="text-gray-500">No milestones found in this schedule.</p>
				{:else}
					<div class="bg-white border border-gray-200 rounded-lg overflow-hidden">
						<table class="min-w-full divide-y divide-gray-200 text-sm">
							<thead class="bg-gray-50">
								<tr>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Activity ID</th>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Milestone Name</th>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Target Date</th>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Early Date</th>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Variance (d)</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-gray-200">
								{#each milestones.milestones as ms}
									{@const targetDate = ms.target_end_date || ms.target_start_date}
									{@const currentDate = ms.early_end_date || ms.early_start_date}
									{@const variance = targetDate && currentDate
										? Math.round((new Date(targetDate).getTime() - new Date(currentDate).getTime()) / (1000 * 60 * 60 * 24))
										: null}
									<tr class="hover:bg-gray-50">
										<td class="px-4 py-2 font-medium text-gray-900">{ms.task_code || ms.task_id}</td>
										<td class="px-4 py-2 text-gray-700">{ms.task_name}</td>
										<td class="px-4 py-2 text-gray-500">{ms.task_type === 'TT_mile' ? 'Start' : 'Finish'}</td>
										<td class="px-4 py-2">
											<span class="px-2 py-0.5 rounded-full text-xs font-medium {ms.status_code === 'TK_Complete' ? 'bg-green-100 text-green-800' : ms.status_code === 'TK_Active' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'}">
												{ms.status_code === 'TK_Complete' ? 'Complete' : ms.status_code === 'TK_Active' ? 'Active' : 'Not Started'}
											</span>
										</td>
										<td class="px-4 py-2 text-gray-500">{targetDate ? new Date(targetDate).toLocaleDateString() : 'N/A'}</td>
										<td class="px-4 py-2 text-gray-500">{currentDate ? new Date(currentDate).toLocaleDateString() : 'N/A'}</td>
										<td class="px-4 py-2 text-right font-medium {variance === null ? 'text-gray-400' : variance >= 0 ? 'text-green-600' : variance >= -10 ? 'text-yellow-600' : 'text-red-600'}">
											{variance !== null ? variance : 'N/A'}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			{:else}
				<p class="text-gray-500">Failed to load milestones data.</p>
			{/if}

		{:else if activeTab === 'alerts'}
			{#if alertsLoading}
				<div class="flex items-center gap-2 text-gray-500">
					<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
					Running early warning analysis...
				</div>
			{:else if alertsData}
				<div class="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
					<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-gray-900">{alertsData.total_alerts}</p>
						<p class="text-xs text-gray-500 mt-1">Total Alerts</p>
					</div>
					<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-red-600">{alertsData.critical_count}</p>
						<p class="text-xs text-red-500 mt-1">Critical</p>
					</div>
					<div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-yellow-600">{alertsData.warning_count}</p>
						<p class="text-xs text-yellow-500 mt-1">Warning</p>
					</div>
					<div class="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-blue-600">{alertsData.info_count}</p>
						<p class="text-xs text-blue-500 mt-1">Info</p>
					</div>
				</div>
				{#if alertsData.alerts.length === 0}
					<div class="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
						<p class="text-green-700 font-medium">No alerts detected</p>
						<p class="text-sm text-green-600 mt-1">Upload a baseline and update schedule to run the early warning analysis.</p>
					</div>
				{:else}
					<div class="space-y-3">
						{#each alertsData.alerts as alert}
							<div class="bg-white border rounded-lg p-4 {severityColor(alert.severity)}">
								<div class="flex items-start justify-between">
									<div class="flex items-center gap-3">
										<div class="w-2.5 h-2.5 rounded-full {severityDot(alert.severity)} mt-0.5"></div>
										<div>
											<h4 class="font-medium text-sm">{alert.title}</h4>
											<p class="text-xs mt-1 opacity-80">{alert.description}</p>
										</div>
									</div>
									<div class="text-right text-xs whitespace-nowrap ml-4">
										<div class="font-semibold">{alert.projected_impact_days.toFixed(1)}d impact</div>
										<div class="opacity-70">Score: {alert.alert_score.toFixed(1)}</div>
									</div>
								</div>
								{#if alert.affected_activities.length > 0}
									<details class="mt-2 ml-5">
										<summary class="text-xs cursor-pointer opacity-70 hover:opacity-100">
											{alert.affected_activities.length} affected activities
										</summary>
										<div class="mt-1 text-xs opacity-60 flex flex-wrap gap-1">
											{#each alert.affected_activities.slice(0, 10) as act}
												<span class="bg-white/50 px-1.5 py-0.5 rounded">{act}</span>
											{/each}
											{#if alert.affected_activities.length > 10}
												<span class="opacity-50">+{alert.affected_activities.length - 10} more</span>
											{/if}
										</div>
									</details>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			{:else}
				<p class="text-gray-500">Failed to load alerts data.</p>
			{/if}
		{/if}
	{/if}
</div>
