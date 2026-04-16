<script lang="ts">
	interface SCurvePoint {
		date: string;
		cumulative_pv: number;
		cumulative_ev: number;
		cumulative_ac: number;
	}

	interface Props {
		data: SCurvePoint[];
		dataDate?: string;
		bac?: number;
		eac?: number;
		spi?: number;
		cpi?: number;
		sv?: number;
		cv?: number;
		height?: number;
		title?: string;
		showKPI?: boolean;
	}

	let {
		data,
		dataDate = '',
		bac = 0,
		eac = 0,
		spi = 0,
		cpi = 0,
		sv = 0,
		cv = 0,
		height = 360,
		title = 'EVM S-Curve',
		showKPI = true,
	}: Props = $props();

	const WIDTH = 800;
	const PAD_TOP = 28;
	const PAD_BOTTOM = 52;
	const PAD_LEFT = 64;
	const padRight = $derived(showKPI ? 200 : 16);

	const chartW = $derived(WIDTH - PAD_LEFT - padRight);
	const chartH = $derived(height - PAD_TOP - PAD_BOTTOM);

	// Find max value across all series + BAC/EAC
	const yMax = $derived.by(() => {
		let max = 0;
		for (const p of data) {
			if (p.cumulative_pv > max) max = p.cumulative_pv;
			if (p.cumulative_ev > max) max = p.cumulative_ev;
			if (p.cumulative_ac > max) max = p.cumulative_ac;
		}
		if (bac > max) max = bac;
		if (eac > max) max = eac;
		return max * 1.1 || 1;
	});

	// X/Y mapping
	function xPos(i: number): number {
		if (data.length <= 1) return chartW / 2;
		return (i / (data.length - 1)) * chartW;
	}

	function yPos(val: number): number {
		return chartH - (val / yMax) * chartH;
	}

	// Build SVG path string from array of [x,y] points
	function buildPath(points: [number, number][]): string {
		if (points.length === 0) return '';
		return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
	}

	// Build closed area path (for shading between two curves)
	function buildAreaPath(upper: [number, number][], lower: [number, number][]): string {
		if (upper.length === 0) return '';
		const fwd = upper.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
		const rev = [...lower].reverse().map(p => `L${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
		return `${fwd} ${rev} Z`;
	}

	// Series paths
	const pvPoints = $derived(data.map((p, i): [number, number] => [xPos(i), yPos(p.cumulative_pv)]));
	const evPoints = $derived(data.map((p, i): [number, number] => [xPos(i), yPos(p.cumulative_ev)]));
	const acPoints = $derived(data.map((p, i): [number, number] => [xPos(i), yPos(p.cumulative_ac)]));

	const pvPath = $derived(buildPath(pvPoints));
	const evPath = $derived(buildPath(evPoints));
	const acPath = $derived(buildPath(acPoints));

	// SV shaded area (between PV and EV up to data date)
	const dataDateIdx = $derived(dataDate ? data.findIndex(p => p.date >= dataDate) : data.length - 1);
	const effectiveIdx = $derived(dataDateIdx >= 0 ? dataDateIdx : data.length - 1);

	const svAreaPath = $derived.by(() => {
		const upper = pvPoints.slice(0, effectiveIdx + 1);
		const lower = evPoints.slice(0, effectiveIdx + 1);
		return buildAreaPath(upper, lower);
	});

	// CV shaded area (between EV and AC up to data date)
	const cvAreaPath = $derived.by(() => {
		const upper = evPoints.slice(0, effectiveIdx + 1);
		const lower = acPoints.slice(0, effectiveIdx + 1);
		return buildAreaPath(upper, lower);
	});

	// Data date X position
	const dataDateX = $derived(effectiveIdx >= 0 ? xPos(effectiveIdx) : -1);

	// Y-axis ticks (5 ticks)
	const yTicks = $derived.by(() => {
		const ticks: { value: number; y: number; label: string }[] = [];
		const step = yMax / 5;
		for (let i = 0; i <= 5; i++) {
			const val = step * i;
			ticks.push({ value: val, y: yPos(val), label: formatCompact(val) });
		}
		return ticks;
	});

	// X-axis ticks (max ~8 labels)
	const xTicks = $derived.by(() => {
		if (data.length === 0) return [];
		const maxLabels = 8;
		const step = Math.max(1, Math.ceil(data.length / maxLabels));
		const ticks: { x: number; label: string }[] = [];
		for (let i = 0; i < data.length; i += step) {
			const d = new Date(data[i].date + 'T00:00:00');
			ticks.push({
				x: xPos(i),
				label: d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' }),
			});
		}
		return ticks;
	});

	function formatCompact(v: number): string {
		if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
		if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
		return v.toFixed(0);
	}

	function formatCost(v: number): string {
		if (!v) return '$0';
		if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
		if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
		return `$${v.toFixed(0)}`;
	}

	function indexColor(val: number): string {
		if (val >= 0.95) return '#10b981';
		if (val >= 0.85) return '#f59e0b';
		return '#ef4444';
	}
</script>

<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
	{#if title}
		<div class="flex items-center justify-between mb-2">
			<p class="text-sm font-semibold text-gray-700 dark:text-gray-300">{title}</p>
			<span class="text-[9px] text-gray-400">ANSI/EIA-748</span>
		</div>
	{/if}

	{#if data.length < 2}
		<div class="flex items-center justify-center text-gray-400 text-sm" style="height: {height}px">
			Insufficient S-Curve data (need 2+ time periods)
		</div>
	{:else}
		<svg viewBox="0 0 {WIDTH} {height}" preserveAspectRatio="xMidYMid meet" class="w-full" style="height: {height}px" role="img" aria-label="{title}">
			<g transform="translate({PAD_LEFT}, {PAD_TOP})">
				<!-- Grid lines -->
				{#each yTicks as tick}
					<line x1="0" y1={tick.y} x2={chartW} y2={tick.y} stroke="#e5e7eb" stroke-width="0.5" class="dark:stroke-gray-700" />
					<text x="-8" y={tick.y + 3} text-anchor="end" font-size="9" fill="#9ca3af" class="dark:fill-gray-500">{tick.label}</text>
				{/each}

				<!-- BAC reference line -->
				{#if bac > 0}
					{@const bacY = yPos(bac)}
					<line x1="0" y1={bacY} x2={chartW} y2={bacY} stroke="#9ca3af" stroke-width="1" stroke-dasharray="6 3" opacity="0.6" />
					<text x={chartW + 4} y={bacY + 3} font-size="8" fill="#9ca3af">BAC</text>
				{/if}

				<!-- EAC reference line -->
				{#if eac > 0 && eac !== bac}
					{@const eacY = yPos(eac)}
					<line x1="0" y1={eacY} x2={chartW} y2={eacY} stroke="#8b5cf6" stroke-width="1" stroke-dasharray="4 2" opacity="0.5" />
					<text x={chartW + 4} y={eacY + 3} font-size="8" fill="#8b5cf6">EAC</text>
				{/if}

				<!-- SV shaded area (PV vs EV) -->
				{#if svAreaPath}
					<path d={svAreaPath} fill="#3b82f6" opacity="0.08" />
				{/if}

				<!-- CV shaded area (EV vs AC) -->
				{#if cvAreaPath}
					<path d={cvAreaPath} fill="#ef4444" opacity="0.06" />
				{/if}

				<!-- PV curve (blue) -->
				<path d={pvPath} fill="none" stroke="#3b82f6" stroke-width="2" opacity="0.9" />

				<!-- EV curve (green) -->
				<path d={evPath} fill="none" stroke="#10b981" stroke-width="2.5" opacity="0.9" />

				<!-- AC curve (orange/red) -->
				<path d={acPath} fill="none" stroke="#f97316" stroke-width="2" opacity="0.9" />

				<!-- Data date vertical line -->
				{#if dataDateX >= 0}
					<line x1={dataDateX} y1="0" x2={dataDateX} y2={chartH} stroke="#dc2626" stroke-width="1.5" stroke-dasharray="5 3" opacity="0.7" />
					<text x={dataDateX} y="-6" text-anchor="middle" font-size="8" fill="#dc2626" font-weight="bold">Data Date</text>
				{/if}

				<!-- Endpoint dots -->
				{#if pvPoints.length > 0}
					{@const last = pvPoints[pvPoints.length - 1]}
					<circle cx={last[0]} cy={last[1]} r="3" fill="#3b82f6" />
				{/if}
				{#if evPoints.length > 0}
					{@const last = evPoints[effectiveIdx] || evPoints[evPoints.length - 1]}
					<circle cx={last[0]} cy={last[1]} r="3.5" fill="#10b981" />
				{/if}
				{#if acPoints.length > 0}
					{@const last = acPoints[effectiveIdx] || acPoints[acPoints.length - 1]}
					<circle cx={last[0]} cy={last[1]} r="3" fill="#f97316" />
				{/if}

				<!-- VAC annotation (BAC vs EAC) -->
				{#if bac > 0 && eac > 0}
					{@const vac = bac - eac}
					{@const vacColor = vac >= 0 ? '#10b981' : '#ef4444'}
					<text x={chartW + 4} y={yPos((bac + eac) / 2) + 3} font-size="7" fill={vacColor} font-weight="bold">
						VAC: {vac >= 0 ? '+' : ''}{formatCompact(vac)}
					</text>
				{/if}

				<!-- X-axis labels -->
				{#each xTicks as tick}
					<text x={tick.x} y={chartH + 16} text-anchor="middle" font-size="9" fill="#9ca3af"
						transform="rotate(-25, {tick.x}, {chartH + 16})">
						{tick.label}
					</text>
				{/each}

				<!-- Axes -->
				<line x1="0" y1="0" x2="0" y2={chartH} stroke="#d1d5db" stroke-width="1" class="dark:stroke-gray-600" />
				<line x1="0" y1={chartH} x2={chartW} y2={chartH} stroke="#d1d5db" stroke-width="1" class="dark:stroke-gray-600" />
			</g>

			<!-- KPI Summary Panel (right side) -->
			{#if showKPI}
				{@const kpiX = WIDTH - padRight + 16}
				{@const kpiY = PAD_TOP + 4}

				<g transform="translate({kpiX}, {kpiY})">
					<text x="0" y="0" font-size="10" font-weight="bold" fill="#374151" class="dark:fill-gray-300">KPI Summary</text>

					<!-- SPI -->
					<text x="0" y="22" font-size="9" fill="#6b7280">SPI</text>
					<text x="80" y="22" font-size="12" font-weight="bold" fill={indexColor(spi)} text-anchor="end">{spi.toFixed(2)}</text>

					<!-- CPI -->
					<text x="0" y="40" font-size="9" fill="#6b7280">CPI</text>
					<text x="80" y="40" font-size="12" font-weight="bold" fill={indexColor(cpi)} text-anchor="end">{cpi.toFixed(2)}</text>

					<line x1="0" y1="48" x2="80" y2="48" stroke="#e5e7eb" stroke-width="0.5" class="dark:stroke-gray-700" />

					<!-- SV -->
					<text x="0" y="64" font-size="9" fill="#6b7280">SV</text>
					<text x="80" y="64" font-size="10" font-weight="600" fill={sv >= 0 ? '#10b981' : '#ef4444'} text-anchor="end">{formatCost(sv)}</text>

					<!-- CV -->
					<text x="0" y="80" font-size="9" fill="#6b7280">CV</text>
					<text x="80" y="80" font-size="10" font-weight="600" fill={cv >= 0 ? '#10b981' : '#ef4444'} text-anchor="end">{formatCost(cv)}</text>

					<line x1="0" y1="88" x2="80" y2="88" stroke="#e5e7eb" stroke-width="0.5" class="dark:stroke-gray-700" />

					<!-- BAC/EAC -->
					<text x="0" y="104" font-size="9" fill="#6b7280">BAC</text>
					<text x="80" y="104" font-size="10" fill="#374151" text-anchor="end" class="dark:fill-gray-300">{formatCost(bac)}</text>

					<text x="0" y="120" font-size="9" fill="#6b7280">EAC</text>
					<text x="80" y="120" font-size="10" fill="#8b5cf6" text-anchor="end">{formatCost(eac)}</text>

					<!-- VAC -->
					{#if bac > 0 && eac > 0}
						{@const vac = bac - eac}
						<text x="0" y="136" font-size="9" fill="#6b7280">VAC</text>
						<text x="80" y="136" font-size="10" font-weight="600" fill={vac >= 0 ? '#10b981' : '#ef4444'} text-anchor="end">{formatCost(vac)}</text>
					{/if}
				</g>
			{/if}

			<!-- Legend -->
			<g transform="translate({PAD_LEFT}, {height - 14})">
				<circle cx="0" cy="0" r="4" fill="#3b82f6" />
				<text x="8" y="3" font-size="9" fill="#6b7280">PV</text>

				<circle cx="40" cy="0" r="4" fill="#10b981" />
				<text x="48" y="3" font-size="9" fill="#6b7280">EV</text>

				<circle cx="80" cy="0" r="4" fill="#f97316" />
				<text x="88" y="3" font-size="9" fill="#6b7280">AC</text>

				{#if bac > 0}
					<line x1="120" y1="0" x2="136" y2="0" stroke="#9ca3af" stroke-width="1" stroke-dasharray="4 2" />
					<text x="140" y="3" font-size="9" fill="#6b7280">BAC</text>
				{/if}

				{#if eac > 0 && eac !== bac}
					<line x1="172" y1="0" x2="188" y2="0" stroke="#8b5cf6" stroke-width="1" stroke-dasharray="4 2" />
					<text x="192" y="3" font-size="9" fill="#6b7280">EAC</text>
				{/if}

				{#if dataDateX >= 0}
					<line x1="224" y1="-4" x2="224" y2="4" stroke="#dc2626" stroke-width="1.5" stroke-dasharray="3 2" />
					<text x="230" y="3" font-size="9" fill="#6b7280">Data Date</text>
				{/if}
			</g>
		</svg>
	{/if}
</div>
