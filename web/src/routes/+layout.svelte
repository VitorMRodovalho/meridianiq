<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { auth, initAuth, signOut } from '$lib/auth';

	let { children } = $props();

	onMount(() => {
		initAuth();
	});
</script>

<div class="flex min-h-screen bg-gray-50">
	<!-- Sidebar -->
	<aside class="w-64 bg-gray-900 text-white flex flex-col shrink-0">
		<div class="px-6 py-5 border-b border-gray-700">
			<a href="/" class="block">
				<h1 class="text-lg font-bold tracking-tight">MeridianIQ</h1>
				<p class="text-xs text-gray-400 mt-0.5">Schedule Intelligence Platform</p>
			</a>
		</div>
		<nav class="flex-1 px-4 py-4 space-y-1">
			<a
				href="/"
				class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1" />
				</svg>
				Dashboard
			</a>
			<a
				href="/upload"
				class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
				</svg>
				Upload
			</a>
			<a
				href="/projects"
				class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
				</svg>
				Projects
			</a>
			<a
				href="/compare"
				class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
				</svg>
				Compare
			</a>
			<a
				href="/forensic"
				class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
				</svg>
				Forensic
			</a>
			<a
				href="/tia"
				class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
				</svg>
				TIA
			</a>
			<a
				href="/evm"
				class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
				</svg>
				EVM
			</a>
			<a
				href="/risk"
				class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
				</svg>
				Risk
			</a>
		</nav>

		<!-- User section -->
		<div class="px-4 py-4 border-t border-gray-700">
			{#if auth.loading}
				<div class="h-8 rounded bg-gray-700 animate-pulse"></div>
			{:else if auth.user}
				<div class="flex items-center gap-3 mb-3">
					{#if auth.user.user_metadata?.avatar_url}
						<img
							src={auth.user.user_metadata.avatar_url}
							alt="avatar"
							class="w-8 h-8 rounded-full object-cover"
						/>
					{:else}
						<div class="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-xs font-bold uppercase">
							{(auth.user.email ?? '?')[0]}
						</div>
					{/if}
					<div class="min-w-0 flex-1">
						<p class="text-xs font-medium text-gray-200 truncate">
							{auth.user.user_metadata?.full_name ?? auth.user.email ?? 'User'}
						</p>
						<p class="text-xs text-gray-500 truncate">{auth.user.email ?? ''}</p>
					</div>
				</div>
				<button
					onclick={signOut}
					class="w-full text-left px-3 py-1.5 rounded-md text-xs text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
				>
					Sign out
				</button>
			{:else}
				<a
					href="/login"
					class="block w-full text-center rounded-md bg-indigo-600 px-3 py-2 text-xs font-medium text-white hover:bg-indigo-500 transition-colors"
				>
					Sign in
				</a>
			{/if}
		</div>

		<div class="px-6 py-4 border-t border-gray-700">
			<p class="text-xs text-gray-500">MeridianIQ &middot; MIT License &middot; &copy; 2025 Vitor Maia Rodovalho</p>
			<p class="text-xs text-gray-500 mt-0.5">v0.7.0-dev</p>
		</div>
	</aside>

	<!-- Main content -->
	<main class="flex-1 overflow-auto">
		{@render children()}
	</main>
</div>
