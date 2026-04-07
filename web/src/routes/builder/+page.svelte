<script lang="ts">
	import { generateSchedule } from '$lib/api';
	import type { GeneratedScheduleResponse } from '$lib/types';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';

	let result: GeneratedScheduleResponse | null = $state(null);
	let loading: boolean = $state(false);
	let error: string = $state('');

	let projectType: string = $state('commercial');
	let sizeCategory: string = $state('medium');
	let projectName: string = $state('');
	let targetDuration: number = $state(0);

	async function generate() {
		loading = true;
		error = '';
		result = null;
		try {
			result = await generateSchedule(
				projectType,
				sizeCategory,
				projectName || `${projectType} Project`,
				targetDuration
			);
			toastSuccess(`Generated: ${result.activity_count} activities, ${result.predicted_duration_days}d`);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Generation failed';
			toastError(error);
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Schedule Builder - MeridianIQ</title>
</svelte:head>

<main class="max-w-4xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Schedule Builder</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">Generate schedules from project parameters using ML templates</p>
	</div>

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<div>
				<label for="type" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Project Type</label>
				<select id="type" bind:value={projectType} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm">
					<option value="commercial">Commercial (Office, Retail, Healthcare)</option>
					<option value="industrial">Industrial (Plant, Refinery, Data Center)</option>
					<option value="infrastructure">Infrastructure (Road, Bridge, Tunnel)</option>
					<option value="residential">Residential (Housing, Apartment)</option>
				</select>
			</div>
			<div>
				<label for="size" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Size Category</label>
				<select id="size" bind:value={sizeCategory} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm">
					<option value="small">Small (&lt;100 activities)</option>
					<option value="medium">Medium (100-500 activities)</option>
					<option value="large">Large (500-2000 activities)</option>
					<option value="mega">Mega (&gt;2000 activities)</option>
				</select>
			</div>
			<div>
				<label for="name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Project Name (optional)</label>
				<input id="name" bind:value={projectName} placeholder="My Project" class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
			<div>
				<label for="dur" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Target Duration (days, 0=auto)</label>
				<input id="dur" type="number" min="0" bind:value={targetDuration} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
		</div>
		<div class="mt-4">
			<button onclick={generate} disabled={loading}
				class="px-6 py-2.5 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50">
				{loading ? 'Generating...' : 'Generate Schedule'}
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

	{#if result}
		<div class="grid grid-cols-3 gap-4 mb-6">
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
				<p class="text-3xl font-bold text-gray-900 dark:text-gray-100">{result.activity_count}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase mt-1">Activities</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
				<p class="text-3xl font-bold text-gray-900 dark:text-gray-100">{result.relationship_count}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase mt-1">Relationships</p>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
				<p class="text-3xl font-bold text-blue-600">{result.predicted_duration_days}d</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 uppercase mt-1">Predicted Duration</p>
			</div>
		</div>

		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Generation Summary</h2>
			<dl class="grid grid-cols-2 gap-3 text-sm">
				<div>
					<dt class="text-gray-500 dark:text-gray-400">Type</dt>
					<dd class="font-medium text-gray-900 dark:text-gray-100 capitalize">{result.project_type}</dd>
				</div>
				<div>
					<dt class="text-gray-500 dark:text-gray-400">Size</dt>
					<dd class="font-medium text-gray-900 dark:text-gray-100 capitalize">{result.size_category}</dd>
				</div>
				<div class="col-span-2">
					<dt class="text-gray-500 dark:text-gray-400">Methodology</dt>
					<dd class="text-gray-700 dark:text-gray-300 text-xs">{result.methodology}</dd>
				</div>
			</dl>
		</div>
	{/if}
</main>
