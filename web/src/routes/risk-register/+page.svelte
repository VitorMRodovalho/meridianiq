<script lang="ts">
	import { success as toastSuccess, error as toastError } from '$lib/toast';
	import { t } from '$lib/i18n';
	import HeatMapChart from '$lib/components/charts/HeatMapChart.svelte';

	const CATEGORY_KEYS: Record<string, string> = {
		schedule: 'risk_register.category_schedule',
		cost: 'risk_register.category_cost',
		scope: 'risk_register.category_scope',
		quality: 'risk_register.category_quality',
		external: 'risk_register.category_external',
	};

	interface RiskEntry {
		risk_id: string;
		name: string;
		description: string;
		category: string;
		probability: number;
		impact_days: number;
		impact_cost: number;
		status: string;
		responsible_party: string;
		mitigation: string;
		affected_activities: string;
	}

	let risks: RiskEntry[] = $state([]);

	// New risk form
	let newRisk = $state<RiskEntry>({
		risk_id: '',
		name: '',
		description: '',
		category: 'schedule',
		probability: 0.5,
		impact_days: 0,
		impact_cost: 0,
		status: 'open',
		responsible_party: '',
		mitigation: '',
		affected_activities: '',
	});

	function addRisk() {
		if (!newRisk.risk_id || !newRisk.name) {
			toastError($t('risk_register.toast_missing'));
			return;
		}
		risks = [...risks, { ...newRisk }];
		toastSuccess(`${$t('page.risk_register')} ${newRisk.risk_id} ${$t('risk_register.toast_added')}`);
		newRisk = {
			risk_id: `R${String(risks.length + 1).padStart(3, '0')}`,
			name: '',
			description: '',
			category: 'schedule',
			probability: 0.5,
			impact_days: 0,
			impact_cost: 0,
			status: 'open',
			responsible_party: '',
			mitigation: '',
			affected_activities: '',
		};
	}

	function removeRisk(id: string) {
		risks = risks.filter((r) => r.risk_id !== id);
		toastSuccess(`${$t('page.risk_register')} ${id} ${$t('risk_register.toast_removed')}`);
	}

	function categoryLabel(cat: string): string {
		const key = CATEGORY_KEYS[cat];
		return key ? $t(key) : cat;
	}

	const openRisks = $derived(risks.filter((r) => r.status === 'open'));
	const expectedImpact = $derived(
		openRisks.reduce((sum, r) => sum + r.probability * r.impact_days, 0)
	);
	const expectedCost = $derived(
		openRisks.reduce((sum, r) => sum + r.probability * r.impact_cost, 0)
	);

	const riskColor = (prob: number, impact: number) => {
		const score = prob * impact;
		if (score >= 15) return 'bg-red-100 text-red-800';
		if (score >= 5) return 'bg-amber-100 text-amber-800';
		return 'bg-green-100 text-green-800';
	};
</script>

<svelte:head>
	<title>{$t('page.risk_register')} - MeridianIQ</title>
</svelte:head>

<main class="max-w-6xl mx-auto px-4 py-8">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('page.risk_register')}</h1>
		<p class="text-gray-500 dark:text-gray-400 mt-1">{$t('risk_register.subtitle')}</p>
	</div>

	<!-- Summary Cards -->
	<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
			<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('risk_register.stat_total')}</p>
			<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{risks.length}</p>
		</div>
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
			<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('risk_register.stat_open')}</p>
			<p class="text-2xl font-bold text-amber-600">{openRisks.length}</p>
		</div>
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
			<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('risk_register.stat_expected_delay')}</p>
			<p class="text-2xl font-bold text-red-600">{expectedImpact.toFixed(1)}d</p>
		</div>
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
			<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{$t('risk_register.stat_expected_cost')}</p>
			<p class="text-2xl font-bold text-red-600">${expectedCost.toLocaleString()}</p>
		</div>
	</div>

	<!-- Heat Map -->
	{#if risks.length > 0}
		<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
			<HeatMapChart
				items={risks.filter(r => r.status === 'open').map(r => ({
					x: r.impact_days,
					y: r.probability,
					label: r.name,
				}))}
				title={$t('risk_register.heatmap_title')}
			/>
			<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
				<p class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{$t('risk_register.category_panel_title')}</p>
				{#each Object.entries(risks.reduce((acc, r) => { acc[r.category] = (acc[r.category] || 0) + 1; return acc; }, {} as Record<string, number>)) as [cat, count]}
					<div class="flex justify-between items-center py-1.5 border-b border-gray-100">
						<span class="text-sm text-gray-600 dark:text-gray-400">{categoryLabel(cat)}</span>
						<span class="text-sm font-semibold text-gray-900 dark:text-gray-100">{count}</span>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Add Risk Form -->
	<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 mb-6">
		<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{$t('risk_register.add_title')}</h2>
		<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
			<div>
				<label for="rid" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('risk_register.field_id')}</label>
				<input id="rid" bind:value={newRisk.risk_id} placeholder="R001" class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
			<div>
				<label for="rname" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('risk_register.field_name')}</label>
				<input id="rname" bind:value={newRisk.name} placeholder={$t('risk_register.placeholder_name')} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
			<div>
				<label for="rcat" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('risk_register.field_category')}</label>
				<select id="rcat" bind:value={newRisk.category} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm">
					<option value="schedule">{$t('risk_register.category_schedule')}</option>
					<option value="cost">{$t('risk_register.category_cost')}</option>
					<option value="scope">{$t('risk_register.category_scope')}</option>
					<option value="quality">{$t('risk_register.category_quality')}</option>
					<option value="external">{$t('risk_register.category_external')}</option>
				</select>
			</div>
			<div>
				<label for="rprob" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('risk_register.field_probability')}</label>
				<input id="rprob" type="number" step="0.1" min="0" max="1" bind:value={newRisk.probability} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
			<div>
				<label for="rdays" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('risk_register.field_impact_days')}</label>
				<input id="rdays" type="number" min="0" bind:value={newRisk.impact_days} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
			<div>
				<label for="rcost" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('risk_register.field_impact_cost')}</label>
				<input id="rcost" type="number" min="0" bind:value={newRisk.impact_cost} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
			<div>
				<label for="rparty" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('risk_register.field_party')}</label>
				<input id="rparty" bind:value={newRisk.responsible_party} placeholder={$t('risk_register.placeholder_party')} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
			<div>
				<label for="rmit" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('risk_register.field_mitigation')}</label>
				<input id="rmit" bind:value={newRisk.mitigation} placeholder={$t('risk_register.placeholder_mitigation')} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
			<div>
				<label for="racts" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{$t('risk_register.field_activities')}</label>
				<input id="racts" bind:value={newRisk.affected_activities} placeholder={$t('risk_register.placeholder_activities')} class="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm" />
			</div>
		</div>
		<div class="mt-4">
			<button onclick={addRisk} class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700">
				{$t('risk_register.btn_add')}
			</button>
		</div>
	</div>

	<!-- Risk Table -->
	{#if risks.length > 0}
		<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">{$t('risk_register.table_title')} ({risks.length} {$t('risk_register.table_risks_suffix')})</h2>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-200 dark:border-gray-700">
							<th class="text-left py-2 px-3">{$t('risk_register.col_id')}</th>
							<th class="text-left py-2 px-3">{$t('risk_register.col_name')}</th>
							<th class="text-left py-2 px-3">{$t('risk_register.field_category')}</th>
							<th class="text-right py-2 px-3">{$t('risk_register.col_prob')}</th>
							<th class="text-right py-2 px-3">{$t('risk_register.col_impact')}</th>
							<th class="text-right py-2 px-3">{$t('risk_register.col_expected')}</th>
							<th class="text-left py-2 px-3">{$t('risk_register.col_status')}</th>
							<th class="text-center py-2 px-3">{$t('risk_register.col_action')}</th>
						</tr>
					</thead>
					<tbody>
						{#each risks as risk}
							<tr class="border-b border-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800">
								<td class="py-2 px-3 font-mono text-xs">{risk.risk_id}</td>
								<td class="py-2 px-3 font-medium">{risk.name}</td>
								<td class="py-2 px-3">{categoryLabel(risk.category)}</td>
								<td class="py-2 px-3 text-right">{(risk.probability * 100).toFixed(0)}%</td>
								<td class="py-2 px-3 text-right">{risk.impact_days}d</td>
								<td class="py-2 px-3 text-right">
									<span class="px-2 py-0.5 rounded text-xs font-medium {riskColor(risk.probability, risk.impact_days)}">
										{(risk.probability * risk.impact_days).toFixed(1)}d
									</span>
								</td>
								<td class="py-2 px-3 capitalize">{risk.status}</td>
								<td class="py-2 px-3 text-center">
									<button onclick={() => removeRisk(risk.risk_id)} class="text-red-500 hover:text-red-700 text-xs">
										{$t('risk_register.btn_remove')}
									</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</main>
