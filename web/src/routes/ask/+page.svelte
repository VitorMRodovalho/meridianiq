<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { getProjects, getAiStatus, askSchedule, ApiError, type AiStatus } from '$lib/api';
	import type { ProjectListItem } from '$lib/types';
	import { supabase } from '$lib/supabase';
	import { t, locale, dateLocale } from '$lib/i18n';
	import { formatNumber } from '$lib/i18n/format';
	import {
		gateView,
		classifyAskError,
		gateMessage,
		remainingMessage,
		interpolate
	} from '$lib/aiGate';

	interface QA {
		question: string;
		answer: string;
		model?: string;
		tokens_used?: number;
	}

	/** Same bound as the API's `question` field. */
	const MAX_QUESTION_LENGTH = 1000;

	const NO_STATUS: AiStatus = {
		available: false,
		reason: null,
		daily_limit: null,
		used_today: null,
		remaining_today: null,
		resets_at: null
	};

	const suggestionKeys = [
		'ask.suggestion_critical_path',
		'ask.suggestion_negative_float',
		'ask.suggestion_delayed_milestones',
		'ask.suggestion_health',
		'ask.suggestion_wbs_risk'
	];

	// checking → signed_out | ready. The composer never renders before the
	// status has answered, so nobody sees an input the gate then takes away.
	let phase: 'checking' | 'signed_out' | 'ready' = $state('checking');
	// Null when the status could not be loaded: gateView() treats that as closed.
	let status = $state<AiStatus | null>(null);
	let projects: ProjectListItem[] = $state([]);
	let projectsFailed = $state(false);
	let selectedProject = $state('');
	let question = $state('');
	let history: QA[] = $state([]);
	let loading = $state(false);
	// i18n key of the outcome of a send that is not a gate state, shown in a role="alert".
	let sendErrorKey = $state('');
	let inputEl: HTMLInputElement | undefined = $state();
	let gateMessageEl: HTMLDivElement | undefined = $state();

	const view = $derived(gateView(status));
	const gateText = $derived(gateMessage($t, view, status?.resets_at, dateLocale($locale)));
	const remainingText = $derived(
		view.mode === 'available'
			? remainingMessage($t, status?.remaining_today, status?.daily_limit)
			: ''
	);
	const canCompose = $derived(view.mode === 'available' && !!selectedProject && !loading);

	function isUnauthorized(e: unknown): boolean {
		return e instanceof ApiError && e.status === 401;
	}

	onMount(async () => {
		let signedIn = false;
		try {
			const {
				data: { session }
			} = await supabase.auth.getSession();
			signedIn = !!session;
		} catch {
			signedIn = false;
		}
		if (!signedIn) {
			phase = 'signed_out';
			return;
		}
		// Status and projects load together so the page settles once.
		const [statusResult, projectsResult] = await Promise.allSettled([
			getAiStatus(),
			getProjects()
		]);
		if (statusResult.status === 'fulfilled') {
			status = statusResult.value;
		} else if (isUnauthorized(statusResult.reason)) {
			phase = 'signed_out';
			return;
		}
		if (projectsResult.status === 'fulfilled') projects = projectsResult.value.projects;
		else projectsFailed = true;
		phase = 'ready';
	});

	/** Reload the status. On failure the page closes (fail-closed) until the next load. */
	async function reloadStatus(): Promise<void> {
		try {
			status = await getAiStatus();
		} catch (e: unknown) {
			if (isUnauthorized(e)) {
				phase = 'signed_out';
				return;
			}
			status = null;
		}
	}

	async function askQuestion(): Promise<void> {
		// Checked here and not only on the controls: Enter, a stale button or a
		// suggestion must never send while the status says no.
		if (view.mode !== 'available' || loading) return;
		const q = question.trim();
		if (!selectedProject || !q || q.length > MAX_QUESTION_LENGTH) return;

		loading = true;
		sendErrorKey = '';
		question = '';
		let gateChanged = false;
		try {
			const res = await askSchedule(selectedProject, q);
			history = [
				...history,
				{ question: q, answer: res.answer, model: res.model, tokens_used: res.tokens_used }
			];
		} catch (e: unknown) {
			question = q;
			const failure = classifyAskError(e);
			if (failure.kind === 'signin') {
				phase = 'signed_out';
				return;
			}
			if (failure.kind === 'gate') {
				// Apply the refusal now; the reload below fills in the rest (reset time).
				status = { ...(status ?? NO_STATUS), available: false, reason: failure.view.reason };
				gateChanged = true;
			} else {
				sendErrorKey = failure.key;
			}
		} finally {
			loading = false;
		}

		await tick();
		if (gateChanged) gateMessageEl?.focus();
		else inputEl?.focus();

		// After every ask: the count moved, and a call that timed out may still
		// have been counted by the server.
		const wasAvailable = view.mode === 'available';
		await reloadStatus();
		if (phase === 'ready' && wasAvailable && view.mode !== 'available') {
			await tick();
			gateMessageEl?.focus();
		}
	}

	/** A suggestion fills the input; the user still decides to send. */
	function useSuggestion(key: string) {
		question = $t(key);
		inputEl?.focus();
	}

	function projectLabel(p: ProjectListItem): string {
		const name = p.name || p.project_id;
		if (typeof p.activity_count !== 'number') return name;
		const count = formatNumber(p.activity_count, $locale, { maximumFractionDigits: 0 });
		return `${name} (${interpolate($t('ask.activity_count'), { count })})`;
	}

	function answerMeta(qa: QA): string {
		const parts: string[] = [];
		if (qa.model) parts.push(qa.model);
		if (typeof qa.tokens_used === 'number' && qa.tokens_used > 0) {
			const count = formatNumber(qa.tokens_used, $locale, { maximumFractionDigits: 0 });
			parts.push(interpolate($t('ask.tokens_used'), { count }));
		}
		return parts.join(' · ');
	}
</script>

<svelte:head>
	<title>{$t('page.ask')} | MeridianIQ</title>
</svelte:head>

<div class="max-w-4xl mx-auto px-4 py-8">
	<div class="mb-6">
		<div class="flex flex-wrap items-center gap-2">
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.ask')}</h1>
			<span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-200">
				{$t('common.beta')}
			</span>
		</div>
		<p class="text-gray-500 dark:text-gray-400 mt-1">{$t('ask.subtitle')}</p>
		<!-- Always mounted so every change of the count is announced. -->
		<p role="status" class="mt-2 min-h-5 text-sm font-medium text-gray-700 dark:text-gray-300">{remainingText}</p>
	</div>

	{#if phase === 'checking'}
		<!-- Neutral while the status loads: no composer flash before the gate decides. -->
		<div role="status" class="flex items-center justify-center py-16 text-gray-400 dark:text-gray-500">
			<svg class="animate-spin h-6 w-6" viewBox="0 0 24 24" aria-hidden="true">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			<span class="sr-only">{$t('common.loading')}</span>
		</div>
	{:else if phase === 'signed_out'}
		<div class="border border-gray-200 dark:border-gray-700 rounded-lg p-10 text-center bg-white dark:bg-gray-900">
			<svg class="mx-auto h-12 w-12 text-blue-500 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
			</svg>
			<h2 class="mt-4 text-lg font-semibold text-gray-900 dark:text-gray-100">{$t('ask.signin_title')}</h2>			<p class="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">{$t('ask.signin_body')}</p>
			<a
				href="/login"
				class="mt-6 inline-block bg-blue-600 text-white px-6 py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors"
			>
				{$t('common.sign_in')}
			</a>
		</div>
	{:else}
		{#if view.mode === 'closed'}
			<!-- A designed state, not an error: what the feature is, how it is
				 enabled (administrators' approval during the beta, a paid plan
				 later), and where to go next, so the journey does not end here.
				 Also the focus target when a send ends in a closed state. -->
			<div
				id="ask-gate-message"
				bind:this={gateMessageEl}
				tabindex="-1"
				class="mb-6 rounded-lg border border-violet-200 dark:border-violet-800 bg-violet-50 dark:bg-violet-950 p-8 text-center focus:outline-none focus:ring-2 focus:ring-violet-500"
			>
				<svg class="mx-auto h-10 w-10 text-violet-600 dark:text-violet-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
				</svg>
				<h2 class="mt-4 text-lg font-semibold text-violet-950 dark:text-violet-50">{$t(view.titleKey ?? 'ask.unavailable_title')}</h2>
				<p class="mt-2 text-sm text-violet-900 dark:text-violet-100 max-w-xl mx-auto">{gateText}</p>
				<p class="mt-3 text-sm text-violet-800 dark:text-violet-200 max-w-xl mx-auto">{$t('ask.rest_available')}</p>
				<div class="mt-6 flex flex-wrap justify-center gap-3">
					<a
						href="/projects"
						class="inline-block bg-blue-600 text-white px-5 py-2 rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors"
					>{$t('ask.go_projects')}</a>
					<a
						href="/upload"
						class="inline-block border border-violet-300 dark:border-violet-700 text-violet-900 dark:text-violet-100 px-5 py-2 rounded-lg text-sm font-semibold hover:bg-violet-100 dark:hover:bg-violet-900 transition-colors"
					>{$t('ask.go_upload')}</a>
				</div>
			</div>
		{:else if view.mode === 'exhausted'}
			<!-- Focus target when a send ends in a quota state; the disabled input points here. -->
			<div
				id="ask-gate-message"
				bind:this={gateMessageEl}
				tabindex="-1"
				class="mb-6 flex items-start gap-3 rounded-lg border border-violet-200 dark:border-violet-800 bg-violet-50 dark:bg-violet-950 p-4 text-sm text-violet-900 dark:text-violet-100 focus:outline-none focus:ring-2 focus:ring-violet-500"
			>
				<svg class="w-5 h-5 shrink-0 text-violet-600 dark:text-violet-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
				</svg>
				<p>{gateText}</p>
			</div>
		{/if}

		{#if view.mode !== 'closed'}
			{#if projectsFailed}
				<div role="alert" class="mb-6 p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-200 text-sm">
					{$t('ask.projects_failed')}
				</div>
			{/if}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-6">
				<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('common.project')}</label>
				<select
					id="project"
					bind:value={selectedProject}
					class="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-200 px-3 py-2 text-sm"
				>
					<option value="">{$t('common.choose_project')}</option>
					{#each projects as p (p.project_id)}
						<option value={p.project_id}>{projectLabel(p)}</option>
					{/each}
				</select>
			</div>
		{/if}

		{#if view.mode !== 'closed' || history.length > 0}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden mb-6">
				<div class="min-h-[300px] max-h-[500px] overflow-y-auto p-4">
					{#if history.length === 0 && !loading && view.mode === 'available'}
						<div class="text-center py-12">
							<p class="text-gray-500 dark:text-gray-400 text-sm mb-4">{$t('ask.empty_prompt')}</p>
							{#if selectedProject}
								<div role="group" aria-label={$t('ask.suggestions_label')} class="flex flex-wrap gap-2 justify-center">
									{#each suggestionKeys as key (key)}
										<button
											type="button"
											onclick={() => useSuggestion(key)}
											class="px-3 py-1.5 text-xs border border-gray-200 dark:border-gray-700 rounded-full text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
										>{$t(key)}</button>
									{/each}
								</div>
							{:else}
								<p class="text-xs text-gray-500 dark:text-gray-400">{$t('ask.select_project_hint')}</p>
							{/if}
						</div>
					{/if}

					<div role="log" aria-live="polite" aria-label={$t('ask.log_label')} class="space-y-4">
						{#each history as qa, i (i)}
							<div class="flex justify-end">
								<div class="max-w-[80%] bg-blue-600 text-white rounded-2xl rounded-br-md px-4 py-2">
									<p class="text-sm whitespace-pre-wrap break-words"><span class="sr-only">{$t('ask.sr_question')} </span>{qa.question}</p>
								</div>
							</div>
							<div class="flex justify-start">
								<div class="max-w-[80%] bg-gray-100 dark:bg-gray-800 rounded-2xl rounded-bl-md px-4 py-3">
									<p class="text-sm text-gray-900 dark:text-gray-100 whitespace-pre-wrap break-words"><span class="sr-only">{$t('ask.sr_answer')} </span>{qa.answer}</p>
									{#if answerMeta(qa)}
										<p class="text-[10px] text-gray-500 dark:text-gray-400 mt-2">{answerMeta(qa)}</p>
									{/if}
								</div>
							</div>
						{/each}

						{#if loading}
							<div class="flex justify-start" aria-hidden="true">
								<div class="bg-gray-100 dark:bg-gray-800 rounded-2xl rounded-bl-md px-4 py-3">
									<div class="flex items-center gap-1">
										<span class="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
										<span class="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
										<span class="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
									</div>
								</div>
							</div>
						{/if}
					</div>
				</div>
				<div role="status" class="sr-only">{loading ? $t('ask.thinking') : ''}</div>

				{#if view.mode !== 'closed'}
					<form
						class="border-t border-gray-200 dark:border-gray-700 p-3 flex gap-2"
						onsubmit={(e) => {
							e.preventDefault();
							askQuestion();
						}}
					>
						<label for="ask-input" class="sr-only">{$t('ask.input_label')}</label>
						<input
							id="ask-input"
							type="text"
							maxlength={MAX_QUESTION_LENGTH}
							bind:this={inputEl}
							bind:value={question}
							placeholder={selectedProject ? $t('ask.placeholder') : $t('ask.placeholder_no_project')}
							disabled={!canCompose}
							aria-describedby={view.mode === 'exhausted' ? 'ask-gate-message' : undefined}
							class="flex-1 min-w-0 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-200 px-4 py-2 text-sm disabled:opacity-50"
						/>
						<button
							type="submit"
							disabled={!canCompose || !question.trim()}
							aria-label={$t('ask.send')}
							class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
						>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
							</svg>
						</button>
					</form>
				{/if}
			</div>
		{/if}

		{#if sendErrorKey}
			<div role="alert" class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-200 text-sm">
				{$t(sendErrorKey)}
			</div>
		{/if}
	{/if}
</div>
