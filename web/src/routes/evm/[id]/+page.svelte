<script lang="ts">
	import { page } from '$app/state';
	import { getEVMAnalysis } from '$lib/api';

	let analysis: any = $state(null);
	let loading = $state(true);
	let error = $state('');

	const id = $derived(page.params.id);

	async function loadAnalysis() {
		loading = true;
		try {
			analysis = await getEVMAnalysis(id);
		} catch (e: any) {
			error = e.message || 'Failed to load';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		if (id) loadAnalysis();
	});

	function healthColor(status: string): string {
		if (status === 'good') return 'bg-green-500';
		if (status === 'watch') return 'bg-yellow-500';
		return 'bg-red-500';
	}

	function healthTextColor(status: string): string {
		if (status === 'good') return 'text-green-700';
		if (status === 'watch') return 'text-yellow-700';
		return 'text-red-700';
	}

	function healthBgColor(status: string): string {
		if (status === 'good') return 'bg-green-50 border-green-200';
		if (status === 'watch') return 'bg-yellow-50 border-yellow-200';
		return 'bg-red-50 border-red-200';
	}

	function fmt(n: number): string {
		return n?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '0.00';
	}

	// S-curve SVG dimensions
	const svgW = 800;
	const svgH = 300;
	const padL = 60;
	const padR = 20;
	const padT = 20;
	const padB = 40;

	function buildPath(points: any[], key: string, maxVal: number): string {
		if (!points || points.length === 0) return '';
		const plotW = svgW - padL - padR;
		const plotH = svgH - padT - padB;
		return points
			.map((p: any, i: number) => {
				const x = padL + (i / Math.max(points.length - 1, 1)) * plotW;
				const y = padT + plotH - (maxVal > 0 ? (p[key] / maxVal) * plotH : 0);
				return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
			})
			.join(' ');
	}

	const scurveMax = $derived.by(() => {
		if (!analysis?.s_curve?.length) return 1;
		let max = 0;
		for (const p of analysis.s_curve) {
			max = Math.max(max, p.cumulative_pv, p.cumulative_ev, p.cumulative_ac);
		}
		return max || 1;
	});
</script>

{#if loading}
	<div class="p-8 text-center text-gray-500">Loading analysis...</div>
{:else if error}
	<div class="p-8 text-center text-red-600">{error}</div>
{:else if analysis}
	<div class="p-8 max-w-6xl mx-auto">
		<!-- Header -->
		<div class="mb-6 flex items-center justify-between">
			<div>
				<h1 class="text-2xl font-bold text-gray-900">EVM Analysis: {analysis.project_name || analysis.analysis_id}</h1>
				<p class="text-sm text-gray-500 mt-1">
					{analysis.analysis_id} | Data Date: {analysis.data_date || 'N/A'}
				</p>
			</div>
			<a href="/evm" class="text-sm text-blue-600 hover:text-blue-800">Back to list</a>
		</div>

		<!-- Summary Cards -->
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
			<div class="bg-white rounded-lg shadow p-4">
				<p class="text-xs font-medium text-gray-500 uppercase">BAC</p>
				<p class="text-xl font-bold text-gray-900 mt-1">${fmt(analysis.metrics.bac)}</p>
			</div>
			<div class="bg-white rounded-lg shadow p-4">
				<p class="text-xs font-medium text-gray-500 uppercase">Earned Value (EV)</p>
				<p class="text-xl font-bold text-green-700 mt-1">${fmt(analysis.metrics.ev)}</p>
			</div>
			<div class="bg-white rounded-lg shadow p-4">
				<p class="text-xs font-medium text-gray-500 uppercase">Actual Cost (AC)</p>
				<p class="text-xl font-bold text-red-700 mt-1">${fmt(analysis.metrics.ac)}</p>
			</div>
			<div class="bg-white rounded-lg shadow p-4">
				<p class="text-xs font-medium text-gray-500 uppercase">Planned Value (PV)</p>
				<p class="text-xl font-bold text-blue-700 mt-1">${fmt(analysis.metrics.pv)}</p>
			</div>
		</div>

		<!-- SPI / CPI Gauges -->
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
			<div class="bg-white rounded-lg shadow p-5 border {healthBgColor(analysis.schedule_health.status)}">
				<div class="flex items-center gap-3">
					<span class="w-4 h-4 rounded-full {healthColor(analysis.schedule_health.status)}"></span>
					<div>
						<p class="text-sm font-medium text-gray-700">Schedule Health (SPI)</p>
						<p class="text-2xl font-bold {healthTextColor(analysis.schedule_health.status)}">
							{analysis.metrics.spi?.toFixed(3)}
						</p>
						<p class="text-xs text-gray-500 mt-0.5">
							SV: ${fmt(analysis.metrics.sv)} | {analysis.schedule_health.label}
						</p>
					</div>
				</div>
			</div>
			<div class="bg-white rounded-lg shadow p-5 border {healthBgColor(analysis.cost_health.status)}">
				<div class="flex items-center gap-3">
					<span class="w-4 h-4 rounded-full {healthColor(analysis.cost_health.status)}"></span>
					<div>
						<p class="text-sm font-medium text-gray-700">Cost Health (CPI)</p>
						<p class="text-2xl font-bold {healthTextColor(analysis.cost_health.status)}">
							{analysis.metrics.cpi?.toFixed(3)}
						</p>
						<p class="text-xs text-gray-500 mt-0.5">
							CV: ${fmt(analysis.metrics.cv)} | {analysis.cost_health.label}
						</p>
					</div>
				</div>
			</div>
		</div>

		<!-- S-Curve Chart -->
		{#if analysis.s_curve && analysis.s_curve.length > 1}
			<div class="bg-white rounded-lg shadow p-6 mb-6">
				<h2 class="text-lg font-semibold text-gray-800 mb-4">S-Curve</h2>
				<svg viewBox="0 0 {svgW} {svgH}" class="w-full h-auto">
					<!-- Grid lines -->
					{#each [0.25, 0.5, 0.75, 1.0] as frac}
						<line
							x1={padL} y1={padT + (svgH - padT - padB) * (1 - frac)}
							x2={svgW - padR} y2={padT + (svgH - padT - padB) * (1 - frac)}
							stroke="#e5e7eb" stroke-width="1"
						/>
						<text
							x={padL - 5}
							y={padT + (svgH - padT - padB) * (1 - frac) + 4}
							text-anchor="end" fill="#9ca3af" font-size="10"
						>
							${(scurveMax * frac / 1000).toFixed(0)}k
						</text>
					{/each}
					<!-- Axes -->
					<line x1={padL} y1={svgH - padB} x2={svgW - padR} y2={svgH - padB} stroke="#d1d5db" stroke-width="1" />
					<line x1={padL} y1={padT} x2={padL} y2={svgH - padB} stroke="#d1d5db" stroke-width="1" />
					<!-- PV line (blue) -->
					<path d={buildPath(analysis.s_curve, 'cumulative_pv', scurveMax)} fill="none" stroke="#3b82f6" stroke-width="2" />
					<!-- EV line (green) -->
					<path d={buildPath(analysis.s_curve, 'cumulative_ev', scurveMax)} fill="none" stroke="#22c55e" stroke-width="2" />
					<!-- AC line (red) -->
					<path d={buildPath(analysis.s_curve, 'cumulative_ac', scurveMax)} fill="none" stroke="#ef4444" stroke-width="2" />
					<!-- Legend -->
					<rect x={svgW - 150} y={padT} width="130" height="60" fill="white" fill-opacity="0.9" stroke="#e5e7eb" rx="4" />
					<line x1={svgW - 140} y1={padT + 15} x2={svgW - 120} y2={padT + 15} stroke="#3b82f6" stroke-width="2" />
					<text x={svgW - 115} y={padT + 19} fill="#374151" font-size="11">PV (Planned)</text>
					<line x1={svgW - 140} y1={padT + 33} x2={svgW - 120} y2={padT + 33} stroke="#22c55e" stroke-width="2" />
					<text x={svgW - 115} y={padT + 37} fill="#374151" font-size="11">EV (Earned)</text>
					<line x1={svgW - 140} y1={padT + 51} x2={svgW - 120} y2={padT + 51} stroke="#ef4444" stroke-width="2" />
					<text x={svgW - 115} y={padT + 55} fill="#374151" font-size="11">AC (Actual)</text>
					<!-- Date labels -->
					{#if analysis.s_curve.length > 0}
						<text x={padL} y={svgH - padB + 18} fill="#9ca3af" font-size="10" text-anchor="start">
							{analysis.s_curve[0].date}
						</text>
						<text x={svgW - padR} y={svgH - padB + 18} fill="#9ca3af" font-size="10" text-anchor="end">
							{analysis.s_curve[analysis.s_curve.length - 1].date}
						</text>
					{/if}
				</svg>
			</div>
		{/if}

		<!-- Forecast Table -->
		<div class="bg-white rounded-lg shadow p-6 mb-6">
			<h2 class="text-lg font-semibold text-gray-800 mb-4">Forecast Scenarios</h2>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead class="bg-gray-50">
						<tr>
							<th class="px-4 py-3 text-left font-medium text-gray-500">Metric</th>
							<th class="px-4 py-3 text-right font-medium text-gray-500">Value</th>
							<th class="px-4 py-3 text-left font-medium text-gray-500">Description</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						<tr>
							<td class="px-4 py-3 font-medium">EAC (CPI)</td>
							<td class="px-4 py-3 text-right font-mono">${fmt(analysis.forecast.eac_cpi)}</td>
							<td class="px-4 py-3 text-gray-500">BAC / CPI -- assumes current cost efficiency continues</td>
						</tr>
						<tr>
							<td class="px-4 py-3 font-medium">EAC (Combined)</td>
							<td class="px-4 py-3 text-right font-mono">${fmt(analysis.forecast.eac_combined)}</td>
							<td class="px-4 py-3 text-gray-500">AC + (BAC - EV) / (CPI * SPI) -- combined index</td>
						</tr>
						<tr>
							<td class="px-4 py-3 font-medium">EAC (New ETC)</td>
							<td class="px-4 py-3 text-right font-mono">${fmt(analysis.forecast.eac_etc_new)}</td>
							<td class="px-4 py-3 text-gray-500">AC + (BAC - EV) -- remaining at budgeted rates</td>
						</tr>
						<tr>
							<td class="px-4 py-3 font-medium">ETC</td>
							<td class="px-4 py-3 text-right font-mono">${fmt(analysis.forecast.etc)}</td>
							<td class="px-4 py-3 text-gray-500">Estimate to Complete at current CPI</td>
						</tr>
						<tr>
							<td class="px-4 py-3 font-medium">VAC</td>
							<td class="px-4 py-3 text-right font-mono">${fmt(analysis.forecast.vac)}</td>
							<td class="px-4 py-3 text-gray-500">Variance at Completion (BAC - EAC)</td>
						</tr>
						<tr>
							<td class="px-4 py-3 font-medium">TCPI</td>
							<td class="px-4 py-3 text-right font-mono">{analysis.forecast.tcpi?.toFixed(3)}</td>
							<td class="px-4 py-3 text-gray-500">To-Complete Performance Index required to meet BAC</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<!-- WBS Drill-Down -->
		{#if analysis.wbs_breakdown && analysis.wbs_breakdown.length > 0}
			<div class="bg-white rounded-lg shadow p-6">
				<h2 class="text-lg font-semibold text-gray-800 mb-4">WBS Drill-Down</h2>
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-4 py-3 text-left font-medium text-gray-500">WBS Name</th>
								<th class="px-4 py-3 text-right font-medium text-gray-500">Budget</th>
								<th class="px-4 py-3 text-right font-medium text-gray-500">EV</th>
								<th class="px-4 py-3 text-right font-medium text-gray-500">AC</th>
								<th class="px-4 py-3 text-center font-medium text-gray-500">SPI</th>
								<th class="px-4 py-3 text-center font-medium text-gray-500">CPI</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200">
							{#each analysis.wbs_breakdown as w}
								<tr class="hover:bg-gray-50">
									<td class="px-4 py-3 font-medium">{w.wbs_name}</td>
									<td class="px-4 py-3 text-right font-mono">${fmt(w.metrics.bac)}</td>
									<td class="px-4 py-3 text-right font-mono">${fmt(w.metrics.ev)}</td>
									<td class="px-4 py-3 text-right font-mono">${fmt(w.metrics.ac)}</td>
									<td class="px-4 py-3 text-center">
										<span class="inline-flex items-center gap-1">
											<span class="w-2 h-2 rounded-full {w.metrics.spi >= 1.0 ? 'bg-green-500' : w.metrics.spi >= 0.9 ? 'bg-yellow-500' : 'bg-red-500'}"></span>
											{w.metrics.spi?.toFixed(2)}
										</span>
									</td>
									<td class="px-4 py-3 text-center">
										<span class="inline-flex items-center gap-1">
											<span class="w-2 h-2 rounded-full {w.metrics.cpi >= 1.0 ? 'bg-green-500' : w.metrics.cpi >= 0.9 ? 'bg-yellow-500' : 'bg-red-500'}"></span>
											{w.metrics.cpi?.toFixed(2)}
										</span>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	</div>
{/if}
