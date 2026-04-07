<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { getOrganization, inviteMember, removeMember, getAuditLog } from '$lib/api';

	const orgId = $derived(page.params.id!);
	let org: any = $state(null);
	let members: any[] = $state([]);
	let auditEntries: any[] = $state([]);
	let loading = $state(true);
	let error = $state('');
	let activeTab = $state('members');

	// Invite form
	let inviteEmail = $state('');
	let inviteRole = $state('member');
	let inviting = $state(false);
	let inviteError = $state('');
	let inviteSuccess = $state('');

	onMount(async () => {
		try {
			const res = await getOrganization(orgId);
			org = res.organization;
			members = res.members;
		} catch {
			error = 'Failed to load organization';
		} finally {
			loading = false;
		}
	});

	async function loadAudit() {
		try {
			const res = await getAuditLog(orgId);
			auditEntries = res.entries;
		} catch {
			// silently fail
		}
	}

	async function handleInvite() {
		if (!inviteEmail.trim()) return;
		inviting = true;
		inviteError = '';
		inviteSuccess = '';
		try {
			await inviteMember(orgId, inviteEmail.trim(), inviteRole);
			inviteSuccess = `Invited ${inviteEmail} as ${inviteRole}`;
			inviteEmail = '';
			// Reload members
			const res = await getOrganization(orgId);
			members = res.members;
		} catch (e: unknown) {
			inviteError = e instanceof Error ? e.message : 'Failed to invite';
		} finally {
			inviting = false;
		}
	}

	async function handleRemove(userId: string) {
		try {
			await removeMember(orgId, userId);
			members = members.filter(m => m.user_id !== userId);
		} catch {
			error = 'Failed to remove member';
		}
	}

	function roleColor(role: string): string {
		if (role === 'owner') return 'bg-purple-100 text-purple-800';
		if (role === 'admin') return 'bg-blue-100 text-blue-800';
		if (role === 'member') return 'bg-green-100 text-green-800';
		return 'bg-gray-100 dark:bg-gray-800 text-gray-800';
	}

	function actionLabel(action: string): string {
		const labels: Record<string, string> = {
			upload: 'Uploaded schedule',
			analyze: 'Ran analysis',
			share: 'Shared project',
			compare: 'Compared schedules',
			export: 'Exported data',
			invite: 'Invited member',
			remove_member: 'Removed member',
			create: 'Created',
			delete: 'Deleted',
		};
		return labels[action] || action;
	}

	function formatDate(d: string): string {
		return new Date(d).toLocaleString();
	}
</script>

<svelte:head>
	<title>{org?.name || 'Organization'} - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-5xl mx-auto">
	<div class="mb-6">
		<a href="/org" class="text-sm text-blue-600 hover:underline">Back to Organizations</a>
	</div>

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400 py-12 justify-center">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			Loading...
		</div>
	{:else if error}
		<div class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
	{:else if org}
		<div class="mb-6">
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{org.name}</h1>
			<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{org.org_type} &middot; {members.length} member{members.length !== 1 ? 's' : ''}</p>
		</div>

		<!-- Tabs -->
		<div class="border-b border-gray-200 dark:border-gray-700 mb-6">
			<nav class="flex gap-6 -mb-px">
				{#each [['members', 'Members'], ['invite', 'Invite'], ['audit', 'Audit Trail']] as [key, label]}
					<button
						class="pb-3 px-1 text-sm font-medium border-b-2 transition-colors {activeTab === key
							? 'border-blue-500 text-blue-600'
							: 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-300 hover:border-gray-300 dark:border-gray-600'}"
						onclick={() => { activeTab = key; if (key === 'audit') loadAudit(); }}
					>
						{label}
					</button>
				{/each}
			</nav>
		</div>

		{#if activeTab === 'members'}
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Member</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Role</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Joined</th>
							<th class="px-4 py-3"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each members as m}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
								<td class="px-4 py-3">
									<div class="flex items-center gap-3">
										{#if m.user_profiles?.avatar_url}
											<img src={m.user_profiles.avatar_url} alt="" class="w-8 h-8 rounded-full" />
										{:else}
											<div class="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-xs font-bold text-gray-600 dark:text-gray-400">
												{(m.user_profiles?.full_name || m.user_profiles?.email || '?')[0].toUpperCase()}
											</div>
										{/if}
										<div>
											<p class="text-sm font-medium text-gray-900 dark:text-gray-100">{m.user_profiles?.full_name || 'User'}</p>
											<p class="text-xs text-gray-500 dark:text-gray-400">{m.user_profiles?.email || ''}</p>
										</div>
									</div>
								</td>
								<td class="px-4 py-3">
									<span class="px-2 py-0.5 text-xs font-medium rounded-full {roleColor(m.role)}">{m.role}</span>
								</td>
								<td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
									{m.accepted_at ? formatDate(m.accepted_at) : 'Pending'}
								</td>
								<td class="px-4 py-3 text-right">
									{#if m.role !== 'owner'}
										<button
											onclick={() => handleRemove(m.user_id)}
											class="text-xs text-red-500 hover:text-red-700"
										>
											Remove
										</button>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

		{:else if activeTab === 'invite'}
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Invite Team Member</h2>
				{#if inviteError}
					<div class="p-3 bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg text-red-700 text-sm mb-4">{inviteError}</div>
				{/if}
				{#if inviteSuccess}
					<div class="p-3 bg-green-50 dark:bg-green-950 border border-green-200 rounded-lg text-green-700 text-sm mb-4">{inviteSuccess}</div>
				{/if}
				<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
					<label class="block sm:col-span-2">
						<span class="text-sm font-medium text-gray-700 dark:text-gray-300">Email Address</span>
						<input
							type="email"
							bind:value={inviteEmail}
							placeholder="colleague@company.com"
							class="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm"
						/>
					</label>
					<label class="block">
						<span class="text-sm font-medium text-gray-700 dark:text-gray-300">Role</span>
						<select bind:value={inviteRole} class="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm">
							<option value="viewer">Viewer</option>
							<option value="member">Member</option>
							<option value="admin">Admin</option>
						</select>
					</label>
				</div>
				<button
					onclick={handleInvite}
					disabled={inviting || !inviteEmail.trim()}
					class="px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
				>
					{inviting ? 'Inviting...' : 'Send Invite'}
				</button>
			</div>

		{:else if activeTab === 'audit'}
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
				{#if auditEntries.length === 0}
					<div class="p-8 text-center text-gray-500 dark:text-gray-400 text-sm">No audit entries yet.</div>
				{:else}
					<table class="min-w-full divide-y divide-gray-200">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">When</th>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Who</th>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Action</th>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Details</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each auditEntries as entry}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">{formatDate(entry.created_at)}</td>
									<td class="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">{entry.user_profiles?.full_name || entry.user_profiles?.email || 'System'}</td>
									<td class="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{actionLabel(entry.action)}</td>
									<td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 font-mono text-xs max-w-xs truncate">
										{entry.entity_type}
										{#if entry.details && Object.keys(entry.details).length > 0}
											— {JSON.stringify(entry.details).slice(0, 80)}
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/if}
			</div>
		{/if}
	{/if}
</div>
