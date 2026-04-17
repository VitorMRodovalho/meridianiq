<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getProjects,
		getCostSnapshots,
		type CostSnapshotSummary
	} from '$lib/api';
	import AnalysisSkeleton from '$lib/components/AnalysisSkeleton.svelte';
	import { error as toastError, success as toastSuccess } from '$lib/toast';
	import { supabase } from '$lib/supabase';

	interface ProjectOption {
		project_id: string;
		name: string;
	}

	let projects = $state<ProjectOption[]>([]);
	let selectedProject = $state<string>('');
	let snapshots = $state<CostSnapshotSummary[]>([]);
	let selectedSnapshot = $state<string>('');
	let loadingProjects = $state(false);
	let loadingSnapshots = $state(false);
	let generating = $state(false);
	let loadError = $state('');

	let originalContractSum = $state<number>(0);
	let previousCertificatesTotal = $state<number>(0);
	let applicationNumber = $state<number>(1);
	let periodTo = $state<string>('');
	let retainagePct = $state<number>(0.10);
	let retainageStoredFraction = $state<number>(0);
	let priorAdditions = $state<number>(0);
	let priorDeductions = $state<number>(0);
	let thisPeriodAdditions = $state<number>(0);
	let thisPeriodDeductions = $state<number>(0);

	let owner = $state<string>('');
	let contractor = $state<string>('');
	let architect = $state<string>('');
	let contractFor = $state<string>('');
	let architectsProjectNumber = $state<string>('');
	let contractDate = $state<string>('');
	let viaArchitect = $state<string>('');

	onMount(async () => {
		loadingProjects = true;
		try {
			const resp = await getProjects();
			projects = resp.projects.map((p) => ({
				project_id: p.project_id,
				name: p.name || p.project_id
			}));
		} catch (e) {
			loadError = e instanceof Error ? e.message : 'Failed to load projects';
		} finally {
			loadingProjects = false;
		}
	});

	async function loadSnapshots(projectId: string) {
		if (!projectId) {
			snapshots = [];
			selectedSnapshot = '';
			return;
		}
		loadingSnapshots = true;
		try {
			const resp = await getCostSnapshots(projectId);
			snapshots = resp.snapshots;
			selectedSnapshot = snapshots.length > 0 ? snapshots[0].snapshot_id : '';
		} catch (e) {
			toastError(e instanceof Error ? e.message : 'Failed to load snapshots');
			snapshots = [];
			selectedSnapshot = '';
		} finally {
			loadingSnapshots = false;
		}
	}

	$effect(() => {
		loadSnapshots(selectedProject);
	});

	const netChangeByCO = $derived(
		priorAdditions + thisPeriodAdditions - priorDeductions - thisPeriodDeductions
	);
	const contractSumToDate = $derived(originalContractSum + netChangeByCO);

	async function generate() {
		if (!selectedProject || !selectedSnapshot) {
			toastError('Pick a project and a CBS snapshot first');
			return;
		}
		if (originalContractSum <= 0) {
			toastError('Original Contract Sum must be > 0');
			return;
		}
		generating = true;
		try {
			const BASE = import.meta.env.VITE_API_URL || '';
			const { data: sessionData } = await supabase.auth.getSession();
			const token = sessionData.session?.access_token;
			const headers: Record<string, string> = {
				'Content-Type': 'application/json'
			};
			if (token) headers['Authorization'] = `Bearer ${token}`;

			const genResp = await fetch(`${BASE}/api/v1/reports/generate`, {
				method: 'POST',
				headers,
				body: JSON.stringify({
					project_id: selectedProject,
					report_type: 'aia_g702',
					options: {
						snapshot_id: selectedSnapshot,
						original_contract_sum: originalContractSum,
						application_number: applicationNumber,
						period_to: periodTo,
						retainage_pct: retainagePct,
						retainage_stored_fraction: retainageStoredFraction,
						previous_certificates_total: previousCertificatesTotal,
						change_order: {
							prior_additions: priorAdditions,
							prior_deductions: priorDeductions,
							this_period_additions: thisPeriodAdditions,
							this_period_deductions: thisPeriodDeductions
						},
						owner,
						contractor,
						architect,
						contract_for: contractFor,
						architects_project_number: architectsProjectNumber,
						contract_date: contractDate,
						via_architect: viaArchitect
					}
				})
			});
			if (!genResp.ok) throw new Error(await genResp.text());
			const body = await genResp.json();
			const reportId = body.report_id as string;

			const downloadHeaders: Record<string, string> = token
				? { Authorization: `Bearer ${token}` }
				: {};
			const dlResp = await fetch(`${BASE}/api/v1/reports/${reportId}/download`, {
				headers: downloadHeaders
			});
			if (!dlResp.ok) throw new Error(await dlResp.text());
			const blob = await dlResp.blob();
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			const isPdf = blob.type === 'application/pdf';
			a.download = `meridianiq-aia-g702-app${String(applicationNumber).padStart(3, '0')}.${isPdf ? 'pdf' : 'html'}`;
			a.click();
			URL.revokeObjectURL(url);
			toastSuccess('G702 downloaded');
		} catch (e) {
			toastError(e instanceof Error ? e.message : 'Generation failed');
		} finally {
			generating = false;
		}
	}
</script>

<svelte:head>
	<title>AIA G702 Certificate — MeridianIQ</title>
</svelte:head>

<main class="max-w-5xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">
			AIA G702 — Application and Certificate for Payment
		</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">
			Generate the cover certificate paired with your G703 Continuation Sheet. Requires a CBS snapshot for line totals.
		</p>
	</div>

	{#if loadError}
		<div class="bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg p-4 mb-6">
			<p class="text-red-700 text-sm">{loadError}</p>
		</div>
	{/if}

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Source</h2>
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Project</span>
				<select
					bind:value={selectedProject}
					disabled={loadingProjects}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				>
					<option value="">— choose project —</option>
					{#each projects as p}
						<option value={p.project_id}>{p.name}</option>
					{/each}
				</select>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">CBS Snapshot</span>
				<select
					bind:value={selectedSnapshot}
					disabled={loadingSnapshots || snapshots.length === 0}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				>
					{#if snapshots.length === 0}
						<option value="">— upload CBS first —</option>
					{:else}
						{#each snapshots as s}
							<option value={s.snapshot_id}>
								{s.source_name || s.snapshot_id.slice(0, 8)} · ${Math.round(s.total_budget).toLocaleString()}
							</option>
						{/each}
					{/if}
				</select>
			</label>
		</div>
	</div>

	{#if loadingProjects || loadingSnapshots}
		<AnalysisSkeleton />
	{/if}

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Contract &amp; Application</h2>
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Original Contract Sum (USD)</span>
				<input
					type="number"
					step="0.01"
					bind:value={originalContractSum}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Previous Certificates Total (USD)</span>
				<input
					type="number"
					step="0.01"
					bind:value={previousCertificatesTotal}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Application Number</span>
				<input
					type="number"
					min="1"
					bind:value={applicationNumber}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Period To</span>
				<input
					type="date"
					bind:value={periodTo}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Retainage % (0–1)</span>
				<input
					type="number"
					min="0"
					max="1"
					step="0.01"
					bind:value={retainagePct}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Retainage Stored Fraction (0–1)</span>
				<input
					type="number"
					min="0"
					max="1"
					step="0.01"
					bind:value={retainageStoredFraction}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
		</div>
	</div>

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Change Orders</h2>
		<div class="grid grid-cols-2 gap-4">
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Prior Months — Additions</span>
				<input
					type="number"
					step="0.01"
					bind:value={priorAdditions}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Prior Months — Deductions</span>
				<input
					type="number"
					step="0.01"
					bind:value={priorDeductions}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">This Month — Additions</span>
				<input
					type="number"
					step="0.01"
					bind:value={thisPeriodAdditions}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">This Month — Deductions</span>
				<input
					type="number"
					step="0.01"
					bind:value={thisPeriodDeductions}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
		</div>
		<div class="mt-3 text-xs text-gray-500 dark:text-gray-400">
			Net Change: <span class="font-semibold text-gray-900 dark:text-gray-100">${netChangeByCO.toLocaleString()}</span>
			— Contract Sum to Date: <span class="font-semibold text-gray-900 dark:text-gray-100">${contractSumToDate.toLocaleString()}</span>
		</div>
	</div>

	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Header Fields (optional)</h2>
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Owner</span>
				<input
					type="text"
					bind:value={owner}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Contractor</span>
				<input
					type="text"
					bind:value={contractor}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Architect</span>
				<input
					type="text"
					bind:value={architect}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Via Architect</span>
				<input
					type="text"
					bind:value={viaArchitect}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Contract For</span>
				<input
					type="text"
					bind:value={contractFor}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Architect's Project No.</span>
				<input
					type="text"
					bind:value={architectsProjectNumber}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
			<label class="block">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">Contract Date</span>
				<input
					type="date"
					bind:value={contractDate}
					class="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
				/>
			</label>
		</div>
	</div>

	<div class="flex justify-end">
		<button
			onclick={generate}
			disabled={generating || !selectedProject || !selectedSnapshot || originalContractSum <= 0}
			class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
		>
			{generating ? 'Generating…' : 'Generate G702 PDF'}
		</button>
	</div>
</main>
