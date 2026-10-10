<script lang="ts">
	// Move one or more schedules into one of the user's programs, or a new
	// one. Same modal pattern as LifecycleOverrideDialog: centered on
	// desktop, bottom sheet on mobile, Escape closes, focus returns to the
	// opener.

	import { onMount } from 'svelte';
	import { t } from '$lib/i18n';
	import {
		ApiError,
		getPrograms,
		placeProject,
		placeProjects,
		type ProgramListItem
	} from '$lib/api';
	import type { ProgramChoice } from '$lib/programPick';
	import ProgramPicker from './ProgramPicker.svelte';

	interface Props {
		projectIds: string[];
		/** The program the schedules are in now, left out of the list (single move). */
		currentProgramId?: string | null;
		/** The schedule's project name, for the suggestion (single move). */
		shortName?: string | null;
		onClose: () => void;
		onMoved: (result: { programId: string; programName: string; count: number }) => void;
		/** A move failed; some of several may have moved, so the caller reloads. */
		onFailed?: () => void;
	}

	let {
		projectIds,
		currentProgramId = null,
		shortName = null,
		onClose,
		onMoved,
		onFailed
	}: Props = $props();

	let programs: ProgramListItem[] = $state([]);
	let loadingPrograms = $state(true);
	let programsFailed = $state(false);
	let choice: ProgramChoice | null = $state(null);
	let submitting = $state(false);
	let formError: string | null = $state(null);
	let titleEl: HTMLHeadingElement | null = $state(null);

	const count = $derived(projectIds.length);

	async function submit(): Promise<void> {
		if (!choice || submitting) return;
		formError = null;
		submitting = true;
		try {
			const programId =
				count === 1
					? (await placeProject(projectIds[0], choice)).program_id
					: (await placeProjects(projectIds, choice)).program_id;
			const programName =
				'newProgramName' in choice
					? choice.newProgramName
					: (programs.find((p) => p.id === programId)?.name ?? '');
			onMoved({ programId, programName, count });
		} catch (err) {
			formError = moveError(err);
			onFailed?.();
		} finally {
			submitting = false;
		}
	}

	function moveError(err: unknown): string {
		if (err instanceof ApiError) {
			if (err.status === 409) return $t('move.linked');
			if (err.status === 404) return $t('move.not_found');
		}
		return $t('move.failed');
	}

	function handleKey(event: KeyboardEvent): void {
		if (event.key === 'Escape' && !submitting) {
			event.preventDefault();
			onClose();
		}
	}

	onMount((): (() => void) | void => {
		if (typeof document === 'undefined') return;
		const previouslyFocused = document.activeElement as HTMLElement | null;
		queueMicrotask(() => titleEl?.focus());
		document.addEventListener('keydown', handleKey);
		getPrograms()
			.then((res) => {
				programs = res.programs ?? [];
			})
			.catch(() => {
				programsFailed = true;
			})
			.finally(() => {
				loadingPrograms = false;
			});
		return () => {
			document.removeEventListener('keydown', handleKey);
			previouslyFocused?.focus?.();
		};
	});
</script>

<div
	class="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-0 sm:p-4"
	onclick={(e) => {
		if (e.target === e.currentTarget && !submitting) onClose();
	}}
	role="presentation"
>
	<div
		role="dialog"
		aria-modal="true"
		aria-labelledby="move-program-title"
		aria-describedby="move-program-help"
		class="bg-white dark:bg-gray-900 rounded-t-2xl sm:rounded-lg shadow-xl w-full sm:max-w-md p-5 max-h-[90vh] overflow-y-auto"
	>
		<h2
			id="move-program-title"
			bind:this={titleEl}
			tabindex="-1"
			class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1 focus:outline-none"
		>
			{count === 1 ? $t('move.title_one') : $t('move.title_many').replace('{n}', String(count))}
		</h2>
		<p id="move-program-help" class="text-xs text-gray-500 dark:text-gray-400 mb-4">
			{$t('move.help')}
		</p>

		{#if loadingPrograms}
			<p class="text-sm text-gray-500 dark:text-gray-400 py-6 text-center">{$t('common.loading')}</p>
		{:else if programsFailed}
			<p class="text-sm text-rose-700 dark:text-rose-300 py-6 text-center" role="alert">
				{$t('upload.programs_failed')}
			</p>
		{:else}
			<ProgramPicker
				{programs}
				{shortName}
				excludeId={currentProgramId}
				idPrefix="move-program"
				bind:choice
			/>
		{/if}

		{#if formError}
			<p class="text-sm text-rose-600 dark:text-rose-400 mt-3" role="alert">{formError}</p>
		{/if}

		<div class="flex justify-end gap-2 pt-4 mt-4 border-t border-gray-200 dark:border-gray-700">
			<button
				type="button"
				onclick={onClose}
				disabled={submitting}
				class="px-3 py-1.5 text-sm rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
			>
				{$t('move.cancel')}
			</button>
			<button
				type="button"
				onclick={submit}
				disabled={!choice || submitting || loadingPrograms || programsFailed}
				class="px-3 py-1.5 text-sm rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500"
			>
				{submitting ? $t('move.submitting') : $t('move.submit')}
			</button>
		</div>
	</div>
</div>
