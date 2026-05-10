<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { getProject, getValidation, getCriticalPath, getFloatDistribution, getMilestones, getProjectHealth, getProjectAlerts, getDelayPrediction, generateReport, downloadReport, getAvailableReports, exportExcel, exportJSON, exportCSV, clearRevisionSkips } from '$lib/api';
	import { t } from '$lib/i18n';
	import { error as toastError, success } from '$lib/toast';
	import { trackEvent } from '$lib/analytics';
	import PieChart from '$lib/components/charts/PieChart.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';
	import GaugeChart from '$lib/components/charts/GaugeChart.svelte';
	import ScatterChart from '$lib/components/charts/ScatterChart.svelte';
	import ScheduleViewer from '$lib/components/ScheduleViewer/ScheduleViewer.svelte';
	import LifecyclePhaseCard from '$lib/components/LifecyclePhaseCard.svelte';
	import RevisionConfirmCard from '$lib/components/RevisionConfirmCard.svelte';
	import type { ScheduleViewData } from '$lib/components/ScheduleViewer/types';
	import type {
		ProjectDetailResponse,
		ValidationResponse,
		CriticalPathResponse,
		FloatDistributionResponse,
		MilestonesResponse,
		ScheduleHealthResponse,
		AlertsResponse,
		DelayPredictionResponse
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
	let predictionData: DelayPredictionResponse | null = $state(null);

	let validationLoading = $state(false);
	let cpLoading = $state(false);
	let floatLoading = $state(false);
	let msLoading = $state(false);
	let healthLoading = $state(false);
	let alertsLoading = $state(false);
	let predictionLoading = $state(false);
	let calendarData = $state<any>(null);
	let calendarLoading = $state(false);
	let attributionData = $state<any>(null);
	let attributionLoading = $state(false);
	let scheduleViewData = $state<ScheduleViewData | null>(null);
	let scheduleViewLoading = $state(false);

	let reportDropdownOpen = $state(false);
	let reportGenerating = $state('');
	let availableReports = $state<ReportAvailabilityEntry[]>([]);
	let excelExporting = $state(false);
	let exportDropdownOpen = $state(false);
	let exportingFormat = $state('');

	// Cycle 5 W3-E (issue #84): revision reconsider mechanism. When user
	// clicks "Confirm as revision of...", clear the persistent skip log
	// + mount the RevisionConfirmCard which re-runs detect (now without
	// skip filter, so the previously-dismissed candidate resurfaces).
	let revisionReconsiderShown = $state(false);
	let revisionReconsiderLoading = $state(false);

	async function handleReconsiderRevision(): Promise<void> {
		revisionReconsiderLoading = true;
		try {
			const result = await clearRevisionSkips(projectId);
			trackEvent('revision_reconsider_started', {
				project_id: projectId,
				cleared_count: result.cleared_count
			});
			if (result.cleared_count === 0) {
				// No skips to clear — user gets the card mounted anyway so
				// they can confirm or skip without prior history.
				success($t('revision.reconsider_no_prior_skip'));
			}
			revisionReconsiderShown = true;
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			toastError(msg);
		} finally {
			revisionReconsiderLoading = false;
		}
	}

	async function handleExcelExport() {
		excelExporting = true;
		try {
			const blob = await exportExcel(projectId);
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `meridianiq-${projectId}.xlsx`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		} catch (e: unknown) {
			console.error('Excel export failed:', e);
		} finally {
			excelExporting = false;
		}
	}

	async function handleDataExport(format: string, dataset?: string) {
		exportDropdownOpen = false;
		exportingFormat = format + (dataset ? `-${dataset}` : '');
		try {
			const blob = format === 'json'
				? await exportJSON(projectId)
				: await exportCSV(projectId, dataset || 'activities');
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			const ext = format === 'json' ? 'json' : 'csv';
			const suffix = dataset && dataset !== 'activities' ? `-${dataset}` : '';
			a.download = `meridianiq-${projectId}${suffix}.${ext}`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		} catch (e: unknown) {
			console.error('Export failed:', e);
		} finally {
			exportingFormat = '';
		}
	}

	const projectId = $derived(page.params.id!);

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
		} else if (tab === 'prediction' && !predictionData) {
			predictionLoading = true;
			try { predictionData = await getDelayPrediction(projectId); } catch {}
			predictionLoading = false;
		} else if (tab === 'schedule' && !scheduleViewData) {
			scheduleViewLoading = true;
			try {
				const BASE = import.meta.env.VITE_API_URL || '';
				const res = await fetch(`${BASE}/api/v1/projects/${projectId}/schedule-view`);
				if (res.ok) scheduleViewData = await res.json();
			} catch {}
			scheduleViewLoading = false;
		} else if (tab === 'calendar' && !calendarData) {
			calendarLoading = true;
			try {
				const BASE = import.meta.env.VITE_API_URL || '';
				const res = await fetch(`${BASE}/api/v1/projects/${projectId}/calendar-validation`);
				if (res.ok) calendarData = await res.json();
			} catch {}
			calendarLoading = false;
		} else if (tab === 'attribution' && !attributionData) {
			attributionLoading = true;
			try {
				const BASE = import.meta.env.VITE_API_URL || '';
				const res = await fetch(`${BASE}/api/v1/projects/${projectId}/delay-attribution`);
				if (res.ok) attributionData = await res.json();
			} catch {}
			attributionLoading = false;
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
	// Use server-side summaries (avoids iterating full arrays client-side)
	const activityStatusCounts = $derived.by(() => {
		if (!project) return { complete: 0, inProgress: 0, notStarted: 0, total: 0 };
		if (project.activity_summary) {
			return {
				complete: project.activity_summary.complete,
				inProgress: project.activity_summary.in_progress,
				notStarted: project.activity_summary.not_started,
				total: project.activity_summary.total,
			};
		}
		// Fallback: compute from array (backward compat)
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
		if (project.relationship_summary) {
			return project.relationship_summary;
		}
		// Fallback: compute from array (backward compat)
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
		if (score >= 80) return 'text-green-600 border-green-300 bg-green-50 dark:bg-green-950';
		if (score >= 60) return 'text-yellow-600 border-yellow-300 bg-yellow-50 dark:bg-yellow-950';
		return 'text-red-600 border-red-300 bg-red-50 dark:bg-red-950';
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
		<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			Loading project...
		</div>
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 text-sm text-red-700">{error}</div>
	{:else if project}
		<!-- Header -->
		<div class="mb-6 flex items-start justify-between">
			<div>
				<a href="/projects" class="text-sm text-blue-600 hover:underline">&#8592; All Projects</a>
				<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-2">{project.name || project.project_id}</h1>
				<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">ID: {project.project_id} &middot; Data Date: {project.data_date || 'N/A'}</p>
			</div>
			<div class="flex items-center gap-2">
			<a
				href="/schedule?project={projectId}"
				class="inline-flex items-center gap-1.5 px-3 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>
				Schedule
			</a>
			<!-- Data Export Dropdown -->
			<div class="relative">
				<button
					class="inline-flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
					onclick={() => exportDropdownOpen = !exportDropdownOpen}
					disabled={!!exportingFormat || excelExporting}
				>
					{#if exportingFormat || excelExporting}
						<svg class="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
						Exporting...
					{:else}
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
						Export
						<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
					{/if}
				</button>
				{#if exportDropdownOpen}
					<div class="absolute right-0 mt-1 w-56 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-10 overflow-hidden">
						<button class="w-full text-left px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 border-b border-gray-100" onclick={() => { exportDropdownOpen = false; window.open(`${import.meta.env.VITE_API_URL || ''}/api/v1/projects/${projectId}/export/xer`, '_blank'); }}>
							XER (.xer) — Primavera P6
						</button>
						<button class="w-full text-left px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 border-b border-gray-100" onclick={() => { exportDropdownOpen = false; handleExcelExport(); }}>
							Excel (.xlsx) — Full workbook
						</button>
						<button class="w-full text-left px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 border-b border-gray-100" onclick={() => handleDataExport('json')}>
							JSON — All data + analysis
						</button>
						<div class="px-4 py-1.5 text-xs font-medium text-gray-400 uppercase bg-gray-50 dark:bg-gray-800">CSV Datasets</div>
						<button class="w-full text-left px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 border-b border-gray-100" onclick={() => handleDataExport('csv', 'activities')}>
							CSV — Activities
						</button>
						<button class="w-full text-left px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 border-b border-gray-100" onclick={() => handleDataExport('csv', 'dcma')}>
							CSV — DCMA Metrics
						</button>
						<button class="w-full text-left px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800" onclick={() => handleDataExport('csv', 'relationships')}>
							CSV — Relationships
						</button>
					</div>
				{/if}
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
					<div class="absolute right-0 mt-1 w-64 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-10 overflow-hidden">
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
									<div class="px-4 py-2.5 text-sm bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed border-b border-gray-200 dark:border-gray-700 last:border-b-0">
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
								class="w-full text-left px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
								onclick={() => handleGenerateReport('health')}
							>
								Health Report (PDF)
							</button>
						{/if}
					</div>
				{/if}
			</div>
		</div>
		</div>

		<!-- Lifecycle Phase (W3 of Cycle 1 v4.0 — ADR-0016) -->
		<div class="mb-6">
			<LifecyclePhaseCard {projectId} />
		</div>

		<!-- Revision Reconsider (Cycle 5 W3-E — issue #84):
		     If the user previously skipped a revision-confirmation candidate
		     for this project, the detect endpoint now filters that candidate
		     out forever. The "Confirm as revision of..." button clears the
		     skip log so a subsequent detect call resurfaces the suggestion. -->
		{#if !revisionReconsiderShown}
			<div class="mb-6">
				<button
					type="button"
					onclick={handleReconsiderRevision}
					disabled={revisionReconsiderLoading}
					class="px-4 py-2 text-sm rounded border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/40 hover:bg-amber-100 dark:hover:bg-amber-900/40 text-amber-900 dark:text-amber-200 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-amber-500"
				>
					{revisionReconsiderLoading
						? $t('revision.reconsidering')
						: $t('revision.reconsider_button')}
				</button>
			</div>
		{:else}
			<div class="mb-6">
				<RevisionConfirmCard
					{projectId}
					onConfirmed={() => {
						revisionReconsiderShown = false;
					}}
					onSkipped={() => {
						revisionReconsiderShown = false;
					}}
				/>
			</div>
		{/if}

		<!-- Tabs -->
		<div class="border-b border-gray-200 dark:border-gray-700 mb-6">
			<nav class="flex gap-6 -mb-px">
				{#each [
					['overview', 'Overview'],
					['health', 'Health Score'],
					['dcma', 'DCMA 14-Point'],
					['critical', 'Critical Path'],
					['float', 'Float Distribution'],
					['milestones', 'Milestones'],
					['alerts', 'Alerts'],
					['prediction', 'Delay Prediction'],
					['schedule', 'Schedule'],
					['calendar', 'Calendars'],
					['attribution', 'Delay Attribution'],
				] as [key, label]}
					<button
						class="pb-3 px-1 text-sm font-medium border-b-2 transition-colors {activeTab === key
							? 'border-blue-500 text-blue-600'
							: 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-300 hover:border-gray-300 dark:border-gray-600'}"
						onclick={() => loadTab(key)}
					>
						{label}
					</button>
				{/each}
			</nav>
		</div>

		<!-- Quick Actions -->
		<div class="flex flex-wrap gap-2 mb-6">
			<a href="/scorecard" class="inline-flex items-center gap-1 px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-full text-xs font-medium hover:bg-indigo-100 transition-colors">Scorecard</a>
			<a href="/whatif" class="inline-flex items-center gap-1 px-3 py-1.5 bg-amber-50 dark:bg-amber-950 text-amber-700 rounded-full text-xs font-medium hover:bg-amber-100 transition-colors">What-If</a>
			<a href="/resources" class="inline-flex items-center gap-1 px-3 py-1.5 bg-teal-50 text-teal-700 rounded-full text-xs font-medium hover:bg-teal-100 transition-colors">Resources</a>
			<a href="/visualization" class="inline-flex items-center gap-1 px-3 py-1.5 bg-purple-50 text-purple-700 rounded-full text-xs font-medium hover:bg-purple-100 transition-colors">4D View</a>
			<a href="/risk-register" class="inline-flex items-center gap-1 px-3 py-1.5 bg-red-50 dark:bg-red-950 text-red-700 rounded-full text-xs font-medium hover:bg-red-100 transition-colors">Risk Register</a>
		</div>

		<!-- Tab Content -->

		{#if activeTab === 'overview'}
			<!-- Stat cards -->
			<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-5">
					<p class="text-sm text-gray-500 dark:text-gray-400">Total Activities</p>
					<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{project.activities.length}</p>
				</div>
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-5">
					<p class="text-sm text-gray-500 dark:text-gray-400">Total Relationships</p>
					<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{project.relationships.length}</p>
				</div>
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-5">
					<p class="text-sm text-gray-500 dark:text-gray-400">WBS Structure</p>
					{#if project.wbs_stats}
						<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{project.wbs_stats.total_elements} <span class="text-sm font-normal text-gray-500">elements</span></p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Max depth: {project.wbs_stats.max_depth} levels</p>
						{#if project.wbs_stats.by_level.length > 0}
							<div class="mt-2 grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs text-gray-600 dark:text-gray-400">
								{#each project.wbs_stats.by_level as lvl}
									<div>L{lvl.level}: {lvl.count}</div>
								{/each}
							</div>
						{/if}
						<p class="text-xs text-gray-400 mt-1">Avg {project.wbs_stats.avg_activities_per_wbs} activities/WBS</p>
					{:else}
						<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">—</p>
					{/if}
				</div>
			</div>

			<!-- Charts Row: Activity Status + Relationship Types -->
			<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
				<PieChart
					title="Activity Status Distribution"
					size={180}
					data={[
						{ label: 'Complete', value: activityStatusCounts.complete, color: '#22c55e' },
						{ label: 'In Progress', value: activityStatusCounts.inProgress, color: '#3b82f6' },
						{ label: 'Not Started', value: activityStatusCounts.notStarted, color: '#9ca3af' },
					]}
				/>
				<PieChart
					title="Relationship Type Distribution"
					size={180}
					data={[
						{ label: 'FS (Finish-Start)', value: relTypeCounts.fs, color: '#3b82f6' },
						{ label: 'FF (Finish-Finish)', value: relTypeCounts.ff, color: '#fb923c' },
						{ label: 'SS (Start-Start)', value: relTypeCounts.ss, color: '#facc15' },
						{ label: 'SF (Start-Finish)', value: relTypeCounts.sf, color: '#ef4444' },
					]}
				/>
			</div>

		{:else if activeTab === 'dcma'}
			{#if validationLoading}
				<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
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
						<h2 class="text-xl font-bold text-gray-900 dark:text-gray-100">Overall DCMA Score</h2>
						<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
							{validation.passed_count} passed / {validation.failed_count} failed of {validation.metrics.length} checks
						</p>
						<p class="text-sm text-gray-500 dark:text-gray-400">{validation.activity_count} activities analyzed</p>
					</div>
				</div>

				<!-- DCMA Metrics Chart -->
				<div class="mb-8">
					<BarChart
						title="DCMA 14-Point — Value vs Threshold"
						horizontal={true}
						height={Math.max(220, validation.metrics.length * 32)}
						data={validation.metrics.map((m) => ({
							label: `#${m.number} ${m.name}`,
							value: m.value,
							threshold: m.threshold,
							color: m.passed ? '#10b981' : '#ef4444',
						}))}
						formatValue={(v) => v.toFixed(1) + '%'}
					/>
				</div>

				<!-- Metric cards -->
				<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
					{#each validation.metrics as metric}
						<div class="rounded-lg border p-4 {metric.passed ? 'bg-green-50 dark:bg-green-950 border-green-200' : 'bg-red-50 dark:bg-red-950 border-red-200'}">
							<div class="flex items-center justify-between mb-2">
								<span class="text-xs font-medium text-gray-500 dark:text-gray-400">#{metric.number}</span>
								<span class="text-xs font-bold px-2 py-0.5 rounded-full {metric.passed ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'}">
									{metric.passed ? 'PASS' : 'FAIL'}
								</span>
							</div>
							<h3 class="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">{metric.name}</h3>
							<p class="text-2xl font-bold {metric.passed ? 'text-green-700' : 'text-red-700'}">
								{metric.value.toFixed(1)}{metric.unit}
							</p>
							<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Threshold: {metric.direction === 'min' ? '<=' : '>='} {metric.threshold}{metric.unit}</p>
						</div>
					{/each}
				</div>
			{:else}
				<p class="text-gray-500 dark:text-gray-400">Failed to load validation data.</p>
			{/if}

		{:else if activeTab === 'critical'}
			{#if cpLoading}
				<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
					<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
					Computing critical path...
				</div>
			{:else if criticalPath}
				<div class="mb-4 flex gap-4 text-sm">
					<span class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-2">
						<span class="text-gray-500 dark:text-gray-400">Project Duration:</span>
						<span class="font-bold text-gray-900 dark:text-gray-100">{formatDays(criticalPath.project_duration)} days</span>
					</span>
					<span class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-2">
						<span class="text-gray-500 dark:text-gray-400">Critical Activities:</span>
						<span class="font-bold text-gray-900 dark:text-gray-100">{criticalPath.critical_path.length}</span>
					</span>
					{#if criticalPath.has_cycles}
						<span class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg px-4 py-2 text-red-700 font-medium">Cycles Detected</span>
					{/if}
				</div>

				<!-- SVG Timeline -->
				{#if timelineData}
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 mb-6 overflow-x-auto">
						<h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Critical Path Timeline</h3>
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
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">#</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Activity ID</th>
								<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Duration (d)</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Early Start</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Early Finish</th>
								<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Total Float (d)</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each criticalPath.critical_path as act, i}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="px-4 py-2 text-gray-500 dark:text-gray-400">{i + 1}</td>
									<td class="px-4 py-2 font-medium text-gray-900 dark:text-gray-100">{act.task_code || act.task_id}</td>
									<td class="px-4 py-2 text-gray-700 dark:text-gray-300">{act.task_name}</td>
									<td class="px-4 py-2 text-right text-gray-700 dark:text-gray-300">{formatDays(act.duration)}</td>
									<td class="px-4 py-2 text-right text-gray-500 dark:text-gray-400">{formatDays(act.early_start)}</td>
									<td class="px-4 py-2 text-right text-gray-500 dark:text-gray-400">{formatDays(act.early_finish)}</td>
									<td class="px-4 py-2 text-right {act.total_float <= 0 ? 'text-red-600 font-medium' : 'text-gray-500 dark:text-gray-400'}">{formatDays(act.total_float)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<p class="text-gray-500 dark:text-gray-400">Failed to load critical path data.</p>
			{/if}

		{:else if activeTab === 'float'}
			{#if floatLoading}
				<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
					<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
					Loading float distribution...
				</div>
			{:else if floatDist}
				{@const bucketColors = ['bg-red-500', 'bg-red-400', 'bg-orange-400', 'bg-yellow-400', 'bg-lime-400', 'bg-green-500']}
				{@const barColors = ['#ef4444', '#f87171', '#fb923c', '#facc15', '#a3e635', '#22c55e']}

				<!-- Float Distribution Bar Chart -->
				<div class="mb-6">
					<BarChart
						title="Float Distribution — {floatDist.total_activities} activities"
						height={240}
						data={floatDist.buckets.map((b, i) => ({
							label: b.range_label,
							value: b.count,
							color: barColors[i] || '#6b7280',
						}))}
						formatValue={(v) => Math.round(v).toString()}
					/>
				</div>

				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-5 mb-6">
					<h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Float Distribution ({floatDist.total_activities} activities)</h3>
					<div class="flex h-8 rounded-full overflow-hidden bg-gray-100 dark:bg-gray-800">
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
					<div class="flex flex-wrap gap-4 mt-3 text-xs text-gray-600 dark:text-gray-400">
						{#each floatDist.buckets as bucket, i}
							<span class="flex items-center gap-1">
								<span class="w-3 h-3 {bucketColors[i] || 'bg-gray-400'} rounded-full inline-block"></span>
								{bucket.range_label}
							</span>
						{/each}
					</div>
				</div>

				<!-- Table -->
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-x-auto mb-6">
					<table class="min-w-full divide-y divide-gray-200 text-sm">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th class="px-6 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Bucket</th>
								<th class="px-6 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Count</th>
								<th class="px-6 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Percentage</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each floatDist.buckets as bucket, i}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="px-6 py-2 text-gray-900 dark:text-gray-100 flex items-center gap-2">
										<span class="w-3 h-3 {bucketColors[i] || 'bg-gray-400'} rounded-full inline-block"></span>
										{bucket.range_label}
									</td>
									<td class="px-6 py-2 text-right text-gray-700 dark:text-gray-300">{bucket.count}</td>
									<td class="px-6 py-2 text-right text-gray-700 dark:text-gray-300">{bucket.percentage.toFixed(1)}%</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<div class="bg-blue-50 dark:bg-blue-950 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
					DCMA best practice: Critical + Near-Critical activities should be &le; 25% of total.
				</div>
			{:else}
				<p class="text-gray-500 dark:text-gray-400">Failed to load float distribution data.</p>
			{/if}

		{:else if activeTab === 'health'}
			{#if healthLoading}
				<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
					<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
					Computing health score...
				</div>
			{:else if healthData}
				<!-- Overall Score with Gauge -->
				<div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
					<GaugeChart
						value={healthData.overall}
						title="Schedule Health Score"
						label="{healthData.rating.toUpperCase()} {healthData.trend_arrow}"
						size={200}
					/>
					<div class="lg:col-span-2 flex items-center">
						<div>
							<h2 class="text-xl font-bold text-gray-900 dark:text-gray-100">Schedule Health Score</h2>
							<p class="text-sm mt-1">
								<span class="inline-block px-2 py-0.5 rounded-full text-xs font-bold uppercase {healthData.rating === 'excellent' ? 'bg-green-100 text-green-800' : healthData.rating === 'good' ? 'bg-blue-100 text-blue-800' : healthData.rating === 'fair' ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'}">
									{healthData.rating}
								</span>
								<span class="text-lg ml-2">{healthData.trend_arrow}</span>
							</p>
							<p class="text-xs text-gray-500 dark:text-gray-400 mt-2">
								Per DCMA 14-Point + GAO Schedule Assessment Guide (2020)
							</p>
							<p class="text-xs text-gray-400 mt-1">
								Score = 40% DCMA + 25% Float + 20% Logic + 15% Trend
							</p>
						</div>
					</div>
				</div>

				<!-- Component Breakdown -->
				<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">DCMA Quality (40%)</p>
						<p class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{healthData.dcma_raw.toFixed(0)}<span class="text-sm text-gray-400">/100</span></p>
						<div class="h-1.5 rounded-full bg-gray-100 dark:bg-gray-800 mt-2 overflow-hidden">
							<div class="h-full rounded-full bg-blue-500" style="width: {healthData.dcma_raw}%"></div>
						</div>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Float Health (25%)</p>
						<p class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{healthData.float_raw.toFixed(0)}<span class="text-sm text-gray-400">/100</span></p>
						<div class="h-1.5 rounded-full bg-gray-100 dark:bg-gray-800 mt-2 overflow-hidden">
							<div class="h-full rounded-full bg-green-500" style="width: {healthData.float_raw}%"></div>
						</div>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Logic Integrity (20%)</p>
						<p class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{healthData.logic_raw.toFixed(0)}<span class="text-sm text-gray-400">/100</span></p>
						<div class="h-1.5 rounded-full bg-gray-100 dark:bg-gray-800 mt-2 overflow-hidden">
							<div class="h-full rounded-full bg-purple-500" style="width: {healthData.logic_raw}%"></div>
						</div>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Trend Direction (15%)</p>
						<p class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{healthData.trend_raw.toFixed(0)}<span class="text-sm text-gray-400">/100</span></p>
						<div class="h-1.5 rounded-full bg-gray-100 dark:bg-gray-800 mt-2 overflow-hidden">
							<div class="h-full rounded-full bg-orange-500" style="width: {healthData.trend_raw}%"></div>
						</div>
					</div>
				</div>

				<div class="bg-blue-50 dark:bg-blue-950 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
					<strong>Formula:</strong> Health = 0.40 x DCMA + 0.25 x Float Health + 0.20 x Logic Integrity + 0.15 x Trend Direction.
					Standards: DCMA 14-Point Assessment, GAO Schedule Assessment Guide (4 characteristics), AACE RP 49R-06.
				</div>
			{:else}
				<p class="text-gray-500 dark:text-gray-400">Failed to load health score data.</p>
			{/if}

		{:else if activeTab === 'milestones'}
			{#if msLoading}
				<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
					<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
					Loading milestones...
				</div>
			{:else if milestones}
				{#if milestones.milestones.length === 0}
					<p class="text-gray-500 dark:text-gray-400">No milestones found in this schedule.</p>
				{:else}
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-x-auto">
						<table class="min-w-full divide-y divide-gray-200 text-sm">
							<thead class="bg-gray-50 dark:bg-gray-800">
								<tr>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Activity ID</th>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Milestone Name</th>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Type</th>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Target Date</th>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Early Date</th>
									<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Variance (d)</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-gray-200">
								{#each milestones.milestones as ms}
									{@const targetDate = ms.target_end_date || ms.target_start_date}
									{@const currentDate = ms.early_end_date || ms.early_start_date}
									{@const variance = targetDate && currentDate
										? Math.round((new Date(targetDate).getTime() - new Date(currentDate).getTime()) / (1000 * 60 * 60 * 24))
										: null}
									<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
										<td class="px-4 py-2 font-medium text-gray-900 dark:text-gray-100">{ms.task_code || ms.task_id}</td>
										<td class="px-4 py-2 text-gray-700 dark:text-gray-300">{ms.task_name}</td>
										<td class="px-4 py-2 text-gray-500 dark:text-gray-400">{ms.task_type === 'TT_mile' ? 'Start' : 'Finish'}</td>
										<td class="px-4 py-2">
											<span class="px-2 py-0.5 rounded-full text-xs font-medium {ms.status_code === 'TK_Complete' ? 'bg-green-100 text-green-800' : ms.status_code === 'TK_Active' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 dark:bg-gray-800 text-gray-800'}">
												{ms.status_code === 'TK_Complete' ? 'Complete' : ms.status_code === 'TK_Active' ? 'Active' : 'Not Started'}
											</span>
										</td>
										<td class="px-4 py-2 text-gray-500 dark:text-gray-400">{targetDate ? new Date(targetDate).toLocaleDateString() : 'N/A'}</td>
										<td class="px-4 py-2 text-gray-500 dark:text-gray-400">{currentDate ? new Date(currentDate).toLocaleDateString() : 'N/A'}</td>
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
				<p class="text-gray-500 dark:text-gray-400">Failed to load milestones data.</p>
			{/if}

		{:else if activeTab === 'alerts'}
			{#if alertsLoading}
				<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
					<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
					Running early warning analysis...
				</div>
			{:else if alertsData}
				<div class="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{alertsData.total_alerts}</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Total Alerts</p>
					</div>
					<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-red-600">{alertsData.critical_count}</p>
						<p class="text-xs text-red-500 mt-1">Critical</p>
					</div>
					<div class="bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-yellow-600">{alertsData.warning_count}</p>
						<p class="text-xs text-yellow-500 mt-1">Warning</p>
					</div>
					<div class="bg-blue-50 dark:bg-blue-950 border border-blue-200 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-blue-600">{alertsData.info_count}</p>
						<p class="text-xs text-blue-500 mt-1">Info</p>
					</div>
				</div>
				{#if alertsData.alerts.length === 0}
					<div class="bg-green-50 dark:bg-green-950 border border-green-200 rounded-lg p-6 text-center">
						<p class="text-green-700 font-medium">No alerts detected</p>
						<p class="text-sm text-green-600 mt-1">Upload a baseline and update schedule to run the early warning analysis.</p>
					</div>
				{:else}
					<div class="space-y-3">
						{#each alertsData.alerts as alert}
							<div class="bg-white dark:bg-gray-900 border rounded-lg p-4 {severityColor(alert.severity)}">
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
												<span class="bg-white dark:bg-gray-900/50 px-1.5 py-0.5 rounded">{act}</span>
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
				<p class="text-gray-500 dark:text-gray-400">Failed to load alerts data.</p>
			{/if}

		{:else if activeTab === 'prediction'}
			{#if predictionLoading}
				<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
					<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
					Running delay prediction analysis...
				</div>
			{:else if predictionData}
				<!-- Summary Cards -->
				<div class="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold {predictionData.project_risk_level === 'critical' ? 'text-red-600' : predictionData.project_risk_level === 'high' ? 'text-orange-600' : predictionData.project_risk_level === 'medium' ? 'text-yellow-600' : 'text-green-600'}">
							{predictionData.project_risk_score.toFixed(0)}
						</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Project Risk Score</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-red-600">{predictionData.critical_risk_count}</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Critical Risk</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-orange-600">{predictionData.high_risk_count}</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">High Risk</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-2xl font-bold text-gray-700 dark:text-gray-300">{predictionData.predicted_completion_delay.toFixed(0)}d</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Predicted Delay</p>
					</div>
				</div>

				<!-- Risk Distribution -->
				<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
						<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Risk Distribution</h3>
						<PieChart
							data={[
								{ label: 'Low', value: predictionData.risk_distribution.low ?? 0, color: '#22c55e' },
								{ label: 'Medium', value: predictionData.risk_distribution.medium ?? 0, color: '#eab308' },
								{ label: 'High', value: predictionData.risk_distribution.high ?? 0, color: '#f97316' },
								{ label: 'Critical', value: predictionData.risk_distribution.critical ?? 0, color: '#ef4444' }
							]}
							size={200}
						/>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
						<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Top Risk Activities</h3>
						<BarChart
							data={predictionData.activity_risks.slice(0, 8).map(r => ({
								label: r.task_code || r.task_id,
								value: r.risk_score,
								color: r.risk_level === 'critical' ? '#ef4444' : r.risk_level === 'high' ? '#f97316' : r.risk_level === 'medium' ? '#eab308' : '#22c55e'
							}))}
							height={200}
							horizontal={true}
							showValues={true}
							formatValue={(v) => v.toFixed(0)}
						/>
					</div>
				</div>

				<!-- Risk vs Float Scatter -->
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
					<ScatterChart
						title="Risk Score vs Total Float"
						xLabel="Total Float (days)"
						yLabel="Risk Score"
						height={260}
						data={predictionData.activity_risks.map(r => ({
							x: r.float_risk,
							y: r.risk_score,
							label: `${r.task_code}: ${r.task_name}`,
							color: r.risk_level === 'critical' ? '#ef4444' : r.risk_level === 'high' ? '#f97316' : r.risk_level === 'medium' ? '#eab308' : '#22c55e',
							size: r.is_critical_path ? 8 : 5
						}))}
					/>
				</div>

				<!-- Activity Risk Table -->
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg">
					<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
						<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Activity Risk Assessment</h3>
						<span class="text-xs text-gray-500 dark:text-gray-400">{predictionData.methodology}</span>
					</div>
					<div class="overflow-x-auto">
						<table class="min-w-full divide-y divide-gray-200 text-sm">
							<thead class="bg-gray-50 dark:bg-gray-800">
								<tr>
									<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Activity</th>
									<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Risk</th>
									<th class="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Level</th>
									<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Delay</th>
									<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Top Factor</th>
									<th class="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">CP</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-gray-200">
								{#each predictionData.activity_risks as risk}
									<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
										<td class="px-4 py-3">
											<span class="font-mono text-xs text-gray-500 dark:text-gray-400">{risk.task_code}</span>
											<span class="ml-2 text-gray-700 dark:text-gray-300">{risk.task_name}</span>
										</td>
										<td class="px-4 py-3 text-right">
											<div class="flex items-center justify-end gap-2">
												<div class="w-16 bg-gray-200 rounded-full h-1.5">
													<div
														class="h-1.5 rounded-full {risk.risk_level === 'critical' ? 'bg-red-500' : risk.risk_level === 'high' ? 'bg-orange-500' : risk.risk_level === 'medium' ? 'bg-yellow-500' : 'bg-green-500'}"
														style="width: {risk.risk_score}%"
													></div>
												</div>
												<span class="text-xs font-medium w-8 text-right">{risk.risk_score.toFixed(0)}</span>
											</div>
										</td>
										<td class="px-4 py-3 text-center">
											<span class="inline-block px-2 py-0.5 rounded-full text-xs font-medium
												{risk.risk_level === 'critical' ? 'bg-red-100 text-red-800' :
												risk.risk_level === 'high' ? 'bg-orange-100 text-orange-800' :
												risk.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-800' :
												'bg-green-100 text-green-800'}">
												{risk.risk_level}
											</span>
										</td>
										<td class="px-4 py-3 text-right text-xs {risk.predicted_delay_days > 0 ? 'text-red-600 font-medium' : 'text-gray-500 dark:text-gray-400'}">
											{risk.predicted_delay_days > 0 ? `+${risk.predicted_delay_days.toFixed(1)}d` : '-'}
										</td>
										<td class="px-4 py-3 text-xs text-gray-600 dark:text-gray-400">
											{#if risk.top_risk_factors.length > 0}
												<span title={risk.top_risk_factors[0].description}>
													{risk.top_risk_factors[0].description}
												</span>
											{:else}
												-
											{/if}
										</td>
										<td class="px-4 py-3 text-center">
											{#if risk.is_critical_path}
												<span class="text-red-500 font-bold text-xs">CP</span>
											{/if}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>
			{:else}
				<p class="text-gray-500 dark:text-gray-400">Failed to load delay prediction data.</p>
			{/if}
		{/if}

		{:else if activeTab === 'schedule'}
			{#if scheduleViewLoading}
				<div class="animate-pulse space-y-4">
					<div class="h-20 bg-gray-200 rounded"></div>
					<div class="h-64 bg-gray-200 rounded"></div>
				</div>
			{:else if scheduleViewData}
				<ScheduleViewer data={scheduleViewData} />
			{:else}
				<p class="text-gray-500 dark:text-gray-400">Failed to load schedule view.</p>
			{/if}

		{:else if activeTab === 'calendar'}
			{#if calendarLoading}
				<div class="animate-pulse space-y-4">
					<div class="h-20 bg-gray-200 rounded"></div>
					<div class="h-40 bg-gray-200 rounded"></div>
				</div>
			{:else if calendarData}
				<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
					<div class="bg-white dark:bg-gray-900 border-2 rounded-lg p-4 text-center {calendarData.grade === 'A' ? 'border-green-200 text-green-600' : calendarData.grade === 'B' ? 'border-blue-200 text-blue-600' : 'border-amber-200 text-amber-600'}">
						<p class="text-3xl font-bold">{calendarData.grade}</p>
						<p class="text-xs uppercase mt-1">Grade</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-xl font-bold text-gray-900 dark:text-gray-100">{calendarData.score.toFixed(0)}/100</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Score</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-xl font-bold text-blue-600">{calendarData.total_calendars}</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Calendars</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-xl font-bold {calendarData.tasks_without_calendar > 0 ? 'text-red-600' : 'text-green-600'}">{calendarData.tasks_without_calendar}</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Unassigned</p>
					</div>
				</div>
				{#if calendarData.issues.length > 0}
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
						<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Findings ({calendarData.issues.length})</h3>
						{#each calendarData.issues as issue}
							<div class="flex items-start gap-2 py-2 border-b border-gray-100">
								<span class="px-1.5 py-0.5 rounded text-xs font-bold uppercase {issue.severity === 'critical' ? 'bg-red-100 text-red-800' : issue.severity === 'warning' ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'}">{issue.severity}</span>
								<p class="text-sm text-gray-700 dark:text-gray-300">{issue.description}</p>
							</div>
						{/each}
					</div>
				{:else}
					<p class="text-green-600 text-sm font-medium">All calendar definitions are valid.</p>
				{/if}
			{:else}
				<p class="text-gray-500 dark:text-gray-400">Failed to load calendar validation data.</p>
			{/if}

		{:else if activeTab === 'attribution'}
			{#if attributionLoading}
				<div class="animate-pulse space-y-4">
					<div class="h-20 bg-gray-200 rounded"></div>
					<div class="h-40 bg-gray-200 rounded"></div>
				</div>
			{:else if attributionData}
				<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-xl font-bold text-gray-900 dark:text-gray-100">{attributionData.total_delay_days}d</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Total Delay</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-xl font-bold text-blue-600">{attributionData.excusable_days}d</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Excusable</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-xl font-bold text-red-600">{attributionData.non_excusable_days}d</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Non-Excusable</p>
					</div>
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
						<p class="text-xl font-bold text-gray-600 dark:text-gray-400 capitalize">{attributionData.data_source}</p>
						<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">Source</p>
					</div>
				</div>
				{#if attributionData.parties.length > 0}
					<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
						<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Party Breakdown</h3>
						{#each attributionData.parties as party}
							<div class="flex items-center justify-between py-2 border-b border-gray-100">
								<span class="text-sm font-medium text-gray-900 dark:text-gray-100">{party.party}</span>
								<div class="flex items-center gap-3">
									<span class="text-sm font-bold">{party.delay_days}d</span>
									<span class="text-xs text-gray-500 dark:text-gray-400">{party.pct_of_total}%</span>
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<p class="text-green-600 text-sm font-medium">No delay detected.</p>
				{/if}
			{:else}
				<p class="text-gray-500 dark:text-gray-400">Failed to load delay attribution data.</p>
			{/if}
	{/if}
</div>
