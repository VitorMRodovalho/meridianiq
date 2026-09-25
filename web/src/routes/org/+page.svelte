<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getOrganizations,
		createOrganization,
		listInvitations,
		acceptInvitation,
		declineInvitation,
		ApiError,
		type Invitation,
		type OrganizationWithRole
	} from '$lib/api';
	import { t, locale } from '$lib/i18n';

	let orgs: OrganizationWithRole[] = $state([]);
	let loading = $state(true);
	let error = $state('');
	let showCreate = $state(false);
	let newName = $state('');
	let newType = $state('general');
	let creating = $state(false);
	let invitations: Invitation[] = $state([]);
	let answering = $state('');
	let invitationError = $state('');

	const orgTypeKeys: { value: string; labelKey: string }[] = [
		{ value: 'owner', labelKey: 'org.type_owner' },
		{ value: 'pm_firm', labelKey: 'org.type_pm_firm' },
		{ value: 'cm_firm', labelKey: 'org.type_cm_firm' },
		{ value: 'general_contractor', labelKey: 'org.type_general_contractor' },
		{ value: 'subcontractor', labelKey: 'org.type_subcontractor' },
		{ value: 'general', labelKey: 'org.type_general' },
	];

	onMount(async () => {
		try {
			const res = await getOrganizations();
			orgs = res.organizations;
		} catch {
			error = $t('org.load_failed');
		} finally {
			loading = false;
		}
		try {
			invitations = (await listInvitations()).invitations;
		} catch {
			// Invitations are secondary to the organization list: leave the panel hidden.
		}
	});

	async function answer(inv: Invitation, accept: boolean) {
		answering = inv.org_id;
		invitationError = '';
		try {
			if (accept) {
				const res = await acceptInvitation(inv.org_id, inv.role);
				const listed = await getOrganizations();
				orgs = listed.organizations;
				if (!orgs.some((o) => o.id === res.org_id)) invitationError = $t('org.invitation_failed');
			} else {
				await declineInvitation(inv.org_id);
			}
			invitations = invitations.filter((i) => i.org_id !== inv.org_id);
		} catch (e: unknown) {
			if (e instanceof ApiError && e.status === 404) {
				// Expired, re-issued for another role, or withdrawn: drop it from the list.
				invitations = invitations.filter((i) => i.org_id !== inv.org_id);
				invitationError = $t('org.invitation_gone');
			} else if (e instanceof ApiError && e.status === 429) {
				invitationError = $t('error.rate_limited');
			} else {
				invitationError = $t('org.invitation_failed');
			}
		} finally {
			answering = '';
		}
	}

	function formatDate(d: string | null): string {
		return d ? new Date(d).toLocaleDateString($locale) : '';
	}

	async function handleCreate() {
		if (!newName.trim()) return;
		creating = true;
		try {
			const res = await createOrganization(newName.trim(), newType);
			orgs = [...orgs, { ...res.organization, role: 'owner' }];
			showCreate = false;
			newName = '';
		} catch (e: unknown) {
			if (e instanceof ApiError && e.status === 422) error = $t('org.name_invalid');
			else if (e instanceof ApiError && e.status === 429) error = $t('error.rate_limited');
			else error = e instanceof Error ? e.message : $t('org.create_failed');
		} finally {
			creating = false;
		}
	}

	function roleColor(role: string): string {
		if (role === 'owner') return 'bg-purple-100 text-purple-800';
		if (role === 'admin') return 'bg-blue-100 text-blue-800';
		if (role === 'member') return 'bg-green-100 text-green-800';
		return 'bg-gray-100 dark:bg-gray-800 text-gray-800';
	}

	function typeLabel(type: string): string {
		const entry = orgTypeKeys.find(t => t.value === type);
		return entry ? $t(entry.labelKey) : type;
	}
</script>

<svelte:head>
	<title>{$t('nav.org')} - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-4xl mx-auto">
	<div class="flex items-center justify-between mb-8">
		<div>
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('nav.org')}</h1>
			<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{$t('org.page_subtitle')}</p>
		</div>
		<button
			onclick={() => showCreate = !showCreate}
			class="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
		>
			{$t('org.new_cta')}
		</button>
	</div>

	{#if error}
		<div class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg text-red-700 text-sm mb-6">{error}</div>
	{/if}

	{#if invitations.length > 0 || invitationError}
		<section
			class="bg-white dark:bg-gray-900 border border-blue-200 dark:border-blue-900 rounded-lg p-5 mb-6"
			aria-labelledby="invitations-title"
		>
			<h2 id="invitations-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100">
				{$t('org.invitations_title')}
			</h2>
			<p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5 mb-4">{$t('org.invitations_hint')}</p>
			{#if invitationError}
				<div role="alert" class="p-3 bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg text-red-700 text-sm mb-3">
					{invitationError}
				</div>
			{/if}
			<ul class="divide-y divide-gray-100 dark:divide-gray-800">
				{#each invitations as inv (inv.org_id)}
					<li class="flex flex-wrap items-center justify-between gap-3 py-3">
						<div class="min-w-0">
							<p class="font-medium text-gray-900 dark:text-gray-100 truncate">
								{inv.org_name ?? $t('org_detail.fallback_name')}
							</p>
							<p class="text-sm text-gray-500 dark:text-gray-400">
								{$t(`org_detail.role_${inv.role}`)}{#if inv.invited_at} · {$t('org.invited_on')} {formatDate(inv.invited_at)}{/if}
							</p>
						</div>
						<div class="flex gap-2">
							<button
								onclick={() => answer(inv, true)}
								disabled={answering !== ''}
								class="px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
							>
								{$t('org.btn_accept')}
							</button>
							<button
								onclick={() => answer(inv, false)}
								disabled={answering !== ''}
								class="px-3 py-1.5 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 text-sm font-medium rounded-lg hover:bg-gray-200 disabled:opacity-50 transition-colors"
							>
								{$t('org.btn_decline')}
							</button>
						</div>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	{#if showCreate}
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{$t('org.create_title')}</h2>
			<div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
				<label class="block">
					<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$t('org.field_name')}</span>
					<input
						type="text"
						maxlength="120"
						bind:value={newName}
						placeholder={$t('org.name_placeholder')}
						class="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
					/>
				</label>
				<label class="block">
					<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$t('org.field_type')}</span>
					<select
						bind:value={newType}
						class="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
					>
						{#each orgTypeKeys as ot}
							<option value={ot.value}>{$t(ot.labelKey)}</option>
						{/each}
					</select>
				</label>
			</div>
			<div class="flex gap-3">
				<button
					onclick={handleCreate}
					disabled={creating || !newName.trim()}
					class="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
				>
					{creating ? $t('org.btn_creating') : $t('org.btn_create')}
				</button>
				<button
					onclick={() => showCreate = false}
					class="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors"
				>
					{$t('org.btn_cancel')}
				</button>
			</div>
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400 py-12 justify-center">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			{$t('org.loading')}
		</div>
	{:else if orgs.length === 0}
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-8 text-center">
			<h3 class="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">{$t('org.empty_title')}</h3>
			<p class="text-sm text-gray-500 dark:text-gray-400 mb-4">{$t('org.empty_hint')}</p>
		</div>
	{:else}
		<div class="space-y-3">
			{#each orgs as org}
				<a
					href="/org/{org.id}"
					class="block bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-5 hover:border-blue-300 hover:shadow-md transition-all"
				>
					<div class="flex items-center justify-between">
						<div>
							<h3 class="font-semibold text-gray-900 dark:text-gray-100">{org.name}</h3>
							<p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{typeLabel(org.org_type)}</p>
						</div>
						<span class="px-2.5 py-0.5 text-xs font-medium rounded-full {roleColor(org.role)}">
							{org.role}
						</span>
					</div>
				</a>
			{/each}
		</div>
	{/if}
</div>
