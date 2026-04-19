<script lang="ts">
	import { t } from '$lib/i18n';

	interface Props {
		cards?: number;
		showChart?: boolean;
		showTable?: boolean;
		// W3: distinguish a generic "loading" pulse from "materializing"
		// (background analytics) so the user gets honest expectations
		// about wait time. Existing callers default to 'loading'.
		mode?: 'loading' | 'materializing';
		// Optional progress hint when WebSocket progress is available
		// (Monte Carlo wires this; static analyses leave it undefined).
		progressPct?: number | null;
	}

	let {
		cards = 4,
		showChart = true,
		showTable = true,
		mode = 'loading',
		progressPct = null,
	}: Props = $props();
</script>

{#if mode === 'materializing'}
	<div
		role="status"
		aria-live="polite"
		class="mb-4 flex items-center gap-3 px-4 py-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-sm text-amber-900 dark:text-amber-100"
	>
		<svg
			class="w-4 h-4 animate-spin shrink-0"
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
		<span class="flex-1">{$t('analysis.materializing_banner')}</span>
		{#if progressPct !== null && progressPct >= 0 && progressPct <= 100}
			<div
				class="w-32 h-1.5 bg-amber-200 dark:bg-amber-800 rounded overflow-hidden"
				role="progressbar"
				aria-valuenow={Math.round(progressPct)}
				aria-valuemin={0}
				aria-valuemax={100}
			>
				<div
					class="h-full bg-amber-600 dark:bg-amber-400 transition-all"
					style="width: {Math.round(progressPct)}%"
				></div>
			</div>
			<span class="tabular-nums text-xs">{Math.round(progressPct)}%</span>
		{/if}
	</div>
{/if}

<div class="animate-pulse">
	<!-- KPI cards skeleton -->
	<div class="grid grid-cols-2 md:grid-cols-{cards} gap-3 mb-6">
		{#each Array(cards) as _}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-3">
				<div class="h-6 bg-gray-200 dark:bg-gray-700 rounded w-16 mx-auto mb-2"></div>
				<div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-20 mx-auto"></div>
			</div>
		{/each}
	</div>

	{#if showChart}
		<!-- Chart skeleton -->
		<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
				<div class="h-4 bg-gray-200 dark:bg-gray-700 rounded w-32 mb-4"></div>
				<div class="h-48 bg-gray-100 dark:bg-gray-800 rounded flex items-end justify-around px-4 pb-4 gap-2">
					{#each [60, 80, 45, 90, 70, 55] as h}
						<div class="bg-gray-200 dark:bg-gray-700 rounded-t w-8" style="height: {h}%"></div>
					{/each}
				</div>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
				<div class="h-4 bg-gray-200 dark:bg-gray-700 rounded w-32 mb-4"></div>
				<div class="h-48 bg-gray-100 dark:bg-gray-800 rounded flex items-center justify-center">
					<div class="w-32 h-32 rounded-full border-8 border-gray-200 dark:border-gray-700"></div>
				</div>
			</div>
		</div>
	{/if}

	{#if showTable}
		<!-- Table skeleton -->
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
			<div class="h-5 bg-gray-200 dark:bg-gray-700 rounded w-40 mb-4"></div>
			<div class="space-y-3">
				{#each Array(5) as _, i}
					<div class="flex items-center gap-4">
						<div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-24"></div>
						<div class="h-3 bg-gray-200 dark:bg-gray-700 rounded flex-1"></div>
						<div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-16"></div>
						<div class="h-5 bg-gray-200 dark:bg-gray-700 rounded w-12"></div>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
