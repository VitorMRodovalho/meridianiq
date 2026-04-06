<script lang="ts">
	interface Props {
		cards?: number;
		showChart?: boolean;
		showTable?: boolean;
	}

	let {
		cards = 4,
		showChart = true,
		showTable = true,
	}: Props = $props();
</script>

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
