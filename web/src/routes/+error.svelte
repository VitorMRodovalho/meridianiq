<script lang="ts">
	import { page } from '$app/state';
	import { t } from '$lib/i18n';

	// The copy follows the status only. hooks.client.ts replaces every error's
	// message with a generic one (no internals in the UI), so a 404 used to show
	// "An unexpected error occurred" under "Page not found".
	const notFound = $derived(page.status === 404);
</script>

<svelte:head>
	<title>{page.status} - MeridianIQ</title>
</svelte:head>

<div class="flex items-center justify-center min-h-[60vh] px-4">
	<div class="text-center max-w-md">
		<p class="text-7xl font-bold text-gray-200 dark:text-gray-700">{page.status}</p>
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-4">
			{notFound ? $t('error_page.not_found_title') : $t('error_page.generic_title')}
		</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-2">
			{notFound ? $t('error_page.not_found_body') : $t('error_page.generic_body')}
		</p>
		<div class="flex items-center justify-center gap-3 mt-6">
			<a href="/" class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700">
				{$t('error_page.go_dashboard')}
			</a>
			<button onclick={() => history.back()} class="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-md text-sm font-medium hover:bg-gray-200 dark:hover:bg-gray-700">
				{$t('error_page.go_back')}
			</button>
		</div>
	</div>
</div>
