<script lang="ts">
	import { getProjects, getScorecard } from '$lib/api';
	import type { ScorecardResponse } from '$lib/types';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import GaugeChart from '$lib/components/charts/GaugeChart.svelte';
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import { page } from '$app/stores';

	let projects: { project_id: string; name: string }[] = $state([]);
	let selectedProject: string = $state('');
	let scorecard = $state<ScorecardResponse | null>(null);
	let loading: boolean = $state(false);
	let error: string = $state('');

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e) {
			error = e instanceof Error ? e.message : $t('scorecard.load_failed');
		}
	}

	async function loadScorecard() {
		if (!selectedProject) return;
		loading = true;
		error = '';
		scorecard = null;
		try {
			scorecard = await getScorecard(selectedProject);
			toastSuccess(`${$t('nav.scorecard')}: ${$t('scorecard.toast_grade')} ${scorecard.overall_grade}`);
		} catch (e) {
			error = e instanceof Error ? e.message : $t('scorecard.get_failed');
			toastError(error);
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadProjects();
	});

	// Honour ?project=<id> deep links (quick links on /projects and the header
	// nav on /schedule both emit them), and auto-run once the project list has
	// arrived.
	//
	// Tracks the id it loaded FOR rather than a boolean latch: a plain
	// `autoLoaded` flag never resets, so navigating from ?project=A to
	// ?project=B on this same route left A's grade and gauges on screen under a
	// picker reading B — a silent misattribution of a score to the wrong
	// project, the worst thing this page can do.
	let autoLoadedFor = $state<string | null>(null);

	$effect(() => {
		const projectParam = $page.url.searchParams.get('project');
		if (!projectParam || projects.length === 0 || loading) return;
		if (autoLoadedFor === projectParam) return;
		// Ignore an id the caller cannot actually see: auto-firing on it would
		// error, toast, and leave the <select> visually blank (no matching
		// <option> for bind:value) — a confusing three-way dead end.
		if (!projects.some((p) => p.project_id === projectParam)) return;
		autoLoadedFor = projectParam;
		selectedProject = projectParam;
		loadScorecard();
	});

	// Dark-mode foregrounds are explicit: the 600-weight text on a 950-weight
	// surface measures ~3.3:1 (sRGB-encoded values linearised to relative
	// luminance), which passes WCAG AA only at large text. That was fine while
	// this function was used solely on the 6xl grade block, but the
	// recommendation badge below renders it at 12px bold — normal text, needing
	// 4.5:1. The 300-weight foregrounds clear that on every grade.
	// `D` also had no dark background token at all, and app.css does not remap
	// `bg-orange-50`, so a D badge rendered near-white in dark mode.
	const gradeColor = (grade: string) => {
		const colors: Record<string, string> = {
			A: 'text-green-600 dark:text-green-300 bg-green-50 dark:bg-green-950 border-green-200',
			B: 'text-blue-600 dark:text-blue-300 bg-blue-50 dark:bg-blue-950 border-blue-200',
			C: 'text-yellow-600 dark:text-yellow-300 bg-yellow-50 dark:bg-yellow-950 border-yellow-200',
			D: 'text-orange-600 dark:text-orange-300 bg-orange-50 dark:bg-orange-950 border-orange-200',
			F: 'text-red-600 dark:text-red-300 bg-red-50 dark:bg-red-950 border-red-200',
		};
		return colors[grade] || 'text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700';
	};

	const gaugeBands = [
		{ threshold: 60, color: '#ef4444' },
		{ threshold: 70, color: '#f59e0b' },
		{ threshold: 80, color: '#3b82f6' },
		{ threshold: 90, color: '#10b981' },
		{ threshold: 100, color: '#059669' },
	];

	// The engine prefixes each recommendation with the dimension grade
	// (`"[F] Validation: ..."` — see _generate_recommendations in
	// src/analytics/scorecard.py). Split it out so the grade renders as a
	// badge instead of leaking raw brackets into the sentence. The API
	// contract stays a plain list[str]; this is presentation only.
	const parsedRecommendations = $derived(
		(scorecard?.recommendations ?? []).map((rec) => {
			const match = /^\[([A-F])\]\s*(.+)$/.exec(rec);
			return match ? { grade: match[1], text: match[2] } : { grade: null, text: rec };
		})
	);
</script>

<svelte:head>
	<title>{$t('page.scorecard')} - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.scorecard')}</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">{$t('scorecard.subtitle')}</p>
	</div>

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<div class="flex items-end gap-4">
			<div class="flex-1">
				<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('scorecard.field_project')}</label>
				<select
					id="project"
					bind:value={selectedProject}
					class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm"
				>
					<option value="">{$t('scorecard.select_project')}</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name || p.project_id}</option>
					{/each}
				</select>
			</div>
			<button
				onclick={loadScorecard}
				disabled={!selectedProject || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
			>
				{loading ? $t('scorecard.btn_loading') : $t('scorecard.btn_get')}
			</button>
			{#if selectedProject}
				<a href="/schedule?project={selectedProject}" class="px-3 py-2 text-xs text-teal-600 hover:text-teal-800 font-medium">{$t('scorecard.view_schedule')}</a>
			{/if}
		</div>
	</div>

	{#if loading}
		<AnalysisSkeleton cards={4} />
	{:else if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 mb-6">
			<p class="text-red-700 text-sm">{error}</p>
		</div>
	{/if}

	{#if scorecard}
		<!-- Overall Grade -->
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6 text-center">
			<div class="inline-flex items-center gap-4">
				<div class={`text-6xl font-black border-4 rounded-xl px-5 py-2 ${gradeColor(scorecard.overall_grade)}`}>
					{scorecard.overall_grade}
				</div>
				<div class="text-left">
					<p class="text-3xl font-bold text-gray-900 dark:text-gray-100">{scorecard.overall_score.toFixed(1)}</p>
					<p class="text-gray-500 dark:text-gray-400 text-sm">{$t('scorecard.overall_score')}</p>
				</div>
			</div>
			<p class="text-gray-500 dark:text-gray-400 text-xs mt-3">{scorecard.methodology}</p>
		</div>

		<!-- Dimension Gauges -->
		<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
			{#each scorecard.dimensions as dim}
				<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-center">
					<GaugeChart value={dim.score} title={dim.name} label={dim.grade} size={140} bands={gaugeBands} />
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-2">{dim.description}</p>
				</div>
			{/each}
		</div>

		<!-- Recommendations -->
		{#if scorecard.recommendations.length > 0}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">{$t('scorecard.recommendations_title')}</h2>
				<ul class="space-y-2">
					{#each parsedRecommendations as rec}
						<li class="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
							<svg class="w-5 h-5 text-blue-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
							{#if rec.grade}
								<span class="shrink-0 px-1.5 py-0.5 rounded border text-xs font-bold {gradeColor(rec.grade)}" aria-label="{$t('common.grade')} {rec.grade}">{rec.grade}</span>
							{/if}
							<span>{rec.text}</span>
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	{/if}
</main>
