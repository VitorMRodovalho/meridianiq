<script lang="ts">
	interface DataPoint {
		x: number;
		y: number;
		label: string;
		size?: number;
		color?: string;
	}

	interface Props {
		data: DataPoint[];
		title?: string;
		xLabel?: string;
		yLabel?: string;
		height?: number;
		defaultColor?: string;
	}

	let {
		data,
		title = '',
		xLabel = '',
		yLabel = '',
		height = 240,
		defaultColor = '#3b82f6',
	}: Props = $props();

	const PADDING = { top: 16, right: 16, bottom: 44, left: 52 };
	const WIDTH = 480;

	const chartWidth = $derived(WIDTH - PADDING.left - PADDING.right);
	const chartHeight = $derived(height - PADDING.top - PADDING.bottom);

	// Filter non-finite values so a malformed backend payload (NaN x/y)
	// doesn't propagate through the `$derived` graph into SVG attributes.
	const finiteData = $derived(
		data.filter((d) => Number.isFinite(d.x) && Number.isFinite(d.y))
	);

	const xMin = $derived(finiteData.length > 0 ? Math.min(...finiteData.map((d) => d.x)) : 0);
	const xMax = $derived(finiteData.length > 0 ? Math.max(...finiteData.map((d) => d.x)) : 100);
	const yMin = $derived(finiteData.length > 0 ? Math.min(...finiteData.map((d) => d.y)) : 0);
	const yMax = $derived(finiteData.length > 0 ? Math.max(...finiteData.map((d) => d.y)) : 100);

	const xRange = $derived(xMax - xMin || 1);
	const yRange = $derived(yMax - yMin || 1);

	// Add 10% padding to ranges
	const xLo = $derived(xMin - xRange * 0.1);
	const xHi = $derived(xMax + xRange * 0.1);
	const yLo = $derived(yMin - yRange * 0.1);
	const yHi = $derived(yMax + yRange * 0.1);
	const xSpan = $derived(xHi - xLo || 1);
	const ySpan = $derived(yHi - yLo || 1);

	function px(v: number): number {
		return ((v - xLo) / xSpan) * chartWidth;
	}

	function py(v: number): number {
		return chartHeight - ((v - yLo) / ySpan) * chartHeight;
	}

	const gridLinesX = $derived(Array.from({ length: 5 }, (_, i) => {
		const val = xLo + (xSpan * (i + 1)) / 6;
		return { x: px(val), val };
	}));

	const gridLinesY = $derived(Array.from({ length: 4 }, (_, i) => {
		const val = yLo + (ySpan * (i + 1)) / 5;
		return { y: py(val), val };
	}));
</script>

<div class="bg-white border border-gray-200 rounded-lg p-4">
	{#if title}
		<p class="text-sm font-medium text-gray-700 mb-3">{title}</p>
	{/if}
	{#if data.length === 0}
		<div class="flex items-center justify-center text-gray-400 text-sm" style="height: {height}px">
			No data
		</div>
	{:else}
		<svg viewBox="0 0 {WIDTH} {height}" preserveAspectRatio="xMidYMid meet" class="w-full" style="height: {height}px" role="img" aria-label="{title}">
			<g transform="translate({PADDING.left}, {PADDING.top})">
				<!-- Grid -->
				{#each gridLinesY as gl}
					<line x1="0" y1={gl.y} x2={chartWidth} y2={gl.y} stroke="#f3f4f6" stroke-width="1" />
					<text x="-6" y={gl.y} text-anchor="end" dominant-baseline="middle" font-size="9" fill="#9ca3af">
						{gl.val.toFixed(0)}
					</text>
				{/each}
				{#each gridLinesX as gl}
					<line x1={gl.x} y1="0" x2={gl.x} y2={chartHeight} stroke="#f3f4f6" stroke-width="1" />
					<text x={gl.x} y={chartHeight + 14} text-anchor="middle" font-size="9" fill="#9ca3af">
						{gl.val.toFixed(0)}
					</text>
				{/each}

				<!-- Axes -->
				<line x1="0" y1={chartHeight} x2={chartWidth} y2={chartHeight} stroke="#d1d5db" stroke-width="1" />
				<line x1="0" y1="0" x2="0" y2={chartHeight} stroke="#d1d5db" stroke-width="1" />

				<!-- Points (filtered to finite values to avoid SVG NaN attributes) -->
				{#each finiteData as pt}
					{@const r = pt.size ? Math.max(3, Math.min(12, pt.size)) : 5}
					<circle
						cx={px(pt.x)}
						cy={py(pt.y)}
						r={r}
						fill={pt.color ?? defaultColor}
						opacity="0.7"
						stroke="white"
						stroke-width="1.5"
					>
						<title>{pt.label}: ({pt.x.toFixed(1)}, {pt.y.toFixed(1)})</title>
					</circle>
				{/each}

				<!-- Axis labels -->
				{#if xLabel}
					<text x={chartWidth / 2} y={chartHeight + 32} text-anchor="middle" font-size="10" fill="#6b7280">{xLabel}</text>
				{/if}
				{#if yLabel}
					<text x="-36" y={chartHeight / 2} text-anchor="middle" font-size="10" fill="#6b7280"
						transform="rotate(-90, -36, {chartHeight / 2})">{yLabel}</text>
				{/if}
			</g>
		</svg>
	{/if}
</div>
