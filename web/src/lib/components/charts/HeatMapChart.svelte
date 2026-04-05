<script lang="ts">
	interface HeatMapItem {
		x: number;
		y: number;
		label?: string;
	}

	interface Props {
		items: HeatMapItem[];
		title?: string;
		xLabel?: string;
		yLabel?: string;
		size?: number;
	}

	let {
		items,
		title = 'Risk Heat Map',
		xLabel = 'Impact (days)',
		yLabel = 'Probability',
		size = 320,
	}: Props = $props();

	const PAD = { top: 30, right: 20, bottom: 40, left: 55 };
	const gridSize = 5;

	const cellW = $derived((size - PAD.left - PAD.right) / gridSize);
	const cellH = $derived((size - PAD.top - PAD.bottom) / gridSize);

	// Risk matrix colors (green → yellow → orange → red)
	const matrixColors = [
		['#dcfce7', '#fef9c3', '#fef9c3', '#fed7aa', '#fed7aa'],
		['#dcfce7', '#fef9c3', '#fed7aa', '#fed7aa', '#fca5a5'],
		['#fef9c3', '#fed7aa', '#fed7aa', '#fca5a5', '#fca5a5'],
		['#fef9c3', '#fed7aa', '#fca5a5', '#fca5a5', '#ef4444'],
		['#fed7aa', '#fca5a5', '#fca5a5', '#ef4444', '#ef4444'],
	];

	const probLabels = ['0-20%', '20-40%', '40-60%', '60-80%', '80-100%'];
	const impactLabels = ['1-5d', '5-15d', '15-30d', '30-60d', '60d+'];

	function probToRow(p: number): number {
		if (p >= 0.8) return 4;
		if (p >= 0.6) return 3;
		if (p >= 0.4) return 2;
		if (p >= 0.2) return 1;
		return 0;
	}

	function impactToCol(d: number): number {
		if (d >= 60) return 4;
		if (d >= 30) return 3;
		if (d >= 15) return 2;
		if (d >= 5) return 1;
		return 0;
	}

	// Count items per cell
	const cellCounts = $derived(() => {
		const counts: number[][] = Array.from({ length: gridSize }, () => Array(gridSize).fill(0));
		for (const item of items) {
			const row = probToRow(item.y);
			const col = impactToCol(item.x);
			counts[row][col]++;
		}
		return counts;
	});
</script>

<div class="bg-white border border-gray-200 rounded-lg p-4">
	{#if title}
		<p class="text-sm font-semibold text-gray-700 mb-2">{title}</p>
	{/if}
	<svg viewBox="0 0 {size} {size}" class="w-full" style="max-width: {size}px;">
		<!-- Grid cells -->
		{#each { length: gridSize } as _, row}
			{#each { length: gridSize } as _, col}
				{@const x = PAD.left + col * cellW}
				{@const y = PAD.top + (gridSize - 1 - row) * cellH}
				{@const count = cellCounts()[row][col]}
				<rect
					{x} {y}
					width={cellW - 1}
					height={cellH - 1}
					fill={matrixColors[row][col]}
					stroke="#e5e7eb"
					stroke-width="0.5"
					rx="2"
				>
					<title>{probLabels[row]} / {impactLabels[col]}: {count} risks</title>
				</rect>
				{#if count > 0}
					<text
						x={x + cellW / 2}
						y={y + cellH / 2 + 5}
						text-anchor="middle"
						class="text-[12px] font-bold fill-gray-700"
					>{count}</text>
				{/if}
			{/each}
		{/each}

		<!-- Y axis labels -->
		{#each probLabels as label, i}
			<text
				x={PAD.left - 5}
				y={PAD.top + (gridSize - 1 - i) * cellH + cellH / 2 + 3}
				text-anchor="end"
				class="text-[8px] fill-gray-500"
			>{label}</text>
		{/each}

		<!-- X axis labels -->
		{#each impactLabels as label, i}
			<text
				x={PAD.left + i * cellW + cellW / 2}
				y={size - PAD.bottom + 15}
				text-anchor="middle"
				class="text-[8px] fill-gray-500"
			>{label}</text>
		{/each}

		<!-- Axis titles -->
		<text x={size / 2} y={size - 5} text-anchor="middle" class="text-[9px] fill-gray-400 font-medium">{xLabel}</text>
		<text
			x="12"
			y={size / 2}
			text-anchor="middle"
			transform="rotate(-90, 12, {size / 2})"
			class="text-[9px] fill-gray-400 font-medium"
		>{yLabel}</text>

		<!-- Risk dots -->
		{#each items as item}
			{@const col = impactToCol(item.x)}
			{@const row = probToRow(item.y)}
			{@const cx = PAD.left + col * cellW + cellW / 2}
			{@const cy = PAD.top + (gridSize - 1 - row) * cellH + cellH / 2}
			<circle
				{cx} {cy}
				r="4"
				fill="#1e293b"
				opacity="0.6"
			>
				<title>{item.label || ''}: P={item.y}, I={item.x}d</title>
			</circle>
		{/each}
	</svg>

	<!-- Legend -->
	<div class="flex items-center justify-center gap-3 mt-2 text-xs text-gray-500">
		<div class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-green-100 border border-gray-200"></span> Low</div>
		<div class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-yellow-100 border border-gray-200"></span> Medium</div>
		<div class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-orange-200 border border-gray-200"></span> High</div>
		<div class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-red-400 border border-gray-200"></span> Critical</div>
	</div>
</div>
