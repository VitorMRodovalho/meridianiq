<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { supabase } from '$lib/supabase';
	import { t } from '$lib/i18n';
	import GaugeChart from '$lib/components/charts/GaugeChart.svelte';
	import PieChart from '$lib/components/charts/PieChart.svelte';
	import BarChart from '$lib/components/charts/BarChart.svelte';

	interface CalendarIssue {
		calendar_id: string;
		calendar_name: string;
		check: string;
		severity: string;
		description: string;
		affected_tasks: number;
	}

	interface CalendarDetail {
		calendar_id: string;
		name: string;
		day_hr_cnt: number;
		week_hr_cnt: number;
		calendar_type: string;
		is_default: boolean;
		task_count: number;
		pct_of_tasks: number;
		working_days_per_week: number;
		issues: string[];
	}

	interface ValidationResult {
		calendars: CalendarDetail[];
		issues: CalendarIssue[];
		score: number;
		grade: string;
		total_calendars: number;
		total_tasks: number;
		tasks_with_calendar: number;
		tasks_without_calendar: number;
		has_default: boolean;
		dominant_calendar: string;
		dominant_pct: number;
		methodology: string;
	}

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let result = $state<ValidationResult | null>(null);
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

	async function validate() {
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
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/calendar-validation`, { headers });
			if (!res.ok) throw new Error(await res.text());
			result = await res.json();
			toastSuccess(`Calendar health: ${result!.grade} (${result!.score.toFixed(0)}/100)`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => { loadProjects(); });

	const gradeColor = (grade: string) => {
		if (grade === 'A') return 'text-green-600 bg-green-50 border-green-200';
		if (grade === 'B') return 'text-blue-600 bg-blue-50 border-blue-200';
		if (grade === 'C') return 'text-amber-600 bg-amber-50 border-amber-200';
		if (grade === 'D') return 'text-orange-600 bg-orange-50 border-orange-200';
		return 'text-red-600 bg-red-50 border-red-200';
	};

	const severityBadge = (sev: string) => {
		if (sev === 'critical') return 'bg-red-100 text-red-800';
		if (sev === 'warning') return 'bg-amber-100 text-amber-800';
		return 'bg-blue-100 text-blue-800';
	};

	const coveragePct = $derived(
		result && result.total_tasks > 0
			? Math.round((result.tasks_with_calendar / result.total_tasks) * 100)
			: 0
	);

	const calDistribution = $derived(
		result ? result.calendars.filter(c => c.task_count > 0).map(c => ({
			label: c.name,
			value: c.task_count,
		})) : []
	);

	const hoursData = $derived(
		result ? result.calendars.map(c => ({
			label: c.name.length > 20 ? c.name.slice(0, 18) + '...' : c.name,
			value: c.week_hr_cnt,
		})) : []
	);

	const criticalCount = $derived(result ? result.issues.filter(i => i.severity === 'critical').length : 0);
	const warningCount = $derived(result ? result.issues.filter(i => i.severity === 'warning').length : 0);
</script>

<svelte:head>
	<title>{$t('page.calendar')} - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900">{$t('page.calendar')}</h1>
		<p class="text-gray-500 mt-1">Work calendar integrity and compliance (DCMA Check #13, AACE RP 49R-06)</p>
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
			<button onclick={validate} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Validating...' : 'Validate Calendars'}
			</button>
		</div>
	</div>

	{#if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
			<p class="text-red-700 text-sm">{error}</p>
		</div>
	{/if}

	{#if result}
		<!-- Grade + Summary Cards -->
		<div class="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
			<div class="bg-white rounded-lg border-2 p-4 text-center {gradeColor(result.grade)}">
				<p class="text-4xl font-bold">{result.grade}</p>
				<p class="text-xs uppercase mt-1">Grade</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-gray-900">{result.score.toFixed(0)}</p>
				<p class="text-xs text-gray-500 uppercase">Score</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-blue-600">{result.total_calendars}</p>
				<p class="text-xs text-gray-500 uppercase">Calendars</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold {coveragePct >= 95 ? 'text-green-600' : coveragePct >= 80 ? 'text-amber-600' : 'text-red-600'}">{coveragePct}%</p>
				<p class="text-xs text-gray-500 uppercase">Coverage</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-red-600">{criticalCount}</p>
				<p class="text-xs text-gray-500 uppercase">Critical</p>
			</div>
			<div class="bg-white rounded-lg border border-gray-200 p-3 text-center">
				<p class="text-lg font-bold text-amber-600">{warningCount}</p>
				<p class="text-xs text-gray-500 uppercase">Warnings</p>
			</div>
		</div>

		<!-- Charts -->
		<div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
			<div class="bg-white rounded-lg border border-gray-200 p-6">
				<GaugeChart value={result.score} max={100} label="Calendar Health" />
			</div>
			{#if calDistribution.length > 0}
				<PieChart data={calDistribution} title="Task Distribution by Calendar" size={160} />
			{/if}
			{#if hoursData.length > 0}
				<BarChart data={hoursData} title="Weekly Hours per Calendar" />
			{/if}
		</div>

		<!-- Issues -->
		{#if result.issues.length > 0}
			<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">Findings ({result.issues.length})</h2>
				<div class="space-y-3">
					{#each result.issues as issue}
						<div class="flex items-start gap-3 p-3 rounded-lg {issue.severity === 'critical' ? 'bg-red-50' : issue.severity === 'warning' ? 'bg-amber-50' : 'bg-blue-50'}">
							<span class="px-2 py-0.5 rounded text-xs font-bold uppercase shrink-0 mt-0.5 {severityBadge(issue.severity)}">
								{issue.severity}
							</span>
							<div class="flex-1 min-w-0">
								<p class="text-sm text-gray-900">{issue.description}</p>
								{#if issue.affected_tasks > 0}
									<p class="text-xs text-gray-500 mt-1">{issue.affected_tasks} task{issue.affected_tasks !== 1 ? 's' : ''} affected</p>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			</div>
		{:else}
			<div class="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
				<p class="text-green-700 text-sm font-medium">No issues found. All calendar definitions are valid and consistent.</p>
			</div>
		{/if}

		<!-- Calendar Detail Table -->
		<div class="bg-white rounded-lg border border-gray-200 p-6">
			<h2 class="text-lg font-semibold text-gray-900 mb-3">Calendar Details ({result.calendars.length})</h2>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-200">
							<th class="text-left py-2 px-3">Calendar</th>
							<th class="text-center py-2 px-3">Default</th>
							<th class="text-right py-2 px-3">Hrs/Day</th>
							<th class="text-right py-2 px-3">Hrs/Week</th>
							<th class="text-right py-2 px-3">Days/Week</th>
							<th class="text-right py-2 px-3">Tasks</th>
							<th class="text-right py-2 px-3">% Tasks</th>
							<th class="text-left py-2 px-3">Status</th>
						</tr>
					</thead>
					<tbody>
						{#each result.calendars as cal}
							<tr class="border-b border-gray-100 hover:bg-gray-50">
								<td class="py-2 px-3">
									<p class="font-medium text-gray-900">{cal.name}</p>
									<p class="text-xs text-gray-400 font-mono">{cal.calendar_id}</p>
								</td>
								<td class="py-2 px-3 text-center">
									{#if cal.is_default}
										<span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-green-100 text-green-700 text-xs font-bold">&#10003;</span>
									{:else}
										<span class="text-gray-300">—</span>
									{/if}
								</td>
								<td class="py-2 px-3 text-right font-mono">{cal.day_hr_cnt}</td>
								<td class="py-2 px-3 text-right font-mono">{cal.week_hr_cnt}</td>
								<td class="py-2 px-3 text-right font-mono">{cal.working_days_per_week}</td>
								<td class="py-2 px-3 text-right font-bold">{cal.task_count}</td>
								<td class="py-2 px-3 text-right">
									<div class="flex items-center justify-end gap-2">
										<div class="w-16 h-1.5 rounded-full bg-gray-100 overflow-hidden">
											<div class="h-full rounded-full bg-blue-500" style="width: {cal.pct_of_tasks}%"></div>
										</div>
										<span class="text-xs text-gray-500 w-10 text-right">{cal.pct_of_tasks}%</span>
									</div>
								</td>
								<td class="py-2 px-3">
									{#if cal.issues.length > 0}
										{#each cal.issues as iss}
											<span class="inline-block px-1.5 py-0.5 rounded text-xs bg-amber-100 text-amber-800 mr-1 mb-1">{iss}</span>
										{/each}
									{:else}
										<span class="text-xs text-green-600">OK</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			{#if result.tasks_without_calendar > 0}
				<div class="mt-4 p-3 bg-red-50 rounded-lg">
					<p class="text-sm text-red-700">
						<strong>{result.tasks_without_calendar}</strong> of {result.total_tasks} tasks have no valid calendar assignment.
						Float and duration calculations for these tasks are unreliable.
					</p>
				</div>
			{/if}

			<p class="text-xs text-gray-400 mt-4">{result.methodology}</p>
		</div>
	{/if}
</main>
