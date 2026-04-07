<script lang="ts">
	import { page } from '$app/state';
	import { getRiskSimulation } from '$lib/api';

	interface PValue { percentile: number; duration_days: number; delta_days: number; }
	interface HistogramBin { bin_start: number; bin_end: number; count: number; frequency: number; }
	interface CriticalityEntry { activity_id: string; activity_name: string; criticality_pct: number; }
	interface SensitivityEntry { activity_id: string; activity_name: string; correlation: number; }
	interface SCurvePoint { duration_days: number; cumulative_probability: number; }

	const simulationId = $derived(page.params.id!);
	let loading = $state(true);
	let error = $state('');

	// Data
	let projectName = $state('');
	let iterations = $state(0);
	let deterministicDays = $state(0);
	let meanDays = $state(0);
	let stdDays = $state(0);
	let pValues: PValue[] = $state([]);
	let histogram: HistogramBin[] = $state([]);
	let criticality: CriticalityEntry[] = $state([]);
	let sensitivity: SensitivityEntry[] = $state([]);
	let sCurve: SCurvePoint[] = $state([]);

	async function loadSimulation() {
		loading = true;
		error = '';
		try {
			const data = await getRiskSimulation(simulationId);
			projectName = data.project_name;
			iterations = data.iterations;
			deterministicDays = data.deterministic_days;
			meanDays = data.mean_days;
			stdDays = data.std_days;
			pValues = data.p_values;
			histogram = data.histogram;
			criticality = data.criticality;
			sensitivity = data.sensitivity;
			sCurve = data.s_curve;
		} catch (e: any) {
			error = e.message;
		} finally {
			loading = false;
		}
	}

	function getPValue(pct: number): PValue | undefined {
		return pValues.find(p => p.percentile === pct);
	}

	// SVG chart dimensions
	const W = 700;
	const H = 300;
	const PAD = 50;

	// Histogram SVG
	function histogramBars() {
		if (!histogram.length) return [];
		const maxCount = Math.max(...histogram.map(b => b.count));
		const barW = (W - 2 * PAD) / histogram.length;

		return histogram.map((b, i) => ({
			x: PAD + i * barW,
			y: PAD + (H - 2 * PAD) * (1 - b.count / (maxCount || 1)),
			width: barW - 1,
			height: (H - 2 * PAD) * (b.count / (maxCount || 1)),
			label: `${b.bin_start.toFixed(1)}-${b.bin_end.toFixed(1)}d: ${b.count}`,
		}));
	}

	function pValueLines() {
		if (!histogram.length || !pValues.length) return [];
		const minX = histogram[0].bin_start;
		const maxX = histogram[histogram.length - 1].bin_end;
		const xRange = maxX - minX || 1;
		const colors: Record<number, string> = { 10: '#22c55e', 50: '#3b82f6', 80: '#f97316', 90: '#ef4444' };
		return pValues
			.filter(pv => [10, 50, 80, 90].includes(pv.percentile))
			.map(pv => ({
				x: PAD + ((pv.duration_days - minX) / xRange) * (W - 2 * PAD),
				color: colors[pv.percentile] || '#6b7280',
				label: `P${pv.percentile}: ${pv.duration_days.toFixed(1)}d`,
				percentile: pv.percentile,
			}));
	}

	// Tornado SVG
	function tornadoBars() {
		const top15 = sensitivity.slice(0, 15);
		if (!top15.length) return [];
		const maxAbs = Math.max(...top15.map(s => Math.abs(s.correlation)), 0.01);
		const barH = Math.min(25, (H - 2 * PAD) / top15.length);

		return top15.map((s, i) => ({
			y: PAD + i * barH,
			width: Math.abs(s.correlation) / maxAbs * ((W - 2 * PAD) / 2),
			x: s.correlation >= 0 ? W / 2 : W / 2 - Math.abs(s.correlation) / maxAbs * ((W - 2 * PAD) / 2),
			height: barH - 2,
			color: s.correlation >= 0 ? '#3b82f6' : '#ef4444',
			label: s.activity_name || s.activity_id,
			value: s.correlation.toFixed(3),
		}));
	}

	// S-Curve SVG
	function sCurvePath() {
		if (!sCurve.length) return '';
		const minX = sCurve[0].duration_days;
		const maxX = sCurve[sCurve.length - 1].duration_days;
		const xRange = maxX - minX || 1;

		return sCurve.map((p, i) => {
			const x = PAD + ((p.duration_days - minX) / xRange) * (W - 2 * PAD);
			const y = PAD + (H - 2 * PAD) * (1 - p.cumulative_probability);
			return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
		}).join(' ');
	}

	$effect(() => {
		if (simulationId) loadSimulation();
	});
</script>

<svelte:head>
	<title>Risk Simulation | MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-7xl mx-auto">
	<div class="mb-6">
		<a href="/risk" class="text-blue-600 hover:text-blue-800 text-sm">&larr; Back to Simulations</a>
	</div>

	{#if loading}
		<div class="text-center text-gray-500 dark:text-gray-400 py-12">Loading simulation...</div>
	{:else if error}
		<div class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
	{:else}
		<div class="mb-6">
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{projectName} - Risk Simulation</h1>
			<p class="text-gray-500 dark:text-gray-400 mt-1">{simulationId} &middot; {iterations.toLocaleString()} iterations</p>
		</div>

		<!-- P-Value Summary Cards -->
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
			{#each [10, 50, 80, 90] as pct}
				{@const pv = getPValue(pct)}
				{#if pv}
					<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
						<div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">P{pct}</div>
						<div class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{pv.duration_days.toFixed(1)}d</div>
						<div class="text-sm mt-1 {pv.delta_days > 0 ? 'text-red-600' : pv.delta_days < 0 ? 'text-green-600' : 'text-gray-500 dark:text-gray-400'}">
							{pv.delta_days > 0 ? '+' : ''}{pv.delta_days.toFixed(1)}d vs deterministic
						</div>
					</div>
				{/if}
			{/each}
		</div>

		<!-- Statistics -->
		<div class="grid grid-cols-3 gap-4 mb-8">
			<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
				<div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Deterministic</div>
				<div class="text-xl font-bold text-gray-900 dark:text-gray-100 mt-1">{deterministicDays.toFixed(1)} days</div>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
				<div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Mean</div>
				<div class="text-xl font-bold text-gray-900 dark:text-gray-100 mt-1">{meanDays.toFixed(1)} days</div>
			</div>
			<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
				<div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Std Dev</div>
				<div class="text-xl font-bold text-gray-900 dark:text-gray-100 mt-1">{stdDays.toFixed(2)} days</div>
			</div>
		</div>

		<!-- Histogram -->
		<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-8">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Completion Duration Distribution</h2>
			<svg viewBox="0 0 {W} {H}" class="w-full" style="max-height: 350px;">
				<!-- Bars -->
				{#each histogramBars() as bar}
					<rect
						x={bar.x}
						y={bar.y}
						width={bar.width}
						height={bar.height}
						fill="#93c5fd"
						stroke="#3b82f6"
						stroke-width="0.5"
					>
						<title>{bar.label}</title>
					</rect>
				{/each}
				<!-- P-value lines -->
				{#each pValueLines() as line}
					<line
						x1={line.x}
						y1={PAD}
						x2={line.x}
						y2={H - PAD}
						stroke={line.color}
						stroke-width="2"
						stroke-dasharray="4 2"
					/>
					<text x={line.x} y={PAD - 5} text-anchor="middle" fill={line.color} font-size="10" font-weight="bold">
						{line.label}
					</text>
				{/each}
				<!-- Axes -->
				<line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="#9ca3af" stroke-width="1" />
				<line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="#9ca3af" stroke-width="1" />
				<text x={W / 2} y={H - 10} text-anchor="middle" fill="#6b7280" font-size="11">Duration (days)</text>
				<text x="15" y={H / 2} text-anchor="middle" fill="#6b7280" font-size="11" transform="rotate(-90 15 {H / 2})">Frequency</text>
			</svg>
		</div>

		<!-- Tornado Diagram -->
		<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-8">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Sensitivity (Tornado Diagram)</h2>
			{#if sensitivity.length === 0}
				<p class="text-gray-500 dark:text-gray-400 text-sm">No sensitivity data available.</p>
			{:else}
				<svg viewBox="0 0 {W} {Math.max(H, 50 + sensitivity.slice(0, 15).length * 25)}" class="w-full" style="max-height: 450px;">
					<!-- Center line -->
					<line x1={W / 2} y1={PAD - 10} x2={W / 2} y2={50 + sensitivity.slice(0, 15).length * 25} stroke="#d1d5db" stroke-width="1" />
					{#each tornadoBars() as bar}
						<rect
							x={bar.x}
							y={bar.y}
							width={bar.width}
							height={bar.height}
							fill={bar.color}
							opacity="0.8"
							rx="2"
						>
							<title>{bar.label}: {bar.value}</title>
						</rect>
						<text
							x={bar.x < W / 2 ? bar.x - 5 : bar.x + bar.width + 5}
							y={bar.y + bar.height / 2 + 4}
							text-anchor={bar.x < W / 2 ? 'end' : 'start'}
							fill="#374151"
							font-size="9"
						>
							{bar.label.length > 25 ? bar.label.slice(0, 25) + '...' : bar.label} ({bar.value})
						</text>
					{/each}
					<text x={W / 2} y={PAD - 15} text-anchor="middle" fill="#6b7280" font-size="10">Spearman Correlation</text>
				</svg>
			{/if}
		</div>

		<!-- Criticality Index Table -->
		<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-8">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Criticality Index</h2>
			<div class="overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Activity</th>
							<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
							<th class="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Criticality %</th>
							<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase w-64">Bar</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each criticality.filter(c => c.criticality_pct > 0) as c}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
								<td class="px-4 py-2 text-sm font-mono text-gray-600 dark:text-gray-400">{c.activity_id}</td>
								<td class="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">{c.activity_name}</td>
								<td class="px-4 py-2 text-sm text-right font-medium text-gray-900 dark:text-gray-100">{c.criticality_pct.toFixed(1)}%</td>
								<td class="px-4 py-2">
									<div class="w-full bg-gray-100 dark:bg-gray-800 rounded-full h-3">
										<div
											class="h-3 rounded-full {c.criticality_pct >= 80 ? 'bg-red-500' : c.criticality_pct >= 50 ? 'bg-orange-400' : 'bg-blue-400'}"
											style="width: {Math.min(c.criticality_pct, 100)}%"
										></div>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>

		<!-- Cumulative S-Curve -->
		<div class="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-8">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Cumulative Probability (S-Curve)</h2>
			<svg viewBox="0 0 {W} {H}" class="w-full" style="max-height: 350px;">
				<!-- Grid lines -->
				{#each [0.25, 0.5, 0.75, 1.0] as prob}
					<line
						x1={PAD}
						y1={PAD + (H - 2 * PAD) * (1 - prob)}
						x2={W - PAD}
						y2={PAD + (H - 2 * PAD) * (1 - prob)}
						stroke="#e5e7eb"
						stroke-width="0.5"
					/>
					<text
						x={PAD - 5}
						y={PAD + (H - 2 * PAD) * (1 - prob) + 4}
						text-anchor="end"
						fill="#9ca3af"
						font-size="9"
					>
						{(prob * 100).toFixed(0)}%
					</text>
				{/each}
				<!-- S-curve path -->
				{#if sCurve.length > 0}
					<path d={sCurvePath()} fill="none" stroke="#3b82f6" stroke-width="2.5" />
				{/if}
				<!-- P-value markers on the S-curve -->
				{#each pValues.filter(pv => [10, 50, 80, 90].includes(pv.percentile)) as pv}
					{#if sCurve.length > 1}
						{@const minX = sCurve[0].duration_days}
						{@const maxX = sCurve[sCurve.length - 1].duration_days}
						{@const xRange = maxX - minX || 1}
						{@const cx = PAD + ((pv.duration_days - minX) / xRange) * (W - 2 * PAD)}
						{@const cy = PAD + (H - 2 * PAD) * (1 - pv.percentile / 100)}
						<circle {cx} {cy} r="4" fill={pv.percentile <= 25 ? '#22c55e' : pv.percentile <= 50 ? '#3b82f6' : pv.percentile <= 80 ? '#f97316' : '#ef4444'} />
						<text x={cx + 8} y={cy + 4} fill="#374151" font-size="9" font-weight="bold">P{pv.percentile}</text>
					{/if}
				{/each}
				<!-- Axes -->
				<line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="#9ca3af" stroke-width="1" />
				<line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="#9ca3af" stroke-width="1" />
				<text x={W / 2} y={H - 10} text-anchor="middle" fill="#6b7280" font-size="11">Duration (days)</text>
				<text x="15" y={H / 2} text-anchor="middle" fill="#6b7280" font-size="11" transform="rotate(-90 15 {H / 2})">Cumulative Probability</text>
			</svg>
		</div>
	{/if}
</div>
