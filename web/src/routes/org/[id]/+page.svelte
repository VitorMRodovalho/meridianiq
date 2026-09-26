<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { page } from '$app/state';
	import {
		getOrganization,
		inviteMember,
		removeMember,
		getAuditLog,
		revokeInvitation,
		ApiError,
		type Organization,
		type OrgMember,
		type AuditEntry
	} from '$lib/api';
	import { t, locale } from '$lib/i18n';

	const ACTION_KEYS: Record<string, string> = {
		upload: 'org_detail.action_upload',
		analyze: 'org_detail.action_analyze',
		share: 'org_detail.action_share',
		compare: 'org_detail.action_compare',
		export: 'org_detail.action_export',
		invite: 'org_detail.action_invite',
		invite_requested: 'org_detail.action_invite_requested',
		invite_revoked: 'org_detail.action_invite_revoked',
		accept_invite: 'org_detail.action_accept_invite',
		remove_member: 'org_detail.action_remove_member',
		create: 'org_detail.action_create',
		delete: 'org_detail.action_delete',
	};

	const orgId = $derived(page.params.id!);
	let org: Organization | null = $state(null);
	let members: OrgMember[] = $state([]);
	let auditEntries: AuditEntry[] = $state([]);
	let loading = $state(true);
	let error = $state('');
	let activeTab = $state('members');

	// Invite form
	let inviteEmail = $state('');
	let inviteRole = $state('member');
	let inviting = $state(false);
	let inviteError = $state('');
	let inviteSuccess = $state('');
	let removeError = $state('');
	let auditError = $state('');

	// Withdraw form
	let revokeEmail = $state('');
	let revoking = $state(false);
	let revokeError = $state('');
	let revokeDone = $state('');
	let auditLoading = $state(false);
	let inviteInput: HTMLInputElement | undefined = $state();
	let revokeInput: HTMLInputElement | undefined = $state();

	onMount(async () => {
		try {
			const res = await getOrganization(orgId);
			org = res.organization;
			members = res.members;
		} catch {
			error = $t('org_detail.load_failed');
		} finally {
			loading = false;
		}
	});

	async function loadAudit() {
		auditError = '';
		auditLoading = true;
		try {
			const res = await getAuditLog(orgId);
			auditEntries = res.entries;
		} catch (e: unknown) {
			auditEntries = [];
			auditError =
				e instanceof ApiError && e.status === 403
					? $t('org_detail.manager_only')
					: $t('org_detail.audit_load_failed');
		} finally {
			auditLoading = false;
		}
	}

	/** A localized message for the answers these actions can get, else `fallbackKey`. */
	function failureMessage(e: unknown, fallbackKey: string): string {
		if (e instanceof ApiError) {
			if (e.status === 422) return $t('org_detail.invite_invalid_email');
			if (e.status === 429) return $t('error.rate_limited');
			if (e.status === 403) return $t('org_detail.manager_only');
			if (e.status === 409) return $t('org_detail.last_owner');
		}
		return $t(fallbackKey);
	}

	async function handleInvite() {
		if (!inviteEmail.trim()) return;
		inviting = true;
		inviteError = '';
		inviteSuccess = '';
		try {
			const res = await inviteMember(orgId, inviteEmail.trim(), inviteRole);
			// The API records a request; it never says whether the address has an
			// account, so the message does not claim that anyone was added.
			inviteSuccess = `${$t('org_detail.invite_requested_prefix')} ${res.email} (${$t(`org_detail.role_${res.role}`)}).`;
			inviteEmail = '';
		} catch (e: unknown) {
			inviteError = failureMessage(e, 'org_detail.invite_failed');
		} finally {
			inviting = false;
			// The submit button is disabled while the request runs, which drops
			// focus; return it to the address field.
			await tick();
			inviteInput?.focus();
		}
	}

	async function handleRemove(userId: string) {
		removeError = '';
		try {
			await removeMember(orgId, userId);
			members = members.filter(m => m.user_id !== userId);
		} catch (e: unknown) {
			removeError = failureMessage(e, 'org_detail.remove_failed');
		}
	}

	async function handleRevoke() {
		if (!revokeEmail.trim()) return;
		revoking = true;
		revokeError = '';
		revokeDone = '';
		try {
			const res = await revokeInvitation(orgId, revokeEmail.trim());
			// The API answers the same whether or not there was an invitation.
			revokeDone = `${$t('org_detail.revoke_done_prefix')} ${res.email} ${$t('org_detail.revoke_done_suffix')}`;
			revokeEmail = '';
		} catch (e: unknown) {
			revokeError = failureMessage(e, 'org_detail.revoke_failed');
		} finally {
			revoking = false;
			await tick();
			revokeInput?.focus();
		}
	}

	function roleColor(role: string): string {
		if (role === 'owner') return 'bg-purple-100 text-purple-800';
		if (role === 'admin') return 'bg-blue-100 text-blue-800';
		if (role === 'member') return 'bg-green-100 text-green-800';
		return 'bg-gray-100 dark:bg-gray-800 text-gray-800';
	}

	function actionLabel(action: string): string {
		const key = ACTION_KEYS[action];
		return key ? $t(key) : action;
	}

	function formatDate(d: string): string {
		return new Date(d).toLocaleString($locale);
	}

	const tabs: [string, string][] = [
		['members', 'org_detail.tab_members'],
		['invite', 'org_detail.tab_invite'],
		['audit', 'org_detail.tab_audit'],
	];
</script>

<svelte:head>
	<title>{org?.name || $t('org_detail.fallback_name')} - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-5xl mx-auto">
	<div class="mb-6">
		<a href="/org" class="text-sm text-blue-600 hover:underline">{$t('org_detail.back_link')}</a>
	</div>

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400 py-12 justify-center">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			{$t('common.loading')}
		</div>
	{:else if error}
		<div role="alert" class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-200 text-sm">{error}</div>
	{:else if org}
		<div class="mb-6">
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{org.name}</h1>
			<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{org.org_type} &middot; {members.length} {members.length === 1 ? $t('org_detail.members_single') : $t('org_detail.members_plural')}</p>
		</div>

		<!-- Tabs -->
		<div class="border-b border-gray-200 dark:border-gray-700 mb-6">
			<nav class="flex gap-6 -mb-px">
				{#each tabs as [key, labelKey]}
					<button
						class="pb-3 px-1 text-sm font-medium border-b-2 transition-colors {activeTab === key
							? 'border-blue-500 text-blue-600'
							: 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-300 hover:border-gray-300 dark:border-gray-600'}"
						onclick={() => { activeTab = key; if (key === 'audit') loadAudit(); }}
					>
						{$t(labelKey)}
					</button>
				{/each}
			</nav>
		</div>

		{#if activeTab === 'members'}
			{#if removeError}
				<div role="alert" class="p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-200 text-sm mb-4">{removeError}</div>
			{/if}
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('org_detail.col_member')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('org_detail.col_role')}</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('org_detail.col_joined')}</th>
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
											<p class="text-sm font-medium text-gray-900 dark:text-gray-100">{m.user_profiles?.full_name || $t('sidebar.user_fallback')}</p>
											<p class="text-xs text-gray-500 dark:text-gray-400">{m.user_profiles?.email || ''}</p>
										</div>
									</div>
								</td>
								<td class="px-4 py-3">
									<span class="px-2 py-0.5 text-xs font-medium rounded-full {roleColor(m.role)}">{m.role}</span>
								</td>
								<td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
									{m.accepted_at ? formatDate(m.accepted_at) : $t('org_detail.status_pending')}
								</td>
								<td class="px-4 py-3 text-right">
									{#if m.role !== 'owner'}
										<button
											onclick={() => handleRemove(m.user_id)}
											class="text-xs text-red-500 hover:text-red-700"
										>
											{$t('org_detail.btn_remove')}
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
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{$t('org_detail.invite_title')}</h2>
				<p class="text-sm text-gray-500 dark:text-gray-400 -mt-2 mb-4">{$t('org_detail.invite_requested_note')}</p>
				{#if inviteError}
					<div role="alert" class="p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-200 text-sm mb-4">{inviteError}</div>
				{/if}
				<!-- The status region stays mounted so its updates are announced. -->
				<div role="status">
					{#if inviteSuccess}
						<div class="p-3 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg text-green-700 dark:text-green-200 text-sm mb-4">{inviteSuccess}</div>
					{/if}
				</div>
				<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
					<label class="block sm:col-span-2">
						<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$t('org_detail.field_email')}</span>
						<input
							type="email"
							maxlength="320"
							bind:this={inviteInput}
							bind:value={inviteEmail}
							placeholder={$t('org_detail.placeholder_email')}
							class="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm"
						/>
					</label>
					<label class="block">
						<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$t('org_detail.field_role')}</span>
						<select bind:value={inviteRole} class="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm">
							<option value="viewer">{$t('org_detail.role_viewer')}</option>
							<option value="member">{$t('org_detail.role_member')}</option>
							<option value="admin">{$t('org_detail.role_admin')}</option>
						</select>
					</label>
				</div>
				<button
					onclick={handleInvite}
					disabled={inviting || !inviteEmail.trim()}
					class="px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
				>
					{inviting ? $t('org_detail.btn_inviting') : $t('org_detail.btn_send_invite')}
				</button>
			</div>

			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mt-6">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{$t('org_detail.revoke_title')}</h2>
				<p class="text-sm text-gray-500 dark:text-gray-400 mt-1 mb-4">{$t('org_detail.revoke_hint')}</p>
				{#if revokeError}
					<div role="alert" class="p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-200 text-sm mb-4">{revokeError}</div>
				{/if}
				<div role="status">
					{#if revokeDone}
						<div class="p-3 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg text-green-700 dark:text-green-200 text-sm mb-4">{revokeDone}</div>
					{/if}
				</div>
				<div class="flex flex-wrap items-end gap-3">
					<label class="block w-full min-w-0 sm:w-auto sm:flex-1">
						<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$t('org_detail.field_email')}</span>
						<input
							type="email"
							maxlength="320"
							bind:this={revokeInput}
							bind:value={revokeEmail}
							placeholder={$t('org_detail.placeholder_email')}
							class="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm"
						/>
					</label>
					<button
						onclick={handleRevoke}
						disabled={revoking || !revokeEmail.trim()}
						class="px-6 py-2 bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 text-sm font-medium rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors"
					>
						{revoking ? $t('org_detail.btn_revoking') : $t('org_detail.btn_revoke')}
					</button>
				</div>
			</div>

		{:else if activeTab === 'audit'}
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-x-auto">
				{#if auditLoading}
					<div class="p-8 text-center text-gray-500 dark:text-gray-400 text-sm">{$t('common.loading')}</div>
				{:else if auditError}
					<div role="alert" class="m-4 p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-200 text-sm">{auditError}</div>
				{:else if auditEntries.length === 0}
					<div class="p-8 text-center text-gray-500 dark:text-gray-400 text-sm">{$t('org_detail.empty_audit')}</div>
				{:else}
					<table class="min-w-full divide-y divide-gray-200">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('org_detail.col_when')}</th>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('org_detail.col_who')}</th>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('org_detail.col_action')}</th>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{$t('org_detail.col_details')}</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each auditEntries as entry}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">{formatDate(entry.created_at)}</td>
									<td class="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">{entry.user_profiles?.full_name || entry.user_profiles?.email || (entry.user_id ? $t('org_detail.deleted_user') : $t('org_detail.system_user'))}</td>
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
