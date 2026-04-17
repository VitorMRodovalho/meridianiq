<script lang="ts">
	import { getProjects } from '$lib/api';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { supabase } from '$lib/supabase';
	import { onMount } from 'svelte';

	let projects: { project_id: string; name: string; tags?: string[] }[] = $state([]);
	let selectedProject = $state('');
	let baselineProject = $state('');
	let data: NarrativeData | null = $state(null);
	let loading = $state(false);
	let error = $state('');

	interface NarrativeSection {
		title: string;
		content: string;
		severity: string;
	}

	interface NarrativeData {
		title: string;
		project_name: string;
		data_date: string;
		generated_at: string;
		executive_summary: string;
		sections: NarrativeSection[];
	}

	onMount(async () => {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
		}
	});

	async function generate() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = session?.access_token
				? { Authorization: `Bearer ${session.access_token}` }
				: {};
			const params = baselineProject ? `?baseline_id=${baselineProject}` : '';
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/narrative${params}`, { headers });
			if (!res.ok) throw new Error(await res.text());
			data = await res.json();
			toastSuccess('Narrative report generated');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}

	function severityColor(s: string): string {
		if (s === 'critical') return 'border-red-500 bg-red-50 dark:bg-red-950';
		if (s === 'warning') return 'border-amber-500 bg-amber-50 dark:bg-amber-950';
		return 'border-blue-200 bg-white dark:bg-gray-900 dark:border-gray-700';
	}

	function severityIcon(s: string): string {
		if (s === 'critical') return 'text-red-600';
		if (s === 'warning') return 'text-amber-600';
		return 'text-blue-600';
	}

	function copyToClipboard() {
		if (!data) return;
		let text = `${data.title}\nData Date: ${data.data_date}\n\n`;
		text += `EXECUTIVE SUMMARY\n${data.executive_summary}\n\n`;
		for (const s of data.sections) {
			text += `${s.title.toUpperCase()}\n${s.content}\n\n`;
		}
		navigator.clipboard.writeText(text);
		toastSuccess('Copied to clipboard');
	}
</script>

<svelte:head>
	<title>Narrative Report | MeridianIQ</title>
</svelte:head>

<main class="max-w-4xl mx-auto px-4 py-8">
	<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-1">Narrative Report</h1>
	<p class="text-sm text-gray-500 dark:text-gray-400 mb-6">Generate structured schedule status narrative for claims and reports (AACE RP 29R-03)</p>

	<!-- Selectors -->
	<div class="flex gap-4 mb-6">
		<div class="flex-1">
			<label for="narrative-schedule" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Schedule</label>
			<select id="narrative-schedule" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 px-3 py-2 text-sm">
				<option value="">Select schedule...</option>
				{#each projects as p}
					<option value={p.project_id}>{p.name || p.project_id}{p.tags?.length ? ` [${p.tags.slice(0, 2).join(', ')}]` : ''}</option>
				{/each}
			</select>
		</div>
		<div class="flex-1">
			<label for="narrative-baseline" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Baseline (optional)</label>
			<select id="narrative-baseline" bind:value={baselineProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 px-3 py-2 text-sm">
				<option value="">None</option>
				{#each projects as p}
					<option value={p.project_id}>{p.name || p.project_id}</option>
				{/each}
			</select>
		</div>
		<div class="flex items-end">
			<button onclick={generate} disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
				{loading ? 'Generating...' : 'Generate'}
			</button>
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm">{error}</div>
	{:else if data}
		<!-- Report header -->
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
			<div class="flex items-center justify-between mb-4">
				<div>
					<h2 class="text-lg font-bold text-gray-900 dark:text-gray-100">{data.title}</h2>
					<p class="text-sm text-gray-500 dark:text-gray-400">Data Date: {data.data_date} | Generated: {new Date(data.generated_at).toLocaleString()}</p>
				</div>
				<button onclick={copyToClipboard} class="text-[10px] px-3 py-1.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 font-medium">
					Copy to Clipboard
				</button>
			</div>

			<!-- Executive Summary -->
			<div class="bg-blue-50 dark:bg-blue-950 border-l-4 border-blue-500 p-4 rounded">
				<h3 class="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-1">Executive Summary</h3>
				<p class="text-sm text-blue-700 dark:text-blue-400 leading-relaxed">{data.executive_summary}</p>
			</div>
		</div>

		<!-- Sections -->
		<div class="space-y-4">
			{#each data.sections as section}
				<div class="border-l-4 rounded-lg p-4 {severityColor(section.severity)}">
					<div class="flex items-center gap-2 mb-2">
						{#if section.severity === 'critical'}
							<svg class="w-4 h-4 {severityIcon(section.severity)}" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
						{:else if section.severity === 'warning'}
							<svg class="w-4 h-4 {severityIcon(section.severity)}" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
						{:else}
							<svg class="w-4 h-4 {severityIcon(section.severity)}" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/></svg>
						{/if}
						<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{section.title}</h3>
						<span class="ml-auto text-[9px] px-2 py-0.5 rounded-full uppercase font-medium
							{section.severity === 'critical' ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' :
							section.severity === 'warning' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300' :
							'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'}">{section.severity}</span>
					</div>
					<p class="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{section.content}</p>
				</div>
			{/each}
		</div>
	{:else}
		<div class="text-center py-12 text-gray-400 dark:text-gray-600">
			<p class="text-lg mb-2">Select a schedule to generate a narrative report</p>
			<p class="text-sm">Optionally select a baseline for comparison narrative</p>
		</div>
	{/if}
</main>
