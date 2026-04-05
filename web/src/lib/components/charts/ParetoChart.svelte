<script lang="ts">
	interface ParetoPoint {
		x: number;
		y: number;
		label: string;
		isOptimal: boolean;
	}

	interface Props {
		points: ParetoPoint[];
		title?: string;
		xLabel?: string;
		yLabel?: string;
		height?: number;
	}

	let {
		points,
		title = 'Time-Cost Trade-Off',
		xLabel = 'Duration (days)',
		yLabel = 'Cost ($)',
		height = 280,
	}: Props = $props();

	const WIDTH = 600;
	const PAD = { top: 30, right: 30, bottom: 40, left: 70 };

	const chartW = $derived(WIDTH - PAD.left - PAD.right);
	const chartH = $derived(height - PAD.top - PAD.bottom);

	const xMin = $derived(Math.min(...points.map((p) => p.x)) * 0.95);
	const xMax = $derived(Math.max(...points.map((p) => p.x)) * 1.05);
	const yMin = $derived(Math.min(...points.map((p) => p.y)) * 0.95);
	const yMax = $derived(Math.max(...points.map((p) => p.y)) * 1.05);

	function xScale(v: number): number {
		const range = xMax - xMin || 1;
		return PAD.left + ((v - xMin) / range) * chartW;
	}

	function yScale(v: number): number {
		const range = yMax - yMin || 1;
		return PAD.top + chartH - ((v - yMin) / range) * chartH;
	}

	const frontier = $derived(
		points.filter((p) => p.isOptimal).sort((a, b) => a.x - b.x)
	);

	const frontierPath = $derived(
		frontier.length > 1
			? frontier.map((p, i) => `${i === 0 ? 'M' : 'L'}${xScale(p.x)},${yScale(p.y)}`).join(' ')
			: ''
	);

	function formatCost(v: number): string {
		if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
		if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
		return `$${v.toFixed(0)}`;
	}
</script>

<div class="bg-white border border-gray-200 rounded-lg p-4">
	{#if title}
		<p class="text-sm font-semibold text-gray-700 mb-2">{title}</p>
	{/if}

	{#if points.length === 0}
		<p class="text-gray-400 text-sm text-center py-8">No scenarios to display</p>
	{:else}
		<svg viewBox="0 0 {WIDTH} {height}" class="w-full">
			<!-- Grid -->
			{#each [0, 0.25, 0.5, 0.75, 1] as pct}
				<line
					x1={PAD.left} y1={PAD.top + pct * chartH}
					x2={WIDTH - PAD.right} y2={PAD.top + pct * chartH}
					stroke="#f3f4f6" stroke-width="1"
				/>
				<text x={PAD.left - 5} y={PAD.top + pct * chartH + 3} text-anchor="end" class="text-[8px] fill-gray-400">
					{formatCost(yMax - pct * (yMax - yMin))}
				</text>
			{/each}

			{#each [0, 0.25, 0.5, 0.75, 1] as pct}
				<text x={PAD.left + pct * chartW} y={height - PAD.bottom + 15} text-anchor="middle" class="text-[8px] fill-gray-400">
					{Math.round(xMin + pct * (xMax - xMin))}d
				</text>
			{/each}

			<!-- Frontier line -->
			{#if frontierPath}
				<path d={frontierPath} fill="none" stroke="#3b82f6" stroke-width="2" stroke-dasharray="6,3" />
			{/if}

			<!-- Points -->
			{#each points as point}
				<circle
					cx={xScale(point.x)}
					cy={yScale(point.y)}
					r={point.isOptimal ? 6 : 4}
					fill={point.isOptimal ? '#3b82f6' : '#9ca3af'}
					stroke={point.isOptimal ? '#1d4ed8' : '#6b7280'}
					stroke-width="1.5"
					opacity="0.85"
				>
					<title>{point.label}: {point.x.toFixed(0)}d, {formatCost(point.y)}{point.isOptimal ? ' (Pareto optimal)' : ''}</title>
				</circle>
				{#if point.isOptimal}
					<text x={xScale(point.x)} y={yScale(point.y) - 10} text-anchor="middle" class="text-[8px] fill-blue-600 font-medium">
						{point.label}
					</text>
				{/if}
			{/each}

			<!-- Axis labels -->
			<text x={WIDTH / 2} y={height - 5} text-anchor="middle" class="text-[9px] fill-gray-400 font-medium">{xLabel}</text>
			<text x="12" y={height / 2} text-anchor="middle" transform="rotate(-90, 12, {height / 2})" class="text-[9px] fill-gray-400 font-medium">{yLabel}</text>

			<!-- Axes -->
			<line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={PAD.top + chartH} stroke="#d1d5db" stroke-width="1" />
			<line x1={PAD.left} y1={PAD.top + chartH} x2={WIDTH - PAD.right} y2={PAD.top + chartH} stroke="#d1d5db" stroke-width="1" />
		</svg>

		<div class="flex items-center gap-4 mt-2 text-xs text-gray-500">
			<div class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-blue-500"></span> Pareto optimal</div>
			<div class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-gray-400"></span> Dominated</div>
			<div class="flex items-center gap-1"><span class="w-4 h-0.5 border-t-2 border-dashed border-blue-500"></span> Frontier</div>
		</div>
	{/if}
</div>
