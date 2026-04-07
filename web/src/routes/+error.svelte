<script lang="ts">
	import { page } from '$app/stores';
</script>

<svelte:head>
	<title>{$page.status} - MeridianIQ</title>
</svelte:head>

<div class="flex items-center justify-center min-h-[60vh] px-4">
	<div class="text-center max-w-md">
		<p class="text-7xl font-bold text-gray-200 dark:text-gray-700">{$page.status}</p>
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-4">
			{#if $page.status === 404}
				Page not found
			{:else}
				Something went wrong
			{/if}
		</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-2">
			{#if $page.error?.message}
				{$page.error.message}
			{:else if $page.status === 404}
				The page you're looking for doesn't exist or has been moved.
			{:else}
				An unexpected error occurred. Please try again.
			{/if}
		</p>
		<div class="flex items-center justify-center gap-3 mt-6">
			<a href="/" class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700">
				Go to Dashboard
			</a>
			<button onclick={() => history.back()} class="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-md text-sm font-medium hover:bg-gray-200 dark:hover:bg-gray-700">
				Go Back
			</button>
		</div>
	</div>
</div>
