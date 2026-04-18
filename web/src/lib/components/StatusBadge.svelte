<script lang="ts">
	import { t } from '$lib/i18n';
	import type { ProjectStatus } from '$lib/types';

	type Props = {
		status: ProjectStatus;
		compact?: boolean;
	};

	const { status, compact = false }: Props = $props();

	// Colour tokens per status — hardcoded Tailwind utilities so dark-mode
	// variants apply without a theme-token indirection (project has none
	// today, per rules/frontend.md).
	const classes = $derived(
		status === 'ready'
			? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200'
			: status === 'pending'
				? 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-200'
				: 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200'
	);

	const label = $derived(
		status === 'ready'
			? $t('status.ready')
			: status === 'pending'
				? $t('status.computing')
				: $t('status.failed')
	);

	const showSpinner = $derived(status === 'pending');
</script>

<span
	class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium {classes}"
	class:px-1.5={compact}
	class:py-0={compact}
	role="status"
	aria-live="polite"
	aria-label={label}
	aria-busy={showSpinner ? 'true' : undefined}
>
	{#if showSpinner}
		<svg
			class="h-3 w-3 animate-spin"
			viewBox="0 0 24 24"
			fill="none"
			aria-hidden="true"
		>
			<circle
				class="opacity-25"
				cx="12"
				cy="12"
				r="10"
				stroke="currentColor"
				stroke-width="4"
			/>
			<path
				class="opacity-75"
				fill="currentColor"
				d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
			/>
		</svg>
	{/if}
	{label}
</span>
