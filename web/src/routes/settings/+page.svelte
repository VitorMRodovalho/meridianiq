<script lang="ts">
	import { user } from '$lib/auth';
	import { getProjects, getPrograms } from '$lib/api';

	let stats = $state({ projects: 0, programs: 0 });
	let statsLoaded = $state(false);

	async function loadStats() {
		try {
			const [projRes, progRes] = await Promise.all([
				getProjects().catch(() => ({ projects: [] })),
				getPrograms().catch(() => ({ programs: [] }))
			]);
			stats = {
				projects: projRes.projects.length,
				programs: progRes.programs.length
			};
		} catch {
			// silently fail
		} finally {
			statsLoaded = true;
		}
	}

	$effect(() => {
		if ($user) loadStats();
	});

	function getInitials(name: string | undefined, email: string | undefined): string {
		if (name) {
			return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
		}
		return (email ?? '?')[0].toUpperCase();
	}

	function formatDate(dateStr: string | undefined): string {
		if (!dateStr) return 'Unknown';
		return new Date(dateStr).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
	}

	function getProvider(user: any): string {
		const provider = user?.app_metadata?.provider;
		if (provider === 'google') return 'Google';
		if (provider === 'azure') return 'Microsoft';
		if (provider === 'linkedin_oidc') return 'LinkedIn';
		return provider ?? 'Unknown';
	}
</script>

<svelte:head>
	<title>Account Settings - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-3xl mx-auto">
	<h1 class="text-2xl font-bold text-gray-900 mb-8">Account Settings</h1>

	{#if !$user}
		<div class="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
			<p class="text-yellow-800">You need to be signed in to view account settings.</p>
			<a href="/login" class="mt-4 inline-block px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors">
				Sign in
			</a>
		</div>
	{:else}
		<!-- Profile Card -->
		<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
			<h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Profile</h2>
			<div class="flex items-center gap-5">
				{#if $user.user_metadata?.avatar_url}
					<img
						src={$user.user_metadata.avatar_url}
						alt="Profile"
						class="w-16 h-16 rounded-full object-cover border-2 border-gray-200"
					/>
				{:else}
					<div class="w-16 h-16 rounded-full bg-indigo-500 flex items-center justify-center text-xl font-bold text-white">
						{getInitials($user.user_metadata?.full_name, $user.email)}
					</div>
				{/if}
				<div>
					<p class="text-lg font-semibold text-gray-900">
						{$user.user_metadata?.full_name ?? 'User'}
					</p>
					<p class="text-sm text-gray-500">{$user.email ?? ''}</p>
					<div class="mt-2 flex items-center gap-2">
						<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
							{getProvider($user)}
						</span>
						<span class="text-xs text-gray-400">
							Member since {formatDate($user.created_at)}
						</span>
					</div>
				</div>
			</div>
		</div>

		<!-- Usage Stats -->
		<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
			<h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Usage</h2>
			{#if statsLoaded}
				<div class="grid grid-cols-2 gap-6">
					<div>
						<p class="text-3xl font-bold text-gray-900">{stats.projects}</p>
						<p class="text-sm text-gray-500 mt-1">Uploaded Schedules</p>
					</div>
					<div>
						<p class="text-3xl font-bold text-gray-900">{stats.programs}</p>
						<p class="text-sm text-gray-500 mt-1">Programs</p>
					</div>
				</div>
			{:else}
				<div class="h-16 flex items-center">
					<div class="h-4 w-32 bg-gray-100 rounded animate-pulse"></div>
				</div>
			{/if}
		</div>

		<!-- Account Info -->
		<div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
			<h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Account Details</h2>
			<dl class="space-y-4 text-sm">
				<div class="flex justify-between">
					<dt class="text-gray-500">User ID</dt>
					<dd class="font-mono text-gray-700 text-xs">{$user.id}</dd>
				</div>
				<div class="flex justify-between">
					<dt class="text-gray-500">Email</dt>
					<dd class="text-gray-900">{$user.email}</dd>
				</div>
				<div class="flex justify-between">
					<dt class="text-gray-500">Auth Provider</dt>
					<dd class="text-gray-900">{getProvider($user)}</dd>
				</div>
				<div class="flex justify-between">
					<dt class="text-gray-500">Last Sign In</dt>
					<dd class="text-gray-900">{formatDate($user.last_sign_in_at)}</dd>
				</div>
			</dl>
		</div>

		<!-- Data & Privacy -->
		<div class="bg-white rounded-lg border border-gray-200 p-6">
			<h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Data & Privacy</h2>
			<ul class="space-y-3 text-sm text-gray-600">
				<li class="flex items-start gap-2">
					<svg class="w-5 h-5 text-green-500 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
						<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
					</svg>
					Your data is stored in an isolated Supabase instance with Row Level Security (RLS). Other users cannot access your schedules.
				</li>
				<li class="flex items-start gap-2">
					<svg class="w-5 h-5 text-green-500 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
						<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
					</svg>
					XER files are stored in encrypted Supabase Storage buckets with per-user access policies.
				</li>
				<li class="flex items-start gap-2">
					<svg class="w-5 h-5 text-green-500 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
						<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
					</svg>
					All analysis is performed server-side. No schedule data is sent to third parties.
				</li>
				<li class="flex items-start gap-2">
					<svg class="w-5 h-5 text-green-500 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
						<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
					</svg>
					MeridianIQ is open-source (MIT). You can audit the entire codebase.
				</li>
			</ul>
		</div>
	{/if}
</div>
