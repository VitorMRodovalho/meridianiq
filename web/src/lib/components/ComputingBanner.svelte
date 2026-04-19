<script lang="ts">
	// W3 of Cycle 1 v4.0 — sticky aggregate banner.
	//
	// Sits below the breadcrumb in `+layout.svelte`. Reads from the global
	// `computingProjects` store and renders a thin strip when the user has
	// any project in a non-terminal status. Dismissible per-session: once
	// dismissed at count N the banner stays hidden until the count exceeds
	// N (FE pre-check spec — surface only on new computing).

	import { computingProjects, startComputingPoll } from '$lib/stores/computing';
	import { t } from '$lib/i18n';

	const SESSION_KEY = 'meridianiq-computing-banner-dismissed-at-count';

	startComputingPoll();

	let dismissedAt = $state<number | null>(_readDismiss());
	// Council P2 (FE end-of-wave): count only pending — failed is
	// terminal-with-attention, not "in progress in the background".
	// Surfacing failed in the same count misleads users into thinking
	// the system is still working on those rows.
	let count = $derived(
		Array.from($computingProjects.statuses.values()).filter((s) => s === 'pending').length
	);
	let visible = $derived(count > 0 && (dismissedAt === null || count > dismissedAt));

	function _readDismiss(): number | null {
		if (typeof sessionStorage === 'undefined') return null;
		const raw = sessionStorage.getItem(SESSION_KEY);
		if (!raw) return null;
		const parsed = Number.parseInt(raw, 10);
		return Number.isFinite(parsed) ? parsed : null;
	}

	function dismiss(): void {
		dismissedAt = count;
		if (typeof sessionStorage !== 'undefined') {
			sessionStorage.setItem(SESSION_KEY, String(count));
		}
	}

	let label = $derived(
		$t('projects.computing_global').replace('{count}', String(count))
	);
</script>

{#if visible}
	<div
		role="status"
		aria-live="polite"
		aria-atomic="true"
		class="bg-amber-50 dark:bg-amber-950/40 border-b border-amber-200 dark:border-amber-800 px-4 py-1.5 flex items-center gap-3 text-xs text-amber-900 dark:text-amber-100"
	>
		<svg
			class="w-3.5 h-3.5 animate-spin shrink-0"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			aria-hidden="true"
		>
			<circle cx="12" cy="12" r="10" stroke-width="2" class="opacity-25" />
			<path
				d="M12 2a10 10 0 0110 10"
				stroke-width="2"
				stroke-linecap="round"
				class="opacity-75"
			/>
		</svg>
		<span class="flex-1">{label}</span>
		<button
			type="button"
			onclick={dismiss}
			class="text-amber-900 dark:text-amber-200 hover:underline focus:outline-none focus:ring-2 focus:ring-amber-500 rounded px-2"
			aria-label={$t('lifecycle.banner_dismiss')}
		>
			×
		</button>
	</div>
{/if}
