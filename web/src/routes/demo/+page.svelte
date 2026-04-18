<script lang="ts">
	import { onMount } from 'svelte';
	import type { DemoProjectResponse } from '$lib/api';
	import { t } from '$lib/i18n';

	let data: DemoProjectResponse | null = $state(null);
	let loading = $state(true);
	let error = $state('');

	const BASE = import.meta.env.VITE_API_URL || '';

	onMount(async () => {
		try {
			const res = await fetch(`${BASE}/api/v1/demo/project`);
			if (!res.ok) throw new Error(await res.text());
			data = await res.json();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : $t('demo.load_failed');
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
	<title>{$t('demo.badge')} - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<div class="mb-6 flex items-center justify-between">
		<div>
			<div class="flex items-center gap-3 mb-2">
				<span class="px-2.5 py-0.5 text-xs font-semibold bg-blue-100 text-blue-700 rounded-full">{$t('demo.badge')}</span>
				<a href="/" class="text-sm text-blue-600 hover:underline">{$t('demo.back_home')}</a>
			</div>
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('demo.title')}</h1>
			<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{$t('demo.subtitle')}</p>
		</div>
		<a
			href="/login"
			class="px-6 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-colors"
		>
			{$t('demo.cta_signin')}
		</a>
	</div>

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400 py-12 justify-center">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			{$t('demo.loading')}
		</div>
	{:else if error}
		<div class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
	{:else if data}
		<!-- Project Overview -->
		<div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{data.project.activity_count}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('common.activities')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{data.project.relationship_count}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('common.relationships')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{data.project.calendar_count}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('demo.stat_calendars')}</p>
			</div>
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{data.project.wbs_count}</p>
				<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t('demo.stat_wbs')}</p>
			</div>
		</div>

		<!-- DCMA 14-Point Assessment -->
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-8">
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{$t('demo.dcma_title')}</h2>
				<div class="text-right">
					<p class="text-3xl font-bold {scoreColor(data.validation.overall_score)}">{data.validation.overall_score.toFixed(0)}<span class="text-sm text-gray-400">/100</span></p>
					<p class="text-xs text-gray-500 dark:text-gray-400">{data.validation.passed_count} {$t('demo.pass_suffix')} / {data.validation.failed_count} {$t('demo.fail_suffix')}</p>
				</div>
			</div>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
				{#each data.validation.metrics as m}
					<div class="rounded-lg border p-3 {m.passed ? 'bg-green-50 dark:bg-green-950 border-green-200' : 'bg-red-50 dark:bg-red-950 border-red-200'}">
						<div class="flex items-center justify-between mb-1">
							<span class="text-xs text-gray-500 dark:text-gray-400">#{m.number}</span>
							<span class="text-xs font-bold px-1.5 py-0.5 rounded-full {m.passed ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'}">
								{m.passed ? $t('common.pass') : $t('common.fail')}
							</span>
						</div>
						<p class="text-sm font-medium text-gray-900 dark:text-gray-100">{m.name}</p>
						<p class="text-xl font-bold mt-1 {m.passed ? 'text-green-700' : 'text-red-700'}">{m.value}{m.unit}</p>
						<p class="text-xs text-gray-500 dark:text-gray-400">{m.direction === 'min' ? '<=' : '>='} {m.threshold}{m.unit}</p>
					</div>
				{/each}
			</div>
		</div>

		<!-- Critical Path -->
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-8">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{$t('demo.cp_title')} ({data.critical_path.length} {$t('demo.activities_suffix')})</h2>
			<div class="overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200 text-sm">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('demo.col_code')}</th>
							<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('demo.col_name')}</th>
							<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('demo.col_tf')}</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each data.critical_path.activities as a}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
								<td class="px-4 py-2 font-mono text-gray-600 dark:text-gray-400">{a.task_code}</td>
								<td class="px-4 py-2 text-gray-900 dark:text-gray-100">{a.task_name}</td>
								<td class="px-4 py-2 text-right font-medium {a.total_float <= 0 ? 'text-red-600' : 'text-gray-600 dark:text-gray-400'}">{a.total_float}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>

		<!-- CTA -->
		<div class="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-lg p-8 text-center text-white">
			<h2 class="text-2xl font-bold mb-2">{$t('demo.cta_title')}</h2>
			<p class="text-blue-100 mb-6">{$t('demo.cta_hint')}</p>
			<a
				href="/login"
				class="inline-block px-8 py-3 bg-white dark:bg-gray-900 text-blue-700 font-semibold rounded-lg hover:bg-blue-50 dark:bg-blue-950 transition-colors"
			>
				{$t('demo.cta_get_started')}
			</a>
		</div>
	{/if}
</div>
