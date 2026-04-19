<script lang="ts">
	// W3 of Cycle 1 v4.0 — lifecycle phase card.
	//
	// Renders the current lifecycle phase (5 + unknown), confidence as a
	// numeric value AND a 4-dot meter (ADR-0009 W3 hard requirement),
	// the rationale (collapsed for high/medium, expanded for low), and
	// the override / revert action that opens LifecycleOverrideDialog.

	import LifecycleOverrideDialog from './LifecycleOverrideDialog.svelte';
	import { t } from '$lib/i18n';
	import { useProjectStatusPolling } from '$lib/composables/useProjectStatusPolling';
	import {
		getLifecycleSummary,
		deleteLifecycleOverride,
		type LifecyclePhaseSummary,
	} from '$lib/api';

	interface Props {
		projectId: string;
	}

	let { projectId }: Props = $props();

	let summary = $state<LifecyclePhaseSummary | null>(null);
	let loading = $state<boolean>(true);
	let error = $state<string | null>(null);
	let showDialog = $state<boolean>(false);
	let detailsOpen = $state<boolean>(false);
	let reverting = $state<boolean>(false);

	// Polling: when the project flips ready, re-fetch the summary so the
	// inference appears without a manual refresh. SvelteKit destroys this
	// component on route change so projectId is stable for the lifetime
	// of this instance — a snapshot is intended.
	// svelte-ignore state_referenced_locally
	const polling = useProjectStatusPolling(projectId, {
		onTerminal: (status): void => {
			if (status === 'ready') {
				void load();
			}
		},
	});

	async function load(): Promise<void> {
		loading = true;
		error = null;
		try {
			summary = await getLifecycleSummary(projectId);
			// Auto-expand rationale for low-confidence inferences.
			if (summary?.inference?.confidence_band === 'low') {
				detailsOpen = true;
			}
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			loading = false;
		}
	}

	async function handleRevert(): Promise<void> {
		if (!summary) return;
		reverting = true;
		try {
			await deleteLifecycleOverride(projectId);
			await load();
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			reverting = false;
		}
	}

	function onOverrideSaved(): void {
		showDialog = false;
		void load();
	}

	$effect(() => {
		if (projectId) void load();
	});

	// Derived UI state.
	let phase = $derived(summary?.effective_phase ?? 'unknown');
	let confidence = $derived(summary?.effective_confidence ?? null);
	let band = $derived(summary?.inference?.confidence_band ?? 'low');
	let source = $derived(summary?.source ?? null);
	let isComputing = $derived(polling.isComputing);

	// Label keys map 1:1 to LifecyclePhase enum.
	let phaseLabel = $derived($t(`lifecycle.phase.${phase}`));
	let bandLabel = $derived($t(`lifecycle.confidence.${band}`));
	let confidencePct = $derived(
		confidence !== null ? Math.round(confidence * 100) : null
	);

	// Dot meter — 4 segments mapped to quartiles (0-25, 25-50, 50-75, 75-100).
	let activeDots = $derived(
		confidence !== null ? Math.max(0, Math.min(4, Math.ceil(confidence * 4))) : 0
	);
	let bandColorClass = $derived(
		band === 'high'
			? 'bg-emerald-500 dark:bg-emerald-400'
			: band === 'medium'
				? 'bg-amber-500 dark:bg-amber-400'
				: 'bg-rose-500 dark:bg-rose-400'
	);
</script>

<div
	class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4"
	role="region"
	aria-label={$t('lifecycle.card_title')}
>
	<div class="flex items-start justify-between mb-3">
		<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
			{$t('lifecycle.card_title')}
		</h3>
		{#if source}
			<span
				class="text-[10px] px-2 py-0.5 rounded font-medium uppercase tracking-wide
					{source === 'manual'
					? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200'
					: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'}"
			>
				{source === 'manual'
					? $t('lifecycle.source_manual_badge')
					: $t('lifecycle.source_inferred_badge')}
			</span>
		{/if}
	</div>

	{#if loading}
		<div class="space-y-2 animate-pulse">
			<div class="h-6 w-2/3 bg-gray-200 dark:bg-gray-700 rounded"></div>
			<div class="h-3 w-1/2 bg-gray-200 dark:bg-gray-700 rounded"></div>
		</div>
	{:else if error}
		<p class="text-sm text-rose-600 dark:text-rose-400">{$t('lifecycle.card_failed')}</p>
		<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{error}</p>
	{:else if isComputing && phase === 'unknown'}
		<p class="text-sm text-gray-500 dark:text-gray-400">{$t('lifecycle.card_empty')}</p>
	{:else}
		<p
			class="text-2xl font-semibold text-gray-900 dark:text-gray-100 capitalize"
			aria-label={phase === 'unknown'
				? $t('lifecycle.phase.unknown')
				: confidencePct !== null
					? `${phaseLabel}, ${$t('lifecycle.confidence.suffix').replace('{pct}', String(confidencePct))} (${bandLabel})`
					: phaseLabel}
		>
			{phaseLabel}
		</p>

		{#if confidencePct !== null}
			<div class="mt-2 flex items-center gap-2">
				<div class="flex gap-1" aria-hidden="true">
					{#each [0, 1, 2, 3] as i}
						<span
							class="block w-2.5 h-2.5 rounded-full transition-colors
								{i < activeDots
								? bandColorClass
								: 'bg-gray-200 dark:bg-gray-700'}"
						></span>
					{/each}
				</div>
				<span class="text-sm text-gray-700 dark:text-gray-300 tabular-nums">
					{$t('lifecycle.confidence.suffix').replace('{pct}', String(confidencePct))}
				</span>
				<span
					class="text-xs px-2 py-0.5 rounded uppercase tracking-wide
						{band === 'high'
						? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200'
						: band === 'medium'
							? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200'
							: 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200'}"
				>
					{bandLabel}
				</span>
			</div>
			{#if band === 'low'}
				<p class="text-xs text-rose-700 dark:text-rose-300 mt-2">
					{$t('lifecycle.card_low_hint')}
				</p>
			{/if}
		{/if}

		{#if summary?.latest_override && source === 'manual'}
			<p class="text-xs text-gray-500 dark:text-gray-400 mt-2 italic">
				{$t('lifecycle.override_by_prefix')}
				{#if summary.latest_override.overridden_by}
					— {summary.latest_override.overridden_by}
				{/if}
				{#if summary.latest_override.overridden_at}
					— {new Date(summary.latest_override.overridden_at).toLocaleString()}
				{/if}
			</p>
		{/if}

		{#if summary?.inference}
			<details
				class="mt-3 text-xs"
				bind:open={detailsOpen}
			>
				<summary
					class="cursor-pointer text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 select-none"
				>
					{$t('lifecycle.rationale_toggle')}
				</summary>
				<div class="mt-2 pl-2 border-l-2 border-gray-200 dark:border-gray-700">
					<p class="font-medium text-gray-700 dark:text-gray-300 mb-1">
						{$t('lifecycle.rationale_heading')}
					</p>
					<dl class="space-y-1 text-gray-600 dark:text-gray-400">
						{#each Object.entries(summary.inference.rationale) as [key, value]}
							<div class="flex gap-2">
								<dt class="font-mono text-[11px] shrink-0">{key}:</dt>
								<dd class="font-mono text-[11px] break-all">
									{typeof value === 'object' ? JSON.stringify(value) : String(value)}
								</dd>
							</div>
						{/each}
					</dl>
				</div>
			</details>
		{/if}

		<div class="mt-4 flex flex-wrap gap-2">
			{#if source === 'manual'}
				<button
					type="button"
					onclick={handleRevert}
					disabled={reverting}
					class="text-xs px-3 py-1.5 rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500"
				>
					{reverting ? $t('common.loading') : $t('lifecycle.override_revert_action')}
				</button>
			{/if}
			{#if !isComputing && summary?.inference}
				<button
					type="button"
					onclick={() => (showDialog = true)}
					class="text-xs px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-700 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
				>
					{$t('lifecycle.override_action')}
				</button>
			{/if}
		</div>
	{/if}
</div>

{#if showDialog && summary?.inference}
	<LifecycleOverrideDialog
		{projectId}
		inferredPhase={summary.inference.phase}
		inferredConfidencePct={confidencePct ?? 0}
		onClose={() => (showDialog = false)}
		onSaved={onOverrideSaved}
	/>
{/if}
