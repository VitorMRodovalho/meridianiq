<script lang="ts">
	interface Props {
		demandByDay: number[];
		maxUnits: number;
		title?: string;
		height?: number;
		rsrcName?: string;
	}

	let {
		demandByDay,
		maxUnits,
		title = 'Resource Utilization',
		height = 220,
		rsrcName = '',
	}: Props = $props();

	const WIDTH = 600;
	const PAD = { top: 30, right: 20, bottom: 30, left: 45 };

	const chartW = $derived(WIDTH - PAD.left - PAD.right);
	const chartH = $derived(height - PAD.top - PAD.bottom);

	// Downsample if too many days
	const maxBars = 60;
	const step = $derived(Math.max(1, Math.ceil(demandByDay.length / maxBars)));
	const sampled = $derived(
		demandByDay.filter((_: number, i: number) => i % step === 0)
	);

	const peakDemand = $derived(Math.max(...sampled, maxUnits, 1));
	const barW = $derived(Math.max(1, chartW / sampled.length - 1));

	function yScale(v: number): number {
		return PAD.top + chartH - (v / peakDemand) * chartH;
	}

	function xPos(i: number): number {
		return PAD.left + (i / sampled.length) * chartW;
	}

	const capacityY = $derived(yScale(maxUnits));

	// Tick marks for Y axis
	const yTicks = $derived(() => {
		const ticks: number[] = [];
		const tickStep = peakDemand <= 5 ? 1 : Math.ceil(peakDemand / 5);
		for (let v = 0; v <= peakDemand; v += tickStep) ticks.push(v);
		return ticks;
	});

	// X axis labels
	const xLabels = $derived(() => {
		const labels: { x: number; text: string }[] = [];
		const labelStep = Math.max(1, Math.floor(sampled.length / 6));
		for (let i = 0; i < sampled.length; i += labelStep) {
			labels.push({ x: xPos(i) + barW / 2, text: `D${i * step}` });
		}
		return labels;
	});
</script>

<div class="bg-white border border-gray-200 rounded-lg p-4">
	{#if title}
		<p class="text-sm font-semibold text-gray-700 mb-2">{title}{rsrcName ? ` — ${rsrcName}` : ''}</p>
	{/if}
	<svg viewBox="0 0 {WIDTH} {height}" class="w-full">
		<!-- Y axis ticks -->
		{#each yTicks() as tick}
			<line x1={PAD.left} y1={yScale(tick)} x2={WIDTH - PAD.right} y2={yScale(tick)}
				stroke="#f3f4f6" stroke-width="1" />
			<text x={PAD.left - 5} y={yScale(tick) + 3} text-anchor="end" class="text-[9px] fill-gray-400">
				{tick}
			</text>
		{/each}

		<!-- Demand bars -->
		{#each sampled as demand, i}
			{@const overloaded = demand > maxUnits}
			<rect
				x={xPos(i)}
				y={yScale(demand)}
				width={barW}
				height={Math.max(0, chartH - (yScale(demand) - PAD.top))}
				rx="1"
				fill={overloaded ? '#ef4444' : demand > maxUnits * 0.8 ? '#f59e0b' : '#3b82f6'}
				opacity="0.8"
			>
				<title>Day {i * step}: {demand} units{overloaded ? ' (OVERLOADED)' : ''}</title>
			</rect>
		{/each}

		<!-- Capacity line -->
		<line
			x1={PAD.left} y1={capacityY}
			x2={WIDTH - PAD.right} y2={capacityY}
			stroke="#ef4444" stroke-width="2" stroke-dasharray="6,3"
		/>
		<text x={WIDTH - PAD.right + 2} y={capacityY + 3} class="text-[9px] fill-red-500 font-semibold">
			Max: {maxUnits}
		</text>

		<!-- X axis labels -->
		{#each xLabels() as label}
			<text x={label.x} y={height - 8} text-anchor="middle" class="text-[9px] fill-gray-400">
				{label.text}
			</text>
		{/each}

		<!-- Axes -->
		<line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={PAD.top + chartH} stroke="#d1d5db" stroke-width="1" />
		<line x1={PAD.left} y1={PAD.top + chartH} x2={WIDTH - PAD.right} y2={PAD.top + chartH} stroke="#d1d5db" stroke-width="1" />
	</svg>

	<!-- Legend -->
	<div class="flex items-center gap-4 mt-2 text-xs text-gray-500">
		<div class="flex items-center gap-1">
			<span class="w-3 h-3 rounded bg-blue-500 opacity-80"></span> Normal
		</div>
		<div class="flex items-center gap-1">
			<span class="w-3 h-3 rounded bg-amber-500 opacity-80"></span> &gt;80% capacity
		</div>
		<div class="flex items-center gap-1">
			<span class="w-3 h-3 rounded bg-red-500 opacity-80"></span> Overloaded
		</div>
		<div class="flex items-center gap-1">
			<span class="w-3 h-1 border-t-2 border-dashed border-red-500"></span> Capacity limit
		</div>
	</div>
</div>
