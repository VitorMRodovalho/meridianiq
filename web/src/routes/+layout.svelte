<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { user, isLoading, initAuth, signOut } from '$lib/auth';
	import { isWarmingUp, warmUp } from '$lib/api';
	import { initAnalytics } from '$lib/analytics';
	import { isDark, toggleTheme, initTheme } from '$lib/stores/theme';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import ToastContainer from '$lib/components/ToastContainer.svelte';
	import { t, locale, detectLocale, availableLocales } from '$lib/i18n';

	import { browser } from '$app/environment';
	import { page } from '$app/stores';

	let { children } = $props();
	let sidebarOpen = $state(false);
	let showShortcuts = $state(false);
	let sidebarSearch = $state('');

	const filteredNavSections = $derived.by(() => {
		if (!sidebarSearch.trim()) return navSections;
		const q = sidebarSearch.toLowerCase();
		return navSections.map(section => ({
			...section,
			items: section.items.filter(item => item.label.toLowerCase().includes(q)),
		})).filter(section => section.items.length > 0 || !section.title);
	});

	// Collapsible sidebar sections — persist state in localStorage
	let collapsed: Record<string, boolean> = $state(
		browser ? JSON.parse(localStorage.getItem('meridianiq-sidebar-collapsed') || '{}') : {}
	);

	function toggleSection(title: string) {
		collapsed[title] = !collapsed[title];
		collapsed = { ...collapsed };
		if (browser) localStorage.setItem('meridianiq-sidebar-collapsed', JSON.stringify(collapsed));
	}

	onMount(() => {
		initAuth();
		warmUp();
		initAnalytics();
		initTheme();
		locale.set(detectLocale());

		function handleKeydown(e: KeyboardEvent) {
			if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
				e.preventDefault();
				toggleTheme();
			} else if (e.key === '/' && !e.ctrlKey && !e.metaKey && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement) && !(e.target instanceof HTMLSelectElement)) {
				e.preventDefault();
				const searchInput = document.querySelector('aside input[type="text"]') as HTMLInputElement;
				if (searchInput) searchInput.focus();
			} else if (e.key === '?' && !e.ctrlKey && !e.metaKey && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement) && !(e.target instanceof HTMLSelectElement)) {
				showShortcuts = !showShortcuts;
			} else if (e.key === 'Escape' && showShortcuts) {
				showShortcuts = false;
			}
		}
		document.addEventListener('keydown', handleKeydown);
		return () => document.removeEventListener('keydown', handleKeydown);
	});

	function closeSidebar() {
		sidebarOpen = false;
	}

	interface NavItem { href: string; label: string; icon: string; auth?: boolean; }
	interface NavSection { title: string; items: NavItem[]; auth?: boolean; }

	const navSections: NavSection[] = [
		{
			title: '',
			items: [
				{ href: '/', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1' },
				{ href: '/upload', label: 'Upload', icon: 'M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12' },
				{ href: '/projects', label: 'Projects', icon: 'M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2' },
				{ href: '/demo', label: 'Demo', icon: 'M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z' },
			],
		},
		{
			title: 'Schedule', auth: true,
			items: [
				{ href: '/schedule', label: 'Gantt Viewer', icon: 'M4 6h16M4 10h16M4 14h16M4 18h16' },
				{ href: '/compare', label: 'Compare', icon: 'M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4' },
				{ href: '/lookahead', label: 'Look-Ahead', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' },
				{ href: '/calendar-validation', label: 'Calendars', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' },
				{ href: '/float-trends', label: 'Float Trends', icon: 'M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z' },
				{ href: '/trends', label: 'Schedule Trends', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
			],
		},
		{
			title: 'Claims & Forensic', auth: true,
			items: [
				{ href: '/forensic', label: 'Forensic CPA', icon: 'M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
				{ href: '/tia', label: 'TIA', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
				{ href: '/delay-attribution', label: 'Delay Attribution', icon: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z' },
				{ href: '/root-cause', label: 'Root Cause', icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7' },
				{ href: '/narrative', label: 'Narrative Report', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
			],
		},
		{
			title: 'Risk & Controls', auth: true,
			items: [
				{ href: '/scorecard', label: 'Scorecard', icon: 'M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z' },
				{ href: '/evm', label: 'EVM', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
				{ href: '/risk', label: 'Monte Carlo', icon: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z' },
				{ href: '/risk-register', label: 'Risk Register', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
				{ href: '/contract', label: 'Contract', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z' },
				{ href: '/anomalies', label: 'Anomalies', icon: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
				{ href: '/cashflow', label: 'Cash Flow', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
			],
		},
		{
			title: 'Prediction & AI', auth: true,
			items: [
				{ href: '/whatif', label: 'What-If', icon: 'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
				{ href: '/delay-prediction', label: 'Delay Prediction', icon: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
				{ href: '/duration-prediction', label: 'Duration ML', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
				{ href: '/benchmarks', label: 'Benchmarks', icon: 'M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3' },
				{ href: '/optimizer', label: 'Optimizer', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
				{ href: '/resources', label: 'Resources', icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10' },
				{ href: '/builder', label: 'Schedule Builder', icon: 'M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4' },
				{ href: '/visualization', label: '4D Visualization', icon: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z' },
			],
		},
		{
			title: 'Enterprise', auth: true,
			items: [
				{ href: '/programs', label: 'Programs', icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10' },
				{ href: '/reports', label: 'Reports', icon: 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z' },
				{ href: '/ips', label: 'IPS Reconcile', icon: 'M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2' },
				{ href: '/recovery', label: 'Recovery', icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15' },
				{ href: '/milestones', label: 'Value Milestones', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
				{ href: '/org', label: 'Organizations', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z' },
			],
		},
		{
			title: '',
			items: [
				{ href: '/settings', label: 'Settings', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
			],
		},
	];
</script>

<a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:z-[60] focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded-md focus:text-sm">
	Skip to content
</a>
<div class="flex min-h-screen bg-gray-50 dark:bg-gray-950">
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
		<!-- Sidebar search -->
		<div class="px-4 pt-3 pb-1">
			<input
				type="text"
				bind:value={sidebarSearch}
				placeholder="Search pages..."
				class="w-full bg-gray-800 text-gray-300 text-xs rounded-md border border-gray-700 px-3 py-1.5 placeholder-gray-500 focus:outline-none focus:border-gray-500"
			/>
		</div>
		<nav class="flex-1 px-4 py-1 overflow-y-auto">
			{#each filteredNavSections as section, si}
				{#if section.auth && !$user}
					<!-- Hidden: requires authentication -->
				{:else}
				{#if section.title}
					<button
						onclick={() => toggleSection(section.title)}
						class="w-full flex items-center justify-between px-3 pt-4 pb-1 group"
					>
						<span class="text-xs font-semibold text-gray-500 uppercase tracking-wider">{section.title}</span>
						<svg
							class="w-3 h-3 text-gray-500 transition-transform {collapsed[section.title] ? '-rotate-90' : ''}"
							fill="none" stroke="currentColor" viewBox="0 0 24 24"
						>
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
						</svg>
					</button>
				{:else if si > 0}
					<div class="my-2 border-t border-gray-700"></div>
				{/if}
				{#if !section.title || !collapsed[section.title]}
				<div class="space-y-0.5">
					{#each section.items as link}
						{@const isActive = $page.url.pathname === link.href || ($page.url.pathname.startsWith(link.href + '/') && link.href !== '/')}
						<a
							href={link.href}
							onclick={closeSidebar}
							class="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors {isActive
								? 'bg-blue-600 text-white'
								: 'text-gray-300 hover:bg-gray-800 hover:text-white'}"
							aria-current={isActive ? 'page' : undefined}
						>
							<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={link.icon} />
							</svg>
							{link.label}
						</a>
					{/each}
				</div>
				{/if}
				{/if}
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
					{$t('common.sign_out')}
				</button>
			{:else}
				<a
					href="/login"
					onclick={closeSidebar}
					class="block w-full text-center rounded-md bg-indigo-600 px-3 py-2 text-xs font-medium text-white hover:bg-indigo-500 transition-colors"
				>
					{$t('common.sign_in')}
				</a>
			{/if}
		</div>

		<div class="px-6 py-4 border-t border-gray-700">
			<div class="flex items-center gap-2 mb-3">
				<select
					class="bg-gray-800 text-gray-300 text-xs rounded px-2 py-1 border border-gray-600 focus:outline-none focus:border-gray-400"
					onchange={(e) => locale.set((e.target as HTMLSelectElement).value as import('$lib/i18n').Locale)}
				>
					{#each availableLocales as loc}
						<option value={loc.code} selected={loc.code === $locale}>{loc.label}</option>
					{/each}
				</select>
				<button
					onclick={toggleTheme}
					class="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
					aria-label="Toggle dark mode"
					title={$isDark ? 'Switch to light mode' : 'Switch to dark mode'}
				>
					{#if $isDark}
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
						</svg>
					{:else}
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
						</svg>
					{/if}
				</button>
			</div>
			<a href="/docs" onclick={closeSidebar} class="text-xs text-gray-400 hover:text-white transition-colors">Documentation</a>
			<span class="text-xs text-gray-600 mx-1">&middot;</span>
			<a href="https://github.com/VitorMRodovalho/meridianiq" target="_blank" rel="noopener" class="text-xs text-gray-400 hover:text-white transition-colors">GitHub</a>
			<p class="text-xs text-gray-500 mt-2">MeridianIQ &middot; MIT &middot; &copy; 2025 Vitor Maia Rodovalho</p>
			<p class="text-xs text-gray-500 mt-0.5">v3.2.0</p>
		</div>
	</aside>

	<!-- Main content -->
	<main id="main-content" class="flex-1 overflow-auto min-w-0 dark:text-gray-100">
		{#if $isWarmingUp}
			<div class="bg-amber-50 dark:bg-amber-950 border-b border-amber-200 dark:border-amber-800 px-4 py-2 flex items-center gap-2 text-sm text-amber-800 dark:text-amber-200">
				<svg class="animate-spin h-4 w-4 text-amber-600 shrink-0" viewBox="0 0 24 24">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
				</svg>
				{$t('warmup.message')}
			</div>
		{/if}
		<Breadcrumb />
		<svelte:boundary>
			{@render children()}
			{#snippet failed(error, reset)}
				<div class="max-w-2xl mx-auto px-4 py-16 text-center">
					<div class="w-16 h-16 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center mx-auto mb-4">
						<svg class="w-8 h-8 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
						</svg>
					</div>
					<h2 class="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">Something went wrong</h2>
					<p class="text-sm text-gray-600 dark:text-gray-400 mb-4">{(error as any)?.message || 'An unexpected error occurred'}</p>
					<div class="flex items-center justify-center gap-3">
						<button onclick={reset} class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700">
							Try Again
						</button>
						<a href="/" class="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-md text-sm font-medium hover:bg-gray-200 dark:hover:bg-gray-700">
							Go Home
						</a>
					</div>
				</div>
			{/snippet}
		</svelte:boundary>
	</main>
	<ToastContainer />

	<!-- Keyboard shortcuts modal -->
	{#if showShortcuts}
		<div class="fixed inset-0 z-[60] bg-black/50 flex items-center justify-center" onclick={() => showShortcuts = false} role="dialog" aria-label="Keyboard shortcuts">
			<div class="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 p-6 max-w-md w-full mx-4" onclick={(e) => e.stopPropagation()}>
				<div class="flex items-center justify-between mb-4">
					<h2 class="text-lg font-bold text-gray-900 dark:text-gray-100">Keyboard Shortcuts</h2>
					<button onclick={() => showShortcuts = false} class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" aria-label="Close">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
					</button>
				</div>
				<div class="space-y-3 text-sm">
					<p class="text-xs text-gray-500 uppercase font-semibold">Global</p>
					<div class="flex justify-between"><span class="text-gray-600 dark:text-gray-400">Toggle dark mode</span><kbd class="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-xs font-mono">Ctrl+D</kbd></div>
					<div class="flex justify-between"><span class="text-gray-600 dark:text-gray-400">Search sidebar</span><kbd class="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-xs font-mono">/</kbd></div>
					<div class="flex justify-between"><span class="text-gray-600 dark:text-gray-400">Show shortcuts</span><kbd class="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-xs font-mono">?</kbd></div>
					<div class="flex justify-between"><span class="text-gray-600 dark:text-gray-400">Close modal</span><kbd class="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-xs font-mono">Esc</kbd></div>
					<div class="border-t border-gray-100 dark:border-gray-800 pt-3 mt-3">
						<p class="text-xs text-gray-500 uppercase font-semibold">Schedule Viewer</p>
					</div>
					<div class="flex justify-between"><span class="text-gray-600 dark:text-gray-400">Zoom in</span><kbd class="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-xs font-mono">+</kbd></div>
					<div class="flex justify-between"><span class="text-gray-600 dark:text-gray-400">Zoom out</span><kbd class="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-xs font-mono">-</kbd></div>
					<div class="flex justify-between"><span class="text-gray-600 dark:text-gray-400">Expand all WBS</span><kbd class="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-xs font-mono">E</kbd></div>
					<div class="flex justify-between"><span class="text-gray-600 dark:text-gray-400">Collapse all WBS</span><kbd class="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-xs font-mono">C</kbd></div>
				</div>
			</div>
		</div>
	{/if}
</div>
