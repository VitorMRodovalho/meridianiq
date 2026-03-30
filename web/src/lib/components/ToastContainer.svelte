<script lang="ts">
	import { toasts, dismiss } from '$lib/toast';

	function iconColor(type: string): string {
		if (type === 'success') return 'text-green-500';
		if (type === 'error') return 'text-red-500';
		if (type === 'warning') return 'text-yellow-500';
		return 'text-blue-500';
	}

	function bgColor(type: string): string {
		if (type === 'success') return 'bg-green-50 border-green-200';
		if (type === 'error') return 'bg-red-50 border-red-200';
		if (type === 'warning') return 'bg-yellow-50 border-yellow-200';
		return 'bg-blue-50 border-blue-200';
	}
</script>

<div class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
	{#each $toasts as t (t.id)}
		<div
			class="flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg {bgColor(t.type)} animate-slide-in"
			role="alert"
		>
			<svg class="w-5 h-5 shrink-0 mt-0.5 {iconColor(t.type)}" fill="currentColor" viewBox="0 0 20 20">
				{#if t.type === 'success'}
					<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
				{:else if t.type === 'error'}
					<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
				{:else if t.type === 'warning'}
					<path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
				{:else}
					<path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
				{/if}
			</svg>
			<p class="text-sm text-gray-800 flex-1">{t.message}</p>
			<button onclick={() => dismiss(t.id)} aria-label="Dismiss" class="text-gray-400 hover:text-gray-600 shrink-0">
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
				</svg>
			</button>
		</div>
	{/each}
</div>

<style>
	@keyframes slide-in {
		from { transform: translateX(100%); opacity: 0; }
		to { transform: translateX(0); opacity: 1; }
	}
	.animate-slide-in {
		animation: slide-in 0.2s ease-out;
	}
</style>
