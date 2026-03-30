<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { user, isLoading, initAuth, signOut } from '$lib/auth';
	import { isWarmingUp, warmUp } from '$lib/api';
	import { initAnalytics } from '$lib/analytics';

	let { children } = $props();
	let sidebarOpen = $state(false);

	onMount(() => {
		initAuth();
		warmUp();
		initAnalytics();
	});

	function closeSidebar() {
		sidebarOpen = false;
	}

	const navLinks = [
		{ href: '/', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1' },
		{ href: '/upload', label: 'Upload', icon: 'M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12' },
		{ href: '/projects', label: 'Projects', icon: 'M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2' },
		{ href: '/compare', label: 'Compare', icon: 'M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4' },
		{ href: '/forensic', label: 'Forensic', icon: 'M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
		{ href: '/tia', label: 'TIA', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
		{ href: '/contract', label: 'Contract', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z' },
		{ href: '/evm', label: 'EVM', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
		{ href: '/risk', label: 'Risk', icon: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z' },
		{ href: '/org', label: 'Organizations', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z' },
		{ href: '/settings', label: 'Settings', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
	];
</script>

<div class="flex min-h-screen bg-gray-50">
	<!-- Mobile hamburger -->
	<button
		onclick={() => (sidebarOpen = true)}
		class="lg:hidden fixed top-4 left-4 z-40 p-2 rounded-md bg-gray-900 text-white shadow-lg"
		aria-label="Open menu"
	>
		<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
		</svg>
	</button>

	<!-- Mobile overlay -->
	{#if sidebarOpen}
		<button
			class="lg:hidden fixed inset-0 z-40 bg-black/50"
			onclick={closeSidebar}
			aria-label="Close menu"
		></button>
	{/if}

	<!-- Sidebar -->
	<aside class="
		fixed lg:sticky top-0 z-50 h-screen w-64 bg-gray-900 text-white flex flex-col shrink-0
		transition-transform duration-200 ease-in-out
		{sidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0
	">
		<div class="px-6 py-5 border-b border-gray-700 flex items-center justify-between">
			<a href="/" class="block" onclick={closeSidebar}>
				<h1 class="text-lg font-bold tracking-tight">MeridianIQ</h1>
				<p class="text-xs text-gray-400 mt-0.5">Schedule Intelligence Platform</p>
			</a>
			<button
				onclick={closeSidebar}
				class="lg:hidden p-1 rounded-md text-gray-400 hover:text-white hover:bg-gray-800"
				aria-label="Close menu"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
				</svg>
			</button>
		</div>
		<nav class="flex-1 px-4 py-4 space-y-1 overflow-y-auto">
			{#each navLinks as link}
				<a
					href={link.href}
					onclick={closeSidebar}
					class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
				>
					<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={link.icon} />
					</svg>
					{link.label}
				</a>
			{/each}
		</nav>

		<!-- User section -->
		<div class="px-4 py-4 border-t border-gray-700">
			{#if $isLoading}
				<div class="h-8 rounded bg-gray-700 animate-pulse"></div>
			{:else if $user}
				<div class="flex items-center gap-3 mb-3">
					{#if $user.user_metadata?.avatar_url}
						<img
							src={$user.user_metadata.avatar_url}
							alt="avatar"
							class="w-8 h-8 rounded-full object-cover"
						/>
					{:else}
						<div class="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-xs font-bold uppercase">
							{($user.email ?? '?')[0]}
						</div>
					{/if}
					<div class="min-w-0 flex-1">
						<p class="text-xs font-medium text-gray-200 truncate">
							{$user.user_metadata?.full_name ?? $user.email ?? 'User'}
						</p>
						<p class="text-xs text-gray-500 truncate">{$user.email ?? ''}</p>
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
					onclick={closeSidebar}
					class="block w-full text-center rounded-md bg-indigo-600 px-3 py-2 text-xs font-medium text-white hover:bg-indigo-500 transition-colors"
				>
					Sign in
				</a>
			{/if}
		</div>

		<div class="px-6 py-4 border-t border-gray-700">
			<a href="/docs" onclick={closeSidebar} class="text-xs text-gray-400 hover:text-white transition-colors">Documentation</a>
			<span class="text-xs text-gray-600 mx-1">&middot;</span>
			<a href="https://github.com/VitorMRodovalho/meridianiq" target="_blank" rel="noopener" class="text-xs text-gray-400 hover:text-white transition-colors">GitHub</a>
			<p class="text-xs text-gray-500 mt-2">MeridianIQ &middot; MIT &middot; &copy; 2025 Vitor Maia Rodovalho</p>
			<p class="text-xs text-gray-500 mt-0.5">v0.9.0</p>
		</div>
	</aside>

	<!-- Main content -->
	<main class="flex-1 overflow-auto min-w-0">
		{#if $isWarmingUp}
			<div class="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center gap-2 text-sm text-amber-800">
				<svg class="animate-spin h-4 w-4 text-amber-600 shrink-0" viewBox="0 0 24 24">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
				</svg>
				Warming up the analysis server... This takes a few seconds on first visit.
			</div>
		{/if}
		{@render children()}
	</main>
</div>
