<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { uploadXER, getPrograms, ApiError, type ProgramListItem } from '$lib/api';
	import { readShortName, type ProgramChoice } from '$lib/programPick';
	import ProgramPicker from '$lib/components/ProgramPicker.svelte';
	import { supabase } from '$lib/supabase';
	import { trackEvent } from '$lib/analytics';
	import { success, error as toastError } from '$lib/toast';
	import RevisionConfirmCard from '$lib/components/RevisionConfirmCard.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import type { ProjectSummary } from '$lib/types';
	import { t } from '$lib/i18n';

	// Auth gate — uploading a file requires an account in production. Resolve
	// the session up front so a logged-out visitor sees a sign-in affordance
	// (+ a link to the no-login demo) instead of dragging a file and hitting a
	// raw 401 after the spinner.
	let authChecked = $state(false);
	let authenticated = $state(false);

	onMount(async () => {
		try {
			const {
				data: { session }
			} = await supabase.auth.getSession();
			authenticated = !!session;
			if (authenticated) void loadPrograms();
		} catch {
			authenticated = false;
		} finally {
			authChecked = true;
		}
	});

	let dragging = $state(false);
	let loading = $state(false);
	let error = $state('');
	let result: ProjectSummary | null = $state(null);
	let isSandbox = $state(false);
	// Cycle 4 W2 PR-B — controls visibility of the revision confirmation
	// card. Set to false on confirm/skip so the card collapses; sandbox
	// uploads bypass entirely (testing data shouldn't enter revision lineage).
	let showRevisionCard = $state(true);

	// The file waits here while the user chooses its program.
	let staged: File | null = $state(null);
	let stagedName: string | null = $state(null);
	let programs: ProgramListItem[] = $state([]);
	// The suggestion needs the real list: until it loads (Fly cold start) or
	// if it fails, no program can be chosen, so a matching program is never
	// missed and a duplicate created next to it.
	let programsState: 'loading' | 'ready' | 'error' = $state('loading');
	let programChoice: ProgramChoice | null = $state(null);
	// The choice sent with the last upload, to tell whether it was honoured.
	let sentChoice: ProgramChoice | null = $state(null);
	let stagedTitle: HTMLHeadingElement | null = $state(null);

	async function loadPrograms(): Promise<void> {
		if (programsState !== 'ready') programsState = 'loading';
		try {
			programs = (await getPrograms()).programs ?? [];
			programsState = 'ready';
		} catch {
			if (programsState !== 'ready') programsState = 'error';
		}
	}

	function programName(id: string | null | undefined): string | null {
		return id ? (programs.find((p) => p.id === id)?.name ?? null) : null;
	}

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
		if (file) await stage(file);
	}

	async function handleFileInput(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		input.value = '';
		if (file) await stage(file);
	}

	async function stage(file: File) {
		const name = file.name.toLowerCase();
		if (!name.endsWith('.xer') && !name.endsWith('.xml')) {
			error = $t('upload.bad_type');
			return;
		}
		error = '';
		result = null;
		stagedName = await readShortName(file);
		staged = file;
		// Announce the second step: move focus to it.
		await tick();
		stagedTitle?.focus();
	}

	function unstage() {
		staged = null;
		stagedName = null;
	}

	async function doUpload() {
		const file = staged;
		if (!file) return;
		loading = true;
		error = '';
		result = null;
		showRevisionCard = true;
		sentChoice = isSandbox ? null : programChoice;
		try {
			result = await uploadXER(file, isSandbox, sentChoice ?? undefined);
			staged = null;
			stagedName = null;
			if (!isSandbox) void loadPrograms();
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
			// A 401 means the session expired mid-page — surface the sign-in
			// gate instead of a raw error. Branch on the typed HTTP status, not
			// the human-readable message (which is freeform/localized).
			if (e instanceof ApiError && e.status === 401) {
				authenticated = false;
				authChecked = true;
			}
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
	<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6">{$t('upload.title')}</h1>

	{#if !authChecked}
		<!-- Resolving auth — neutral state so a logged-out visitor never sees
			 the dropzone flash before it is replaced by the sign-in gate. -->
		<div class="flex items-center justify-center py-16 text-gray-400">
			<svg class="animate-spin h-6 w-6" viewBox="0 0 24 24" aria-hidden="true">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
		</div>
	{:else if !authenticated}
		<!-- Sign-in gate: replaces the raw 401 dead-end with a clear path
			 (sign in) plus the zero-friction escape hatch (the live demo). -->
		<div class="border border-gray-200 dark:border-gray-700 rounded-lg p-10 text-center bg-white dark:bg-gray-900">
			<svg class="mx-auto h-12 w-12 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
			</svg>
			<h2 class="mt-4 text-lg font-semibold text-gray-900 dark:text-gray-100">{$t('upload.signin_required_title')}</h2>
			<p class="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">{$t('upload.signin_required_body')}</p>
			<a
				href="/login"
				class="mt-6 inline-block bg-blue-600 text-white px-6 py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors"
			>
				{$t('upload.signin_cta')}
			</a>
			<p class="mt-4">
				<a href="/demo" class="text-sm text-blue-600 hover:underline">{$t('upload.try_demo')}</a>
			</p>
		</div>
	{:else}
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
				<input id="xer-file" type="file" accept=".xer,.xml" class="hidden" onchange={handleFileInput} />
			</label>
			<p class="mt-2 text-xs text-gray-400">{$t('upload.file_types')}</p>
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

	{#if staged && !loading}
		<form
			aria-labelledby="staged-title"
			onsubmit={(e) => {
				e.preventDefault();
				void doUpload();
			}}
			class="mt-6 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-5"
		>
			<h2
				id="staged-title"
				bind:this={stagedTitle}
				tabindex="-1"
				class="text-base font-semibold text-gray-900 dark:text-gray-100 focus:outline-none"
			>
				{$t('upload.staged_title')}
			</h2>
			<p class="mt-1 text-sm text-gray-700 dark:text-gray-300 break-all">
				{staged.name} · {(staged.size / 1024 / 1024).toFixed(1)} MB
			</p>
			{#if stagedName}
				<p class="text-xs text-gray-500 dark:text-gray-400">
					{$t('upload.staged_project').replace('{name}', stagedName)}
				</p>
			{/if}

			<div class="mt-4">
				{#if isSandbox}
					<p class="text-sm text-gray-600 dark:text-gray-400">{$t('upload.sandbox_no_program')}</p>
				{:else}
					<ProgramPicker
						{programs}
						shortName={stagedName}
						idPrefix="upload-program"
						loading={programsState !== 'ready'}
						bind:choice={programChoice}
					/>
					{#if programsState === 'error'}
						<p class="mt-2 text-sm text-rose-700 dark:text-rose-300" role="alert">
							{$t('upload.programs_failed')}
							<button
								type="button"
								onclick={() => void loadPrograms()}
								class="ml-1 underline hover:no-underline focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
							>
								{$t('upload.programs_retry')}
							</button>
						</p>
					{/if}
				{/if}
			</div>

			<div class="mt-4 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
				<button
					type="button"
					onclick={unstage}
					class="px-4 py-2 text-sm rounded-md border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
				>
					{$t('upload.change_file')}
				</button>
				<button
					type="submit"
					disabled={!isSandbox && (programsState !== 'ready' || !programChoice)}
					class="px-4 py-2 text-sm font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500"
				>
					{$t('upload.submit')}
				</button>
			</div>
		</form>
	{/if}
	{/if}

	<!-- Error -->
	{#if error}
		<div class="mt-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg p-4 text-sm text-red-700 dark:text-red-300">
			{error}
		</div>
	{/if}

	<!-- Result -->
	{#if result}
		<div class="mt-6 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
			<div class="flex flex-wrap items-center gap-2 mb-4">
				<svg class="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
					<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
				</svg>
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{$t('upload.success')}</h2>
				<StatusBadge status={result.status ?? 'pending'} />
			</div>
			{#if result.status === 'pending'}
				<p class="mb-4 text-sm text-sky-700 dark:text-sky-300">
					{$t('upload.computing_toast')}
				</p>
			{/if}
			{#if result.program_id}
				<p class="mb-4 text-sm text-gray-700 dark:text-gray-300">
					{$t('program_pick.legend')}:
					<a href="/programs/{result.program_id}" class="font-medium text-blue-600 dark:text-blue-400 hover:underline">
						{programName(result.program_id) ?? $t('move.view_program')}
					</a>
				</p>
			{:else if sentChoice}
				<p class="mb-4 text-sm text-amber-700 dark:text-amber-300" role="status">
					{$t('upload.program_failed')}
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

		<!--
			Cycle 4 W2 PR-B — revision confirmation card.
			Renders only for non-sandbox uploads (sandbox bypass per
			frontend-ux-reviewer entry council #3). Card self-detects;
			collapses if no candidate found OR if detect-revision-of fails.

			DA exit-council fix-up #P1-1 / #P2-2: ``{#key result.project_id}``
			forces unmount + remount when the user uploads a different file
			before the previous detect resolves. Without this, the component
			instance is reused with stale ``$state``, and a slow detect for
			file A can resolve AFTER file B's detect has set state — silent
			data corruption (revision_history row anchored to wrong parent).
		-->
		{#if !isSandbox && showRevisionCard}
			{#key result.project_id}
				<RevisionConfirmCard
					projectId={result.project_id}
					onConfirmed={() => {
						showRevisionCard = false;
					}}
					onSkipped={() => {
						showRevisionCard = false;
					}}
				/>
			{/key}
		{/if}
	{/if}
</div>
