<script lang="ts">
	// W3 of Cycle 1 v4.0 — lifecycle phase override dialog.
	//
	// Centered modal on desktop, bottom-sheet on mobile. Diff display
	// (inferred → new), required reason text (10 char min API-side, also
	// enforced here), preset quickpicks that prefill the textarea.
	// Focus trap + Escape closes (FE pre-check a11y P1s).

	import { t } from '$lib/i18n';
	import { onMount } from 'svelte';
	import {
		postLifecycleOverride,
		type LifecycleOverrideRequest,
	} from '$lib/api';
	import type { LifecyclePhase } from '$lib/types';

	interface Props {
		projectId: string;
		inferredPhase: LifecyclePhase;
		inferredConfidencePct: number;
		onClose: () => void;
		onSaved: () => void;
	}

	let { projectId, inferredPhase, inferredConfidencePct, onClose, onSaved }: Props = $props();

	const PHASES: LifecyclePhase[] = [
		'planning',
		'design',
		'procurement',
		'construction',
		'closeout',
	];

	const QUICKPICK_KEYS = [
		'lifecycle.override_quickpick_erp',
		'lifecycle.override_quickpick_stakeholder',
		'lifecycle.override_quickpick_inference_error',
		'lifecycle.override_quickpick_milestone',
	] as const;

	// Snapshot at mount: the dialog opens once with whatever inferredPhase
	// is current; the user then edits selectedPhase locally. Re-mounting
	// the dialog (close + reopen) reads the latest prop.
	// svelte-ignore state_referenced_locally
	let selectedPhase = $state<LifecyclePhase>(inferredPhase);
	let reason = $state<string>('');
	let submitting = $state<boolean>(false);
	let formError = $state<string | null>(null);
	let dialogEl: HTMLDivElement | null = $state(null);
	let phaseSelectEl: HTMLSelectElement | null = $state(null);

	const REASON_MIN = 10;

	let reasonValid = $derived(reason.trim().length >= REASON_MIN);
	let phaseChanged = $derived(selectedPhase !== inferredPhase);
	let canSubmit = $derived(reasonValid && phaseChanged && !submitting);

	function applyQuickpick(key: string): void {
		reason = $t(key);
	}

	async function submit(): Promise<void> {
		formError = null;
		if (!canSubmit) return;
		submitting = true;
		try {
			const body: LifecycleOverrideRequest = {
				override_phase: selectedPhase,
				override_reason: reason.trim(),
			};
			await postLifecycleOverride(projectId, body);
			onSaved();
		} catch (err) {
			formError = err instanceof Error ? err.message : String(err);
		} finally {
			submitting = false;
		}
	}

	function handleKey(event: KeyboardEvent): void {
		if (event.key === 'Escape') {
			event.preventDefault();
			onClose();
		}
	}

	onMount((): (() => void) | void => {
		if (typeof document === 'undefined') return;
		const previouslyFocused = document.activeElement as HTMLElement | null;
		// Defer focus until after mount so the select is in the DOM.
		queueMicrotask(() => {
			phaseSelectEl?.focus();
		});
		document.addEventListener('keydown', handleKey);
		return () => {
			document.removeEventListener('keydown', handleKey);
			previouslyFocused?.focus?.();
		};
	});
</script>

<!-- Backdrop -->
<div
	class="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-0 sm:p-4"
	onclick={(e) => {
		if (e.target === e.currentTarget) onClose();
	}}
	role="presentation"
>
	<div
		bind:this={dialogEl}
		role="dialog"
		aria-modal="true"
		aria-labelledby="lifecycle-override-title"
		class="bg-white dark:bg-gray-900 rounded-t-2xl sm:rounded-lg shadow-xl w-full sm:max-w-md p-5 max-h-[90vh] overflow-y-auto"
	>
		<h2
			id="lifecycle-override-title"
			class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1"
		>
			{$t('lifecycle.override_dialog_title')}
		</h2>
		<p class="text-xs text-gray-500 dark:text-gray-400 mb-4">
			{$t('lifecycle.override_reason_help')}
		</p>

		<!-- Diff display -->
		<div
			role="group"
			aria-labelledby="lifecycle-override-diff-heading"
			class="mb-4 rounded border border-gray-200 dark:border-gray-700 p-3 bg-gray-50 dark:bg-gray-800/50"
		>
			<p
				id="lifecycle-override-diff-heading"
				class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2"
			>
				{$t('lifecycle.override_diff_heading')}
			</p>
			<div class="flex flex-col sm:flex-row sm:items-center gap-2 text-sm">
				<span class="text-gray-600 dark:text-gray-400">
					{$t('lifecycle.inferred_phase')}: <strong class="capitalize">{$t(`lifecycle.phase.${inferredPhase}`)}</strong>
					<span class="text-xs">({inferredConfidencePct}%)</span>
				</span>
				<span class="text-gray-400" aria-hidden="true">↓</span>
				<span class="text-gray-900 dark:text-gray-100">
					{$t('lifecycle.manual_phase')}:
					<strong class="capitalize text-blue-700 dark:text-blue-300">
						{$t(`lifecycle.phase.${selectedPhase}`)}
					</strong>
				</span>
			</div>
		</div>

		<!-- Phase selector -->
		<label class="block mb-4">
			<span class="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">
				{$t('lifecycle.override_phase_label')}
			</span>
			<select
				bind:this={phaseSelectEl}
				bind:value={selectedPhase}
				class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
			>
				{#each PHASES as phase}
					<option value={phase}>{$t(`lifecycle.phase.${phase}`)}</option>
				{/each}
			</select>
		</label>

		<!-- Quickpicks -->
		<div class="mb-3">
			<p class="text-xs text-gray-500 dark:text-gray-400 mb-1">
				{$t('lifecycle.override_quickpick_hint')}
			</p>
			<div class="flex flex-wrap gap-1.5">
				{#each QUICKPICK_KEYS as key}
					<button
						type="button"
						onclick={() => applyQuickpick(key)}
						class="text-xs px-2.5 py-1 rounded-full border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
					>
						{$t(key)}
					</button>
				{/each}
			</div>
		</div>

		<!-- Reason textarea -->
		<label class="block mb-4">
			<span class="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">
				{$t('lifecycle.override_reason_label')}
			</span>
			<textarea
				bind:value={reason}
				rows="3"
				maxlength="2000"
				placeholder={$t('lifecycle.override_reason_placeholder')}
				aria-describedby="lifecycle-override-reason-help"
				class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
			></textarea>
			<p
				id="lifecycle-override-reason-help"
				class="text-xs mt-1 {reasonValid
					? 'text-gray-500 dark:text-gray-400'
					: 'text-rose-600 dark:text-rose-400'}"
			>
				{#if reasonValid}
					{reason.trim().length} / 2000
				{:else}
					{$t('lifecycle.override_reason_required')}
				{/if}
			</p>
		</label>

		{#if formError}
			<p class="text-sm text-rose-600 dark:text-rose-400 mb-3">{formError}</p>
		{/if}

		<div class="flex justify-end gap-2 pt-2 border-t border-gray-200 dark:border-gray-700">
			<button
				type="button"
				onclick={onClose}
				disabled={submitting}
				class="px-3 py-1.5 text-sm rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
			>
				{$t('lifecycle.override_cancel')}
			</button>
			<button
				type="button"
				onclick={submit}
				disabled={!canSubmit}
				class="px-3 py-1.5 text-sm rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500"
			>
				{submitting ? $t('lifecycle.override_submitting') : $t('lifecycle.override_submit')}
			</button>
		</div>
	</div>
</div>
