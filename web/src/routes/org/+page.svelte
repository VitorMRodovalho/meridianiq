<script lang="ts">
	import { onMount } from 'svelte';
	import { getOrganizations, createOrganization } from '$lib/api';

	let orgs: any[] = $state([]);
	let loading = $state(true);
	let error = $state('');
	let showCreate = $state(false);
	let newName = $state('');
	let newType = $state('general');
	let creating = $state(false);

	const orgTypes = [
		{ value: 'owner', label: 'Owner / Developer' },
		{ value: 'pm_firm', label: 'PM / Cost Consultancy' },
		{ value: 'cm_firm', label: 'CM Firm' },
		{ value: 'general_contractor', label: 'General Contractor' },
		{ value: 'subcontractor', label: 'Subcontractor' },
		{ value: 'general', label: 'Other' },
	];

	onMount(async () => {
		try {
			const res = await getOrganizations();
			orgs = res.organizations;
		} catch {
			error = 'Failed to load organizations';
		} finally {
			loading = false;
		}
	});

	async function handleCreate() {
		if (!newName.trim()) return;
		creating = true;
		try {
			const res = await createOrganization(newName.trim(), newType);
			orgs = [...orgs, { ...res.organization, role: 'owner' }];
			showCreate = false;
			newName = '';
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to create';
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
		return orgTypes.find(t => t.value === type)?.label || type;
	}
</script>

<svelte:head>
	<title>Organizations - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-4xl mx-auto">
	<div class="flex items-center justify-between mb-8">
		<div>
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Organizations</h1>
			<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">Manage your teams and project sharing</p>
		</div>
		<button
			onclick={() => showCreate = !showCreate}
			class="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
		>
			+ New Organization
		</button>
	</div>

	{#if error}
		<div class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg text-red-700 text-sm mb-6">{error}</div>
	{/if}

	{#if showCreate}
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Create Organization</h2>
			<div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
				<label class="block">
					<span class="text-sm font-medium text-gray-700 dark:text-gray-300">Organization Name</span>
					<input
						type="text"
						bind:value={newName}
						placeholder="e.g., Turner Construction"
						class="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
					/>
				</label>
				<label class="block">
					<span class="text-sm font-medium text-gray-700 dark:text-gray-300">Type</span>
					<select
						bind:value={newType}
						class="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
					>
						{#each orgTypes as t}
							<option value={t.value}>{t.label}</option>
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
					{creating ? 'Creating...' : 'Create'}
				</button>
				<button
					onclick={() => showCreate = false}
					class="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors"
				>
					Cancel
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
			Loading organizations...
		</div>
	{:else if orgs.length === 0}
		<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-8 text-center">
			<h3 class="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No organizations yet</h3>
			<p class="text-sm text-gray-500 dark:text-gray-400 mb-4">Create an organization to start collaborating with your team.</p>
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
