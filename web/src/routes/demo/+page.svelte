<script lang="ts">
	import { onMount } from 'svelte';

	let data: any = $state(null);
	let loading = $state(true);
	let error = $state('');

	const BASE = import.meta.env.VITE_API_URL || '';

	onMount(async () => {
		try {
			const res = await fetch(`${BASE}/api/v1/demo/project`);
			if (!res.ok) throw new Error(await res.text());
			data = await res.json();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load demo';
		} finally {
			loading = false;
		}
	});

	function scoreColor(score: number): string {
		if (score >= 80) return 'text-green-600';
		if (score >= 60) return 'text-yellow-600';
		return 'text-red-600';
	}
</script>

<svelte:head>
	<title>Demo - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<div class="mb-6 flex items-center justify-between">
		<div>
			<div class="flex items-center gap-3 mb-2">
				<span class="px-2.5 py-0.5 text-xs font-semibold bg-blue-100 text-blue-700 rounded-full">DEMO</span>
				<a href="/" class="text-sm text-blue-600 hover:underline">Back to home</a>
			</div>
			<h1 class="text-2xl font-bold text-gray-900">Sample Schedule Analysis</h1>
			<p class="text-sm text-gray-500 mt-1">This is a synthetic schedule demonstrating MeridianIQ's analysis capabilities.</p>
		</div>
		<a
			href="/login"
			class="px-6 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-colors"
		>
			Sign in to analyze your own
		</a>
	</div>

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500 py-12 justify-center">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			Analyzing demo schedule...
		</div>
	{:else if error}
		<div class="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
	{:else if data}
		<!-- Project Overview -->
		<div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-gray-900">{data.project.activity_count}</p>
				<p class="text-xs text-gray-500 mt-1">Activities</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-gray-900">{data.project.relationship_count}</p>
				<p class="text-xs text-gray-500 mt-1">Relationships</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-gray-900">{data.project.calendar_count}</p>
				<p class="text-xs text-gray-500 mt-1">Calendars</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-gray-900">{data.project.wbs_count}</p>
				<p class="text-xs text-gray-500 mt-1">WBS Elements</p>
			</div>
		</div>

		<!-- DCMA 14-Point Assessment -->
		<div class="bg-white border border-gray-200 rounded-lg p-6 mb-8">
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-lg font-semibold text-gray-900">DCMA 14-Point Assessment</h2>
				<div class="text-right">
					<p class="text-3xl font-bold {scoreColor(data.validation.overall_score)}">{data.validation.overall_score.toFixed(0)}<span class="text-sm text-gray-400">/100</span></p>
					<p class="text-xs text-gray-500">{data.validation.passed_count} passed / {data.validation.failed_count} failed</p>
				</div>
			</div>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
				{#each data.validation.metrics as m}
					<div class="rounded-lg border p-3 {m.passed ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}">
						<div class="flex items-center justify-between mb-1">
							<span class="text-xs text-gray-500">#{m.number}</span>
							<span class="text-xs font-bold px-1.5 py-0.5 rounded-full {m.passed ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'}">
								{m.passed ? 'PASS' : 'FAIL'}
							</span>
						</div>
						<p class="text-sm font-medium text-gray-900">{m.name}</p>
						<p class="text-xl font-bold mt-1 {m.passed ? 'text-green-700' : 'text-red-700'}">{m.value}{m.unit}</p>
						<p class="text-xs text-gray-500">{m.direction === 'min' ? '<=' : '>='} {m.threshold}{m.unit}</p>
					</div>
				{/each}
			</div>
		</div>

		<!-- Critical Path -->
		<div class="bg-white border border-gray-200 rounded-lg p-6 mb-8">
			<h2 class="text-lg font-semibold text-gray-900 mb-4">Critical Path ({data.critical_path.length} activities)</h2>
			<div class="overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200 text-sm">
					<thead class="bg-gray-50">
						<tr>
							<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Code</th>
							<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
							<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Total Float (days)</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each data.critical_path.activities as a}
							<tr class="hover:bg-gray-50">
								<td class="px-4 py-2 font-mono text-gray-600">{a.task_code}</td>
								<td class="px-4 py-2 text-gray-900">{a.task_name}</td>
								<td class="px-4 py-2 text-right font-medium {a.total_float <= 0 ? 'text-red-600' : 'text-gray-600'}">{a.total_float}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>

		<!-- CTA -->
		<div class="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-lg p-8 text-center text-white">
			<h2 class="text-2xl font-bold mb-2">Ready to analyze your own schedules?</h2>
			<p class="text-blue-100 mb-6">Upload your Primavera P6 XER files and unlock all 10 analysis engines.</p>
			<a
				href="/login"
				class="inline-block px-8 py-3 bg-white text-blue-700 font-semibold rounded-lg hover:bg-blue-50 transition-colors"
			>
				Get started free
			</a>
		</div>
	{/if}
</div>
