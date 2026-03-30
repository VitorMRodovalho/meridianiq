<script lang="ts">
	import { uploadXER } from '$lib/api';
	import { trackEvent } from '$lib/analytics';
	import type { ProjectSummary } from '$lib/types';

	let dragging = $state(false);
	let loading = $state(false);
	let error = $state('');
	let result: ProjectSummary | null = $state(null);

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
			result = await uploadXER(file);
			trackEvent('xer_upload_success', {
				activity_count: result.activity_count,
				relationship_count: result.relationship_count,
			});
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Upload failed';
			trackEvent('xer_upload_error', { error });
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Upload - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-3xl mx-auto">
	<h1 class="text-2xl font-bold text-gray-900 mb-6">Upload XER File</h1>

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
	>
		{#if loading}
			<div class="flex flex-col items-center gap-3">
				<svg class="animate-spin h-10 w-10 text-blue-500" viewBox="0 0 24 24">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
				</svg>
				<p class="text-gray-600">Parsing XER file...</p>
			</div>
		{:else}
			<svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
			</svg>
			<p class="mt-4 text-gray-600">Drag and drop your .xer file here, or</p>
			<label class="mt-3 inline-block cursor-pointer bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors">
				Browse files
				<input type="file" accept=".xer,.xml" class="hidden" onchange={handleFileInput} />
			</label>
			<p class="mt-2 text-xs text-gray-400">Primavera P6 (.xer) or Microsoft Project (.xml)</p>
		{/if}
	</div>

	<!-- Error -->
	{#if error}
		<div class="mt-4 bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
			{error}
		</div>
	{/if}

	<!-- Result -->
	{#if result}
		<div class="mt-6 bg-white border border-gray-200 rounded-lg p-6">
			<div class="flex items-center gap-2 mb-4">
				<svg class="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
					<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
				</svg>
				<h2 class="text-lg font-semibold text-gray-900">Upload Successful</h2>
			</div>

			<dl class="grid grid-cols-2 gap-4 text-sm">
				<div>
					<dt class="text-gray-500">Project Name</dt>
					<dd class="font-medium text-gray-900">{result.name || 'Unnamed'}</dd>
				</div>
				<div>
					<dt class="text-gray-500">Data Date</dt>
					<dd class="font-medium text-gray-900">{result.data_date || 'N/A'}</dd>
				</div>
				<div>
					<dt class="text-gray-500">Activities</dt>
					<dd class="font-medium text-gray-900">{result.activity_count}</dd>
				</div>
				<div>
					<dt class="text-gray-500">Relationships</dt>
					<dd class="font-medium text-gray-900">{result.relationship_count}</dd>
				</div>
				<div>
					<dt class="text-gray-500">Calendars</dt>
					<dd class="font-medium text-gray-900">{result.calendar_count}</dd>
				</div>
				<div>
					<dt class="text-gray-500">WBS Elements</dt>
					<dd class="font-medium text-gray-900">{result.wbs_count}</dd>
				</div>
			</dl>

			<a
				href="/projects/{result.project_id}"
				class="mt-6 inline-block bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors"
			>
				View Project Details
			</a>
		</div>
	{/if}
</div>
