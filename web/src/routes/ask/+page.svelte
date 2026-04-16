<script lang="ts">
	import { getProjects } from '$lib/api';
	import { error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import { supabase } from '$lib/supabase';

	interface QA {
		question: string;
		answer: string;
		model?: string;
		tokens_used?: number;
	}

	let projects: { project_id: string; name: string; activity_count?: number }[] = $state([]);
	let selectedProject = $state('');
	let question = $state('');
	let history: QA[] = $state([]);
	let loading = $state(false);
	let error = $state('');

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch { /* ignore */ }
	}

	async function askQuestion() {
		if (!selectedProject || !question.trim()) return;
		loading = true;
		error = '';
		const q = question.trim();
		question = '';
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: { session } } = await supabase.auth.getSession();
			const headers: Record<string, string> = {
				'Content-Type': 'application/json',
			};
			if (session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
			const res = await fetch(`${BASE}/api/v1/projects/${selectedProject}/ask`, {
				method: 'POST',
				headers,
				body: JSON.stringify({ question: q }),
			});
			if (!res.ok) {
				const text = await res.text();
				throw new Error(text || `HTTP ${res.status}`);
			}
			const data: QA = await res.json();
			history = [...history, data];
		} catch (e: any) {
			error = e.message || 'Failed to get answer';
			toastError(error);
			// Restore question on error
			question = q;
		} finally {
			loading = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			askQuestion();
		}
	}

	$effect(() => { loadProjects(); });

	const suggestions = [
		'What is the critical path?',
		'Which activities have negative float?',
		'How many milestones are delayed?',
		'What is the overall schedule health?',
		'Which WBS has the most risk?',
	];
</script>

<svelte:head>
	<title>{$t('page.ask')} | MeridianIQ</title>
</svelte:head>

<main class="max-w-4xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.ask')}</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">Ask questions about your schedule in natural language</p>
	</div>

	<!-- Project selector -->
	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-6">
		<label for="project" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('common.project')}</label>
		<select id="project" bind:value={selectedProject} class="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 px-3 py-2 text-sm">
			<option value="">{$t('common.choose_project')}</option>
			{#each projects as p}
				<option value={p.project_id}>{p.name || p.project_id} ({p.activity_count} act.)</option>
			{/each}
		</select>
	</div>

	<!-- Chat area -->
	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden mb-6">
		<!-- Messages -->
		<div class="min-h-[300px] max-h-[500px] overflow-y-auto p-4 space-y-4">
			{#if history.length === 0 && !loading}
				<div class="text-center py-12">
					<p class="text-gray-400 dark:text-gray-500 text-sm mb-4">Ask anything about your schedule</p>
					{#if selectedProject}
						<div class="flex flex-wrap gap-2 justify-center">
							{#each suggestions as s}
								<button
									onclick={() => { question = s; askQuestion(); }}
									class="px-3 py-1.5 text-xs border border-gray-200 dark:border-gray-700 rounded-full text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
								>{s}</button>
							{/each}
						</div>
					{:else}
						<p class="text-xs text-gray-400">Select a project above to start</p>
					{/if}
				</div>
			{/if}

			{#each history as qa}
				<!-- Question -->
				<div class="flex justify-end">
					<div class="max-w-[80%] bg-blue-600 text-white rounded-2xl rounded-br-md px-4 py-2">
						<p class="text-sm">{qa.question}</p>
					</div>
				</div>
				<!-- Answer -->
				<div class="flex justify-start">
					<div class="max-w-[80%] bg-gray-100 dark:bg-gray-800 rounded-2xl rounded-bl-md px-4 py-3">
						<p class="text-sm text-gray-900 dark:text-gray-100 whitespace-pre-wrap">{qa.answer}</p>
						{#if qa.model || qa.tokens_used}
							<p class="text-[10px] text-gray-400 mt-2">{qa.model || ''}{qa.tokens_used ? ` · ${qa.tokens_used} tokens` : ''}</p>
						{/if}
					</div>
				</div>
			{/each}

			{#if loading}
				<div class="flex justify-start">
					<div class="bg-gray-100 dark:bg-gray-800 rounded-2xl rounded-bl-md px-4 py-3">
						<div class="flex items-center gap-1">
							<span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
							<span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
							<span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
						</div>
					</div>
				</div>
			{/if}
		</div>

		<!-- Input -->
		<div class="border-t border-gray-200 dark:border-gray-700 p-3 flex gap-2">
			<input
				type="text"
				bind:value={question}
				onkeydown={handleKeydown}
				placeholder={selectedProject ? 'Ask about this schedule...' : 'Select a project first'}
				disabled={!selectedProject || loading}
				class="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 px-4 py-2 text-sm disabled:opacity-50"
			/>
			<button
				onclick={askQuestion}
				disabled={!selectedProject || !question.trim() || loading}
				class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
				</svg>
			</button>
		</div>
	</div>

	{#if error}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4">
			<p class="text-red-700 dark:text-red-400 text-sm">{error}</p>
			<p class="text-xs text-red-500 mt-1">Requires ANTHROPIC_API_KEY configured on the server</p>
		</div>
	{/if}
</main>
