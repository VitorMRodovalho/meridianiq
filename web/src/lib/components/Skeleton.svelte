<script lang="ts">
	interface Props {
		lines?: number;
		height?: string;
		class?: string;
	}

	let {
		lines = 3,
		height = 'h-4',
		class: className = '',
	}: Props = $props();
</script>

<div class="animate-pulse space-y-3 {className}">
	{#each Array(lines) as _, i}
		<div class="{height} bg-gray-200 dark:bg-gray-700 rounded {i === lines - 1 ? 'w-3/4' : 'w-full'}"></div>
	{/each}
</div>
