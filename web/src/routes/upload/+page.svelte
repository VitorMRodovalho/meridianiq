<script lang="ts">
	import { uploadXER } from '$lib/api';
	import { trackEvent } from '$lib/analytics';
	import { success, error as toastError } from '$lib/toast';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import type { ProjectSummary } from '$lib/types';
	import { t } from '$lib/i18n';

	let dragging = $state(false);
	let loading = $state(false);
	let error = $state('');
	let result: ProjectSummary | null = $state(null);
	let isSandbox = $state(false);

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		dragging = true;
	}

	function handleDragLeave() {
		dragging = false;
	}

	async function handleDrop(e: DragEvent) {
		e.preventDefault();
		dragging = false;
		const file = e.dataTransfer?.files[0];
		if (file) await doUpload(file);
	}

	async function handleFileInput(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (file) await doUpload(file);
	}

	async function doUpload(file: File) {
		const name = file.name.toLowerCase();
		if (!name.endsWith('.xer') && !name.endsWith('.xml')) {
			error = 'Please select a .xer (Primavera P6) or .xml (Microsoft Project) file';
			return;
		}
		loading = true;
		error = '';
		result = null;
		try {
			result = await uploadXER(file, isSandbox);
			// ADR-0015: pending means the async materializer is still running;
			// ready means the sync fast-path completed (InMemoryStore / tests).
			const toastMsg =
				result.status === 'pending'
					? $t('upload.computing_toast')
					: `${$t('upload.success')} — ${result.activity_count} × ${result.relationship_count}`;
			success(toastMsg);
			trackEvent('xer_upload_success', {
				activity_count: result.activity_count,
				relationship_count: result.relationship_count,
				status: result.status,
			});
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Upload failed';
			toastError(error);
			trackEvent('xer_upload_error', { error });
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>{$t('upload.title')} - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-3xl mx-auto">
	<h1 class="text-2xl font-bold text-gray-900 mb-6">{$t('upload.title')}</h1>

	<!-- Drop zone -->
	<div
		role="button"
		tabindex="0"
		class="relative border-2 border-dashed rounded-lg p-12 text-center transition-colors {dragging
			? 'border-blue-400 bg-blue-50'
			: 'border-gray-300 hover:border-gray-400'}"
		ondragover={handleDragOver}
		ondragleave={handleDragLeave}
		ondrop={handleDrop}
		onkeydown={(e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); document.getElementById('xer-file')?.click(); }}}
		aria-label="Drop XER file here or press Enter to browse"
	>
		{#if loading}
			<div class="flex flex-col items-center gap-3">
				<svg class="animate-spin h-10 w-10 text-blue-500" viewBox="0 0 24 24">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
				</svg>
				<p class="text-gray-600">{$t('upload.parsing')}</p>
			</div>
		{:else}
			<svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
			</svg>
			<p class="mt-4 text-gray-600">{$t('upload.drag')}</p>
			<label class="mt-3 inline-block cursor-pointer bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors">
				{$t('upload.browse')}
				<input type="file" accept=".xer,.xml" class="hidden" onchange={handleFileInput} />
			</label>
			<p class="mt-2 text-xs text-gray-400">Primavera P6 (.xer) or Microsoft Project (.xml)</p>
		{/if}
	</div>

	<!-- Sandbox toggle -->
	<label class="mt-4 flex items-center gap-3 cursor-pointer">
		<input type="checkbox" bind:checked={isSandbox} class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
		<div>
			<span class="text-sm font-medium text-gray-700">Sandbox mode</span>
			<p class="text-xs text-gray-400">Hidden from other users and org views. For testing and development only.</p>
		</div>
	</label>

	<!-- Error -->
	{#if error}
		<div class="mt-4 bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
			{error}
		</div>
	{/if}

	<!-- Result -->
	{#if result}
		<div class="mt-6 bg-white border border-gray-200 rounded-lg p-6">
			<div class="flex flex-wrap items-center gap-2 mb-4">
				<svg class="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
					<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
				</svg>
				<h2 class="text-lg font-semibold text-gray-900">{$t('upload.success')}</h2>
				<StatusBadge status={result.status ?? 'pending'} />
			</div>
			{#if result.status === 'pending'}
				<p class="mb-4 text-sm text-sky-700 dark:text-sky-300">
					{$t('upload.computing_toast')}
				</p>
			{/if}

			<dl class="grid grid-cols-2 gap-4 text-sm">
				<div>
					<dt class="text-gray-500 dark:text-gray-400">Project Name</dt>
					<dd class="font-medium text-gray-900 dark:text-gray-100">{result.name || 'Unnamed'}</dd>
				</div>
				<div>
					<dt class="text-gray-500 dark:text-gray-400">Data Date</dt>
					<dd class="font-medium text-gray-900 dark:text-gray-100">{result.data_date?.slice(0, 10) || 'N/A'}</dd>
				</div>
				<div>
					<dt class="text-gray-500 dark:text-gray-400">Activities</dt>
					<dd class="font-medium text-gray-900 dark:text-gray-100">{result.activity_count?.toLocaleString()}</dd>
				</div>
				<div>
					<dt class="text-gray-500 dark:text-gray-400">Relationships</dt>
					<dd class="font-medium text-gray-900 dark:text-gray-100">{result.relationship_count?.toLocaleString()}</dd>
				</div>
				<div>
					<dt class="text-gray-500 dark:text-gray-400">Calendars</dt>
					<dd class="font-medium text-gray-900 dark:text-gray-100">{result.calendar_count}</dd>
				</div>
				<div>
					<dt class="text-gray-500 dark:text-gray-400">WBS Elements</dt>
					<dd class="font-medium text-gray-900 dark:text-gray-100">{result.wbs_count?.toLocaleString()}</dd>
				</div>
			</dl>

			<!-- Metadata tags -->
			{#if result.metadata?.tags?.length}
				<div class="mt-3 flex flex-wrap gap-1.5">
					{#each result.metadata.tags as tag}
						<span class="px-2 py-0.5 rounded-full text-[10px] font-medium
							{tag === 'FINAL' ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' :
							tag === 'DRAFT' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300' :
							tag === 'BASELINE' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300' :
							tag.startsWith('UP#') ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' :
							'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'}">{tag}</span>
					{/each}
				</div>
			{/if}

			<!-- Quick quality indicators -->
			{#if result.metadata}
				<div class="mt-3 flex items-center gap-3 text-[10px]">
					{#if result.metadata.has_baseline_dates}
						<span class="text-green-600 dark:text-green-400 flex items-center gap-1">
							<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
							Baseline dates ({result.metadata.baseline_coverage_pct?.toFixed(0)}%)
						</span>
					{:else}
						<span class="text-amber-600 dark:text-amber-400">No baseline dates</span>
					{/if}
					{#if result.metadata.retained_logic}
						<span class="text-green-600 dark:text-green-400">Retained Logic</span>
					{/if}
					{#if result.metadata.progress_override}
						<span class="text-red-600 dark:text-red-400 font-bold">Progress Override</span>
					{/if}
				</div>
			{/if}

			<div class="flex items-center gap-3 mt-6">
				<a
					href="/projects/{result.project_id}"
					class="inline-block bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors"
				>
					{$t('upload.view')}
				</a>
				<a
					href="/schedule?project={result.project_id}"
					class="inline-block bg-teal-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-teal-700 transition-colors"
				>
					View Schedule
				</a>
				<a
					href="/scorecard?project={result.project_id}"
					class="inline-block bg-gray-100 text-gray-700 px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-200 transition-colors"
				>
					Scorecard
				</a>
			</div>
		</div>
	{/if}
</div>
