<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { supabase } from '$lib/supabase';

	interface ReportDescriptor {
		report_type: string;
		name: string;
		description: string;
		ready: boolean;
		reason: string;
	}

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let reports: ReportDescriptor[] = $state([]);
	let loading: boolean = $state(false);
	let downloading: string = $state('');
	let error: string = $state('');

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
		}
	}

	async function loadReports() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		reports = [];
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = session?.access_token
				? { Authorization: `Bearer ${session.access_token}` }
				: {};
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/available-reports`, { headers });
			if (!res.ok) throw new Error(await res.text());
			const data = await res.json();
			reports = data.reports || [];
			toastSuccess(`${reports.filter(r => r.ready).length} of ${reports.length} reports available`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	async function downloadReport(reportType: string) {
		downloading = reportType;
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = session?.access_token
				? { Authorization: `Bearer ${session.access_token}` }
				: {};
			const res = await fetch(`${BASE}/api/v1/reports/${selectedProject}/${reportType}/download`, { headers });
			if (!res.ok) throw new Error(await res.text());
			const blob = await res.blob();
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `${reportType}-report.pdf`;
			a.click();
			URL.revokeObjectURL(url);
			toastSuccess(`Downloaded ${reportType} report`);
		} catch (e) {
			toastError(e instanceof Error ? e.message : 'Download failed');
		} finally {
			downloading = '';
		}
	}

	$effect(() => { loadProjects(); });

	const readyCount = $derived(reports.filter(r => r.ready).length);

	const reportIcon = (type: string) => {
		const icons: Record<string, string> = {
			validation: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
			baseline: 'M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
			forensic: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
			evm: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6',
			monthly: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
			risk: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z',
			executive: 'M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9.5a2 2 0 00-2-2h-2',
		};
		return icons[type] || 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z';
	};
</script>

<svelte:head>
	<title>{$t('page.reports')} - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.reports')}</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">{$t('reports.subtitle')}</p>
	</div>

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<div class="flex items-end gap-4">
			<div class="flex-1">
				<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('common.project')}</label>
				<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm">
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<button onclick={loadReports} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? $t('common.loading') : $t('reports.check_button')}
			</button>
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 mb-6">
			<p class="text-red-700 text-sm">{error}</p>
		</div>
	{/if}

	{#if reports.length > 0}
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-6">
			<p class="text-sm text-gray-600 dark:text-gray-400">{readyCount} of {reports.length} reports ready for download</p>
		</div>

		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
			{#each reports as report}
				<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-5 flex flex-col">
					<div class="flex items-start gap-3 mb-3">
						<div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 {report.ready ? 'bg-blue-100' : 'bg-gray-100 dark:bg-gray-800'}">
							<svg class="w-5 h-5 {report.ready ? 'text-blue-600' : 'text-gray-400'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={reportIcon(report.report_type)} />
							</svg>
						</div>
						<div class="min-w-0">
							<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{report.name}</h3>
							<p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{report.description}</p>
						</div>
					</div>
					{#if report.ready}
						<button
							onclick={() => downloadReport(report.report_type)}
							disabled={downloading === report.report_type}
							class="mt-auto w-full px-3 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
						>
							{#if downloading === report.report_type}
								<svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
									<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
									<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
								</svg>
								{$t('reports.downloading')}
							{:else}
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
								</svg>
								{$t('reports.download_pdf')}
							{/if}
						</button>
					{:else}
						<div class="mt-auto px-3 py-2 bg-gray-50 dark:bg-gray-800 rounded-md text-xs text-gray-500 dark:text-gray-400 text-center">
							{report.reason}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</main>
