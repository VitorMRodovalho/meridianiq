<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getProjects,
		getTIAAnalyses,
		createTIAAnalysis,
		getProject
	} from '$lib/api';
	import type {
		ProjectListItem,
		TIAAnalysisSummarySchema,
		TIAAnalysisSchema,
		DelayFragmentSchema,
		FragmentActivitySchema
	} from '$lib/types';

	let projects: ProjectListItem[] = $state([]);
	let analyses: TIAAnalysisSummarySchema[] = $state([]);
	let loading = $state(false);
	let projectsLoading = $state(true);
	let error = $state('');
	let showCreate = $state(false);

	// Form state
	let selectedProjectId = $state('');
	let fragments: DelayFragmentSchema[] = $state([]);
	let activityCodes: string[] = $state([]);

	const responsibleParties = [
		{ value: 'owner', label: 'Owner' },
		{ value: 'contractor', label: 'Contractor' },
		{ value: 'shared', label: 'Shared' },
		{ value: 'third_party', label: 'Third Party' },
		{ value: 'force_majeure', label: 'Force Majeure' }
	];

	onMount(async () => {
		try {
			const [projRes, tiaRes] = await Promise.all([getProjects(), getTIAAnalyses()]);
			projects = projRes.projects;
			analyses = tiaRes.analyses;
		} catch {
			error = 'Failed to load data';
		} finally {
			projectsLoading = false;
		}
	});

	async function onProjectChange() {
		if (!selectedProjectId) {
			activityCodes = [];
			return;
		}
		try {
			const detail = await getProject(selectedProjectId);
			activityCodes = detail.activities.map((a) => a.task_code).filter(Boolean);
		} catch {
			activityCodes = [];
		}
	}

	function addFragment() {
		const idx = fragments.length + 1;
		fragments = [
			...fragments,
			{
				fragment_id: `FRAG-${String(idx).padStart(3, '0')}`,
				name: '',
				description: '',
				responsible_party: 'contractor',
				activities: [
					{
						fragment_activity_id: `FRAG-${String(idx).padStart(3, '0')}-A`,
						name: '',
						duration_hours: 0,
						predecessors: [{ activity_code: '', rel_type: 'FS', lag_hours: 0 }],
						successors: [{ activity_code: '', rel_type: 'FS', lag_hours: 0 }]
					}
				]
			}
		];
	}

	function removeFragment(index: number) {
		fragments = fragments.filter((_, i) => i !== index);
	}

	async function doCreate() {
		if (!selectedProjectId || fragments.length === 0) {
			error = 'Select a project and add at least one fragment';
			return;
		}
		loading = true;
		error = '';
		try {
			const result: TIAAnalysisSchema = await createTIAAnalysis(
				selectedProjectId,
				fragments
			);
			window.location.href = `/tia/${result.analysis_id}`;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to create analysis';
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Time Impact Analysis - P6 XER Analytics</title>
</svelte:head>

<div class="p-8 max-w-7xl mx-auto">
	<div class="flex items-center justify-between mb-6">
		<div>
			<h1 class="text-2xl font-bold text-gray-900">Time Impact Analysis</h1>
			<p class="text-sm text-gray-500 mt-1">
				Prospective delay analysis per AACE RP 52R-06
			</p>
		</div>
		<button
			onclick={() => (showCreate = !showCreate)}
			class="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors"
		>
			{showCreate ? 'Cancel' : 'New Analysis'}
		</button>
	</div>

	{#if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700 mb-6">
			{error}
		</div>
	{/if}

	{#if showCreate}
		<div class="bg-white border border-gray-200 rounded-lg p-6 mb-6">
			<h2 class="text-lg font-semibold text-gray-900 mb-4">Create TIA Analysis</h2>
			<p class="text-sm text-gray-500 mb-4">
				Select a base schedule and define delay fragments. Each fragment represents a
				discrete delay event that will be inserted into the schedule network.
			</p>

			<!-- Project Selection -->
			<div class="mb-4">
				<label for="project" class="block text-sm font-medium text-gray-700 mb-1"
					>Base Schedule</label
				>
				{#if projectsLoading}
					<p class="text-gray-500 text-sm">Loading projects...</p>
				{:else}
					<select
						id="project"
						bind:value={selectedProjectId}
						onchange={onProjectChange}
						class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
					>
						<option value="">Select a project...</option>
						{#each projects as p}
							<option value={p.project_id}>{p.name || p.project_id} ({p.activity_count} activities)</option>
						{/each}
					</select>
				{/if}
			</div>

			<!-- Fragments -->
			<div class="mb-4">
				<div class="flex items-center justify-between mb-2">
					<label class="block text-sm font-medium text-gray-700">Delay Fragments</label>
					<button
						onclick={addFragment}
						class="text-sm text-blue-600 hover:text-blue-800 font-medium"
					>
						+ Add Fragment
					</button>
				</div>

				{#if fragments.length === 0}
					<p class="text-sm text-gray-400 italic">
						No fragments added. Click "+ Add Fragment" to begin.
					</p>
				{/if}

				{#each fragments as frag, fi}
					<div class="border border-gray-200 rounded-md p-4 mb-3 bg-gray-50">
						<div class="flex items-center justify-between mb-3">
							<span class="text-sm font-medium text-gray-800"
								>Fragment {fi + 1}: {frag.fragment_id}</span
							>
							<button
								onclick={() => removeFragment(fi)}
								class="text-xs text-red-500 hover:text-red-700"
							>
								Remove
							</button>
						</div>
						<div class="grid grid-cols-2 gap-3 mb-3">
							<div>
								<label class="block text-xs text-gray-500 mb-1">Name</label>
								<input
									type="text"
									bind:value={frag.name}
									placeholder="e.g., Permit Delay"
									class="w-full border border-gray-300 rounded px-2 py-1 text-sm"
								/>
							</div>
							<div>
								<label class="block text-xs text-gray-500 mb-1"
									>Responsible Party</label
								>
								<select
									bind:value={frag.responsible_party}
									class="w-full border border-gray-300 rounded px-2 py-1 text-sm"
								>
									{#each responsibleParties as rp}
										<option value={rp.value}>{rp.label}</option>
									{/each}
								</select>
							</div>
						</div>
						<div class="mb-3">
							<label class="block text-xs text-gray-500 mb-1">Description</label>
							<input
								type="text"
								bind:value={frag.description}
								placeholder="Description of the delay event"
								class="w-full border border-gray-300 rounded px-2 py-1 text-sm"
							/>
						</div>

						<!-- Activities within fragment -->
						{#each frag.activities as act, ai}
							<div class="bg-white border border-gray-200 rounded p-3 mb-2">
								<div class="text-xs font-medium text-gray-600 mb-2">
									Activity: {act.fragment_activity_id}
								</div>
								<div class="grid grid-cols-3 gap-2 mb-2">
									<div>
										<label class="block text-xs text-gray-500 mb-1"
											>Activity Name</label
										>
										<input
											type="text"
											bind:value={act.name}
											class="w-full border border-gray-300 rounded px-2 py-1 text-sm"
										/>
									</div>
									<div>
										<label class="block text-xs text-gray-500 mb-1"
											>Duration (hours)</label
										>
										<input
											type="number"
											bind:value={act.duration_hours}
											class="w-full border border-gray-300 rounded px-2 py-1 text-sm"
										/>
									</div>
									<div></div>
								</div>
								<div class="grid grid-cols-2 gap-2">
									<div>
										<label class="block text-xs text-gray-500 mb-1"
											>Predecessor Activity Code</label
										>
										{#if activityCodes.length > 0}
											<select
												bind:value={act.predecessors[0].activity_code}
												class="w-full border border-gray-300 rounded px-2 py-1 text-sm"
											>
												<option value="">Select...</option>
												{#each activityCodes as code}
													<option value={code}>{code}</option>
												{/each}
											</select>
										{:else}
											<input
												type="text"
												bind:value={act.predecessors[0].activity_code}
												placeholder="e.g., A3050"
												class="w-full border border-gray-300 rounded px-2 py-1 text-sm"
											/>
										{/if}
									</div>
									<div>
										<label class="block text-xs text-gray-500 mb-1"
											>Successor Activity Code</label
										>
										{#if activityCodes.length > 0}
											<select
												bind:value={act.successors[0].activity_code}
												class="w-full border border-gray-300 rounded px-2 py-1 text-sm"
											>
												<option value="">Select...</option>
												{#each activityCodes as code}
													<option value={code}>{code}</option>
												{/each}
											</select>
										{:else}
											<input
												type="text"
												bind:value={act.successors[0].activity_code}
												placeholder="e.g., A4010"
												class="w-full border border-gray-300 rounded px-2 py-1 text-sm"
											/>
										{/if}
									</div>
								</div>
							</div>
						{/each}
					</div>
				{/each}
			</div>

			<div class="flex items-center gap-4">
				<button
					onclick={doCreate}
					disabled={loading || !selectedProjectId || fragments.length === 0}
					class="bg-blue-600 text-white px-6 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
				>
					{loading ? 'Analyzing...' : `Analyze ${fragments.length} Fragments`}
				</button>
			</div>
		</div>
	{/if}

	<!-- Existing Analyses -->
	{#if analyses.length > 0}
		<div class="bg-white border border-gray-200 rounded-lg">
			<div class="px-6 py-4 border-b border-gray-200">
				<h2 class="text-lg font-semibold text-gray-900">TIA Analyses</h2>
			</div>
			<div class="overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200 text-sm">
					<thead class="bg-gray-50">
						<tr>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
								>Analysis</th
							>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
								>Project</th
							>
							<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase"
								>Fragments</th
							>
							<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase"
								>Owner Delay</th
							>
							<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase"
								>Contractor Delay</th
							>
							<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase"
								>Net Delay</th
							>
							<th class="px-4 py-3"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each analyses as a}
							<tr class="hover:bg-gray-50">
								<td class="px-4 py-3 font-mono text-gray-900">{a.analysis_id}</td>
								<td class="px-4 py-3 text-gray-700">{a.project_name}</td>
								<td class="px-4 py-3 text-right text-gray-500"
									>{a.fragment_count}</td
								>
								<td class="px-4 py-3 text-right text-blue-600"
									>{a.total_owner_delay.toFixed(1)}d</td
								>
								<td class="px-4 py-3 text-right text-red-600"
									>{a.total_contractor_delay.toFixed(1)}d</td
								>
								<td
									class="px-4 py-3 text-right font-medium {a.net_delay > 0
										? 'text-red-600'
										: 'text-gray-500'}"
								>
									{a.net_delay > 0 ? '+' : ''}{a.net_delay.toFixed(1)}d
								</td>
								<td class="px-4 py-3 text-right">
									<a
										href="/tia/{a.analysis_id}"
										class="text-blue-600 hover:underline text-sm"
									>
										View
									</a>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{:else if !projectsLoading && !showCreate}
		<div class="bg-white border border-gray-200 rounded-lg p-12 text-center">
			<svg
				class="mx-auto h-12 w-12 text-gray-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			<h3 class="mt-2 text-sm font-medium text-gray-900">No TIA analyses yet</h3>
			<p class="mt-1 text-sm text-gray-500">
				Click "New Analysis" to create your first Time Impact Analysis.
			</p>
		</div>
	{/if}
</div>
