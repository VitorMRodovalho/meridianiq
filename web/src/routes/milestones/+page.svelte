<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getProjects,
		getValueMilestones,
		createValueMilestone,
		updateValueMilestone,
		type ValueMilestone,
		type ValueMilestoneCreate
	} from '$lib/api';
	import { success, error as toastError } from '$lib/toast';
	import type { ProjectListItem } from '$lib/types';

	let projects: ProjectListItem[] = $state([]);
	let selectedProjectId = $state('');
	let milestones: ValueMilestone[] = $state([]);
	let loading = $state(true);
	let milestonesLoading = $state(false);
	let error = $state('');

	// Create form state
	let showForm = $state(false);
	let formData = $state({
		task_code: '',
		task_name: '',
		milestone_type: 'payment',
		commercial_value: 0,
		currency: 'USD',
		payment_trigger: '',
		contract_ref: '',
		notes: '',
		baseline_date: '',
		forecast_date: '',
	});
	let saving = $state(false);

	// Inline editing
	let editingId: string | null = $state(null);
	let editStatus = $state('');
	let editActualDate = $state('');

	onMount(async () => {
		try {
			const res = await getProjects();
			projects = res.projects;
			// Auto-select from URL query param
			const params = new URLSearchParams(window.location.search);
			const projParam = params.get('project');
			if (projParam && projects.some((p) => p.project_id === projParam)) {
				selectedProjectId = projParam;
				await loadMilestones();
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load projects';
		} finally {
			loading = false;
		}
	});

	async function loadMilestones() {
		if (!selectedProjectId) return;
		milestonesLoading = true;
		try {
			const res = await getValueMilestones(selectedProjectId);
			milestones = res.milestones;
		} catch (e: unknown) {
			toastError(e instanceof Error ? e.message : 'Failed to load milestones');
		} finally {
			milestonesLoading = false;
		}
	}

	async function handleProjectChange() {
		milestones = [];
		editingId = null;
		showForm = false;
		await loadMilestones();
	}

	async function handleCreate() {
		if (!formData.task_code.trim()) {
			toastError('Task code is required');
			return;
		}
		saving = true;
		try {
			const payload: ValueMilestoneCreate = {
				project_id: selectedProjectId,
				task_code: formData.task_code,
				task_name: formData.task_name,
				milestone_type: formData.milestone_type,
				commercial_value: formData.commercial_value,
				currency: formData.currency,
				payment_trigger: formData.payment_trigger,
				contract_ref: formData.contract_ref,
				notes: formData.notes,
			};
			if (formData.baseline_date) payload.baseline_date = formData.baseline_date;
			if (formData.forecast_date) payload.forecast_date = formData.forecast_date;

			await createValueMilestone(selectedProjectId, payload);
			success('Value milestone created');
			showForm = false;
			resetForm();
			await loadMilestones();
		} catch (e: unknown) {
			toastError(e instanceof Error ? e.message : 'Failed to create milestone');
		} finally {
			saving = false;
		}
	}

	function resetForm() {
		formData = {
			task_code: '',
			task_name: '',
			milestone_type: 'payment',
			commercial_value: 0,
			currency: 'USD',
			payment_trigger: '',
			contract_ref: '',
			notes: '',
			baseline_date: '',
			forecast_date: '',
		};
	}

	function startEdit(m: ValueMilestone) {
		editingId = m.id;
		editStatus = m.status || 'pending';
		editActualDate = m.actual_date ? m.actual_date.split('T')[0] : '';
	}

	async function saveEdit(id: string) {
		try {
			const updates: { status: string; actual_date?: string } = { status: editStatus };
			if (editActualDate) updates.actual_date = editActualDate;
			await updateValueMilestone(id, updates);
			success('Milestone updated');
			editingId = null;
			await loadMilestones();
		} catch (e: unknown) {
			toastError(e instanceof Error ? e.message : 'Failed to update milestone');
		}
	}

	function statusBadge(status: string): string {
		switch (status) {
			case 'achieved':
				return 'bg-green-100 text-green-700 border-green-300';
			case 'at_risk':
				return 'bg-yellow-100 text-yellow-700 border-yellow-300';
			case 'overdue':
				return 'bg-red-100 text-red-700 border-red-300';
			default:
				return 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-300 dark:border-gray-600';
		}
	}

	function formatCurrency(value: number, currency: string): string {
		return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(value);
	}

	function formatDate(d: string | null): string {
		if (!d) return '-';
		return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}

	const totalValue = $derived(milestones.reduce((sum, m) => sum + (m.commercial_value || 0), 0));
	const achievedValue = $derived(
		milestones.filter((m) => m.status === 'achieved').reduce((sum, m) => sum + (m.commercial_value || 0), 0)
	);
	const atRiskCount = $derived(milestones.filter((m) => m.status === 'at_risk' || m.status === 'overdue').length);
</script>

<svelte:head>
	<title>Value Milestones - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<div class="flex items-center justify-between mb-6">
		<div>
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Value Milestones</h1>
			<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">Link schedule milestones to commercial value, payment triggers, and contract references</p>
		</div>
		{#if selectedProjectId && !milestonesLoading}
			<button
				onclick={() => { showForm = !showForm; if (!showForm) resetForm(); }}
				class="px-4 py-2 text-sm font-medium rounded-lg transition-colors {showForm ? 'bg-gray-200 text-gray-700 dark:text-gray-300 hover:bg-gray-300' : 'bg-blue-600 text-white hover:bg-blue-700'}"
			>
				{showForm ? 'Cancel' : 'Add Milestone'}
			</button>
		{/if}
	</div>

	<!-- Project selector -->
	<div class="mb-6">
		<label for="project-select" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Project</label>
		<select
			id="project-select"
			bind:value={selectedProjectId}
			onchange={handleProjectChange}
			class="w-full max-w-md px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
		>
			<option value="">Select a project...</option>
			{#each projects as p}
				<option value={p.project_id}>{p.name || p.project_id}</option>
			{/each}
		</select>
	</div>

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			Loading...
		</div>
	{:else if !selectedProjectId}
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
			<p class="text-gray-500 dark:text-gray-400">Select a project to manage its value milestones.</p>
		</div>
	{:else if milestonesLoading}
		<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			Loading milestones...
		</div>
	{:else}
		<!-- Summary cards -->
		{#if milestones.length > 0}
			<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
					<p class="text-sm text-gray-500 dark:text-gray-400">Total Contract Value</p>
					<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{formatCurrency(totalValue, 'USD')}</p>
					<p class="text-xs text-gray-400 mt-1">{milestones.length} milestone{milestones.length !== 1 ? 's' : ''}</p>
				</div>
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
					<p class="text-sm text-gray-500 dark:text-gray-400">Achieved Value</p>
					<p class="text-2xl font-bold text-green-600">{formatCurrency(achievedValue, 'USD')}</p>
					<p class="text-xs text-gray-400 mt-1">{totalValue > 0 ? ((achievedValue / totalValue) * 100).toFixed(0) : 0}% earned</p>
				</div>
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
					<p class="text-sm text-gray-500 dark:text-gray-400">At Risk / Overdue</p>
					<p class="text-2xl font-bold {atRiskCount > 0 ? 'text-red-600' : 'text-green-600'}">{atRiskCount}</p>
					<p class="text-xs text-gray-400 mt-1">{atRiskCount === 0 ? 'All on track' : 'Requires attention'}</p>
				</div>
			</div>
		{/if}

		<!-- Create form -->
		{#if showForm}
			<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">New Value Milestone</h2>
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
					<div>
						<label for="task-code" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Task Code *</label>
						<input id="task-code" type="text" bind:value={formData.task_code} class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="e.g. A1020" />
					</div>
					<div>
						<label for="task-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Task Name</label>
						<input id="task-name" type="text" bind:value={formData.task_name} class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Substantial Completion" />
					</div>
					<div>
						<label for="milestone-type" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Type</label>
						<select id="milestone-type" bind:value={formData.milestone_type} class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
							<option value="payment">Payment</option>
							<option value="contractual">Contractual</option>
							<option value="regulatory">Regulatory</option>
							<option value="substantial_completion">Substantial Completion</option>
							<option value="final_completion">Final Completion</option>
						</select>
					</div>
					<div>
						<label for="commercial-value" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Commercial Value</label>
						<div class="flex gap-2">
							<input id="commercial-value" type="number" bind:value={formData.commercial_value} min="0" step="0.01" class="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
							<select bind:value={formData.currency} class="w-24 px-2 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
								<option value="USD">USD</option>
								<option value="EUR">EUR</option>
								<option value="GBP">GBP</option>
								<option value="BRL">BRL</option>
							</select>
						</div>
					</div>
					<div>
						<label for="payment-trigger" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Payment Trigger</label>
						<input id="payment-trigger" type="text" bind:value={formData.payment_trigger} class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="e.g. Certificate of Substantial Completion" />
					</div>
					<div>
						<label for="contract-ref" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Contract Reference</label>
						<input id="contract-ref" type="text" bind:value={formData.contract_ref} class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="e.g. AIA A201 §9.8.1" />
					</div>
					<div>
						<label for="baseline-date" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Baseline Date</label>
						<input id="baseline-date" type="date" bind:value={formData.baseline_date} class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
					</div>
					<div>
						<label for="forecast-date" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Forecast Date</label>
						<input id="forecast-date" type="date" bind:value={formData.forecast_date} class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
					</div>
					<div class="sm:col-span-2">
						<label for="notes" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Notes</label>
						<textarea id="notes" bind:value={formData.notes} rows="2" class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Additional context..."></textarea>
					</div>
				</div>
				<div class="mt-4 flex justify-end">
					<button
						onclick={handleCreate}
						disabled={saving}
						class="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
					>
						{saving ? 'Creating...' : 'Create Milestone'}
					</button>
				</div>
			</div>
		{/if}

		<!-- Milestones table -->
		{#if milestones.length === 0 && !showForm}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
				<p class="text-gray-500 dark:text-gray-400 mb-4">No value milestones defined for this project.</p>
				<button
					onclick={() => showForm = true}
					class="inline-block bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700"
				>
					Add First Milestone
				</button>
			</div>
		{:else if milestones.length > 0}
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Task</th>
								<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Type</th>
								<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Value</th>
								<th class="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Baseline</th>
								<th class="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Forecast</th>
								<th class="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Status</th>
								<th class="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Actions</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each milestones as m}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
									<td class="px-4 py-3">
										<div class="text-sm font-medium text-gray-900 dark:text-gray-100">{m.task_code}</div>
										{#if m.task_name}
											<div class="text-xs text-gray-400">{m.task_name}</div>
										{/if}
										{#if m.payment_trigger}
											<div class="text-xs text-gray-400 mt-0.5">Trigger: {m.payment_trigger}</div>
										{/if}
									</td>
									<td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 capitalize">{(m.milestone_type || 'payment').replace('_', ' ')}</td>
									<td class="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 text-right font-medium">{formatCurrency(m.commercial_value || 0, m.currency || 'USD')}</td>
									<td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 text-center">{formatDate(m.baseline_date)}</td>
									<td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 text-center">{formatDate(m.forecast_date)}</td>
									<td class="px-4 py-3 text-center">
										{#if editingId === m.id}
											<select bind:value={editStatus} class="text-xs px-2 py-1 border border-gray-300 dark:border-gray-600 rounded focus:outline-none focus:ring-1 focus:ring-blue-500">
												<option value="pending">Pending</option>
												<option value="at_risk">At Risk</option>
												<option value="achieved">Achieved</option>
												<option value="overdue">Overdue</option>
											</select>
										{:else}
											<span class="inline-flex px-2 py-0.5 text-xs font-medium rounded-full border {statusBadge(m.status || 'pending')}">
												{(m.status || 'pending').replace('_', ' ')}
											</span>
										{/if}
									</td>
									<td class="px-4 py-3 text-center">
										{#if editingId === m.id}
											<div class="flex items-center gap-1 justify-center">
												<input type="date" bind:value={editActualDate} class="text-xs px-1 py-0.5 border border-gray-300 dark:border-gray-600 rounded w-32" placeholder="Actual date" />
												<button onclick={() => saveEdit(m.id)} class="text-xs text-blue-600 hover:text-blue-800 font-medium">Save</button>
												<button onclick={() => editingId = null} class="text-xs text-gray-400 hover:text-gray-600 dark:text-gray-400">Cancel</button>
											</div>
										{:else}
											<button onclick={() => startEdit(m)} class="text-xs text-blue-600 hover:text-blue-800 font-medium">Edit</button>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	{/if}
</div>
