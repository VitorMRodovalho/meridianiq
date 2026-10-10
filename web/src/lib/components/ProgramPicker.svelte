<script lang="ts">
	// Choose a schedule's program: one of the user's programs, or a new one.
	// Pre-selects the program whose name resembles the file's project name
	// (advisory; the user confirms or changes it). Native radios, select and
	// input, so keyboard, screen readers and mobile pickers work unaided.

	import { t } from '$lib/i18n';
	import {
		programNamed,
		suggestProgram,
		type ProgramChoice,
		type ProgramOption
	} from '$lib/programPick';

	interface Props {
		/** The user's programs, most recently updated first. */
		programs: (ProgramOption & { revision_count?: number })[];
		/** The project name read from the file, if any. */
		shortName: string | null;
		/** A program to leave out of the list (the one a schedule is moving from). */
		excludeId?: string | null;
		/** Prefix for element ids, unique per page. */
		idPrefix: string;
		/** The current choice; null while it is incomplete. */
		choice?: ProgramChoice | null;
		/** The program list is still loading: no suggestion and no choice yet. */
		loading?: boolean;
	}

	let {
		programs,
		shortName,
		excludeId = null,
		idPrefix,
		choice = $bindable(null),
		loading = false
	}: Props = $props();

	const options = $derived(programs.filter((p) => p.id !== excludeId));
	const current = $derived(programs.find((p) => p.id === excludeId) ?? null);
	const suggestion = $derived(suggestProgram(shortName, options));

	let mode = $state<'existing' | 'new'>('new');
	let selectedId = $state('');
	let newName = $state('');

	// Reset the defaults whenever a new file (or list) arrives; after that
	// the user's edits stand.
	$effect(() => {
		const s = suggestion;
		const opts = options;
		const name = shortName;
		if (s) {
			mode = 'existing';
			selectedId = s.program.id;
		} else {
			mode = 'new';
			selectedId = opts[0]?.id ?? '';
		}
		newName = name ?? '';
	});

	// Typing the name of the program the schedule is already in would move
	// it nowhere, so it is not a choice.
	const isCurrent = $derived(
		mode === 'new' && current !== null && programNamed(newName, [current]) !== null
	);

	$effect(() => {
		const name = newName.trim();
		choice = loading || isCurrent
			? null
			: mode === 'existing'
				? selectedId
					? { programId: selectedId }
					: null
				: name
					? { newProgramName: name }
					: null;
	});

	const sameName = $derived(mode === 'new' ? programNamed(newName, options) : null);

	function useExisting(id: string): void {
		mode = 'existing';
		selectedId = id;
	}

	function revisions(n: number | undefined): string {
		const count = n ?? 0;
		return count === 1
			? $t('program_pick.revision_one')
			: $t('program_pick.revisions').replace('{n}', String(count));
	}
</script>

<fieldset class="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
	<legend class="px-1 text-sm font-semibold text-gray-900 dark:text-gray-100">
		{$t('program_pick.legend')}
	</legend>

	<p id="{idPrefix}-reason" class="text-xs text-gray-500 dark:text-gray-400 mb-3" aria-live="polite">
		{#if loading}
			{$t('common.loading')}
		{:else if suggestion}
			{$t('program_pick.suggested').replace('{name}', suggestion.matched)}
		{:else if shortName}
			{$t('program_pick.no_suggestion').replace('{name}', shortName)}
		{:else}
			{$t('program_pick.no_name')}
		{/if}
	</p>

	{#if loading}
		<div class="space-y-2" aria-hidden="true">
			<div class="h-4 w-2/3 rounded bg-gray-200 dark:bg-gray-700 animate-pulse"></div>
			<div class="h-9 w-full rounded bg-gray-200 dark:bg-gray-700 animate-pulse"></div>
		</div>
	{:else}
	{#if options.length > 0}
		<div class="flex flex-col gap-2 mb-3">
			<label class="flex items-center gap-2 text-sm text-gray-800 dark:text-gray-200 cursor-pointer">
				<input
					type="radio"
					name="{idPrefix}-mode"
					value="existing"
					bind:group={mode}
					class="h-4 w-4 text-blue-600 focus:ring-blue-500"
				/>
				{$t('program_pick.existing')}
			</label>
			{#if mode === 'existing'}
				<label class="block sm:pl-6">
					<span class="sr-only">{$t('program_pick.select_label')}</span>
					<select
						bind:value={selectedId}
						aria-describedby="{idPrefix}-reason"
						class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
					>
						{#each options as program (program.id)}
							<option value={program.id}>
								{program.name} · {revisions(program.revision_count)}
							</option>
						{/each}
					</select>
				</label>
			{/if}
		</div>
	{/if}

	<div class="flex flex-col gap-2">
		<label class="flex items-center gap-2 text-sm text-gray-800 dark:text-gray-200 cursor-pointer">
			<input
				type="radio"
				name="{idPrefix}-mode"
				value="new"
				bind:group={mode}
				class="h-4 w-4 text-blue-600 focus:ring-blue-500"
			/>
			{$t('program_pick.new')}
		</label>
		{#if mode === 'new'}
			<label class="block sm:pl-6">
				<span class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
					{$t('program_pick.new_label')}
				</span>
				<input
					type="text"
					bind:value={newName}
					maxlength="200"
					aria-describedby="{idPrefix}-reason{sameName || isCurrent ? ` ${idPrefix}-same` : ''}"
					class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
				/>
			</label>
			{#if isCurrent && current}
				<p id="{idPrefix}-same" class="sm:pl-6 text-xs text-amber-700 dark:text-amber-300">
					{$t('program_pick.name_is_current').replace('{name}', current.name)}
				</p>
			{:else if sameName}
				<p id="{idPrefix}-same" class="sm:pl-6 text-xs text-amber-700 dark:text-amber-300">
					{$t('program_pick.name_exists').replace('{name}', sameName.name)}
					<button
						type="button"
						onclick={() => useExisting(sameName.id)}
						class="ml-1 underline hover:no-underline focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
					>
						{$t('program_pick.use_existing')}
					</button>
				</p>
			{/if}
		{/if}
	</div>
	{/if}
</fieldset>
