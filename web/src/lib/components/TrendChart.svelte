<script lang="ts">
	interface Props {
		data: (number | null)[];
		labels: string[];
		title: string;
		color?: string;
		height?: number;
		formatValue?: (v: number) => string;
	}

	let {
		data,
		labels,
		title,
		color = '#3b82f6',
		height = 200,
		formatValue = (v: number) => v.toFixed(1)
	}: Props = $props();

	const PADDING = { top: 20, right: 16, bottom: 40, left: 48 };
	const WIDTH = 480;

	const validData = $derived(
		data.map((v, i) => ({ v, i, label: labels[i] ?? `${i + 1}` })).filter((d) => d.v !== null && d.v !== undefined) as { v: number; i: number; label: string }[]
	);

	const minVal = $derived(validData.length > 0 ? Math.min(...validData.map((d) => d.v)) : 0);
	const maxVal = $derived(validData.length > 0 ? Math.max(...validData.map((d) => d.v)) : 100);

	const yMin = $derived(Math.max(0, minVal - (maxVal - minVal) * 0.15));
	const yMax = $derived(maxVal + (maxVal - minVal) * 0.15 || 100);
	const yRange = $derived(yMax - yMin || 1);

	const chartWidth = $derived(WIDTH - PADDING.left - PADDING.right);
	const chartHeight = $derived(height - PADDING.top - PADDING.bottom);

	const totalPoints = $derived(data.length);

	function xPos(idx: number): number {
		if (totalPoints <= 1) return chartWidth / 2;
		return (idx / (totalPoints - 1)) * chartWidth;
	}

	function yPos(val: number): number {
		return chartHeight - ((val - yMin) / yRange) * chartHeight;
	}

	const gridLines = $derived((() => {
		const count = 4;
		return Array.from({ length: count + 1 }, (_, i) => {
			const val = yMin + (yRange * i) / count;
			return { y: yPos(val), val };
		});
	})());

	// Build line path with gaps for null values
	const linePath = $derived((() => {
		let path = '';
		let inSegment = false;
		for (let i = 0; i < data.length; i++) {
			const v = data[i];
			if (v === null || v === undefined) {
				inSegment = false;
				continue;
			}
			const x = xPos(i);
			const y = yPos(v);
			if (!inSegment) {
				path += `M ${x} ${y} `;
				inSegment = true;
			} else {
				path += `L ${x} ${y} `;
			}
		}
		return path.trim();
	})());

	// X-axis labels: show first, last, and up to 4 intermediates if <=6 points, else first+last only
	const xLabels = $derived((() => {
		if (totalPoints === 0) return [];
		if (totalPoints === 1) return [{ i: 0, label: labels[0] ?? '1' }];
		const indices: number[] = [0];
		if (totalPoints <= 6) {
			for (let i = 1; i < totalPoints - 1; i++) indices.push(i);
		}
		indices.push(totalPoints - 1);
		return indices.map((i) => ({ i, label: labels[i] ?? `${i + 1}` }));
	})());
</script>

<div class="bg-white border border-gray-200 rounded-lg p-4">
	<p class="text-sm font-medium text-gray-700 mb-3">{title}</p>
	{#if validData.length === 0}
		<div class="flex items-center justify-center text-gray-400 text-sm" style="height: {height}px">
			No data available
		</div>
	{:else}
		<svg
			viewBox="0 0 {WIDTH} {height}"
			preserveAspectRatio="xMidYMid meet"
			class="w-full"
			style="height: {height}px"
			role="img"
			aria-label="{title} trend chart"
		>
			<g transform="translate({PADDING.left}, {PADDING.top})">
				<!-- Grid lines and Y-axis labels -->
				{#each gridLines as gl}
					<line
						x1="0"
						y1={gl.y}
						x2={chartWidth}
						y2={gl.y}
						stroke="#e5e7eb"
						stroke-width="1"
					/>
					<text
						x="-6"
						y={gl.y}
						text-anchor="end"
						dominant-baseline="middle"
						font-size="10"
						fill="#9ca3af"
					>{formatValue(gl.val)}</text>
				{/each}

				<!-- Line path -->
				{#if linePath}
					<path
						d={linePath}
						fill="none"
						stroke={color}
						stroke-width="2.5"
						stroke-linejoin="round"
						stroke-linecap="round"
					/>
				{/if}

				<!-- Data points -->
				{#each validData as pt}
					<circle
						cx={xPos(pt.i)}
						cy={yPos(pt.v)}
						r="4"
						fill={color}
						stroke="white"
						stroke-width="2"
					>
						<title>{pt.label}: {formatValue(pt.v)}</title>
					</circle>
				{/each}

				<!-- X-axis labels -->
				{#each xLabels as xl}
					<text
						x={xPos(xl.i)}
						y={chartHeight + 16}
						text-anchor="middle"
						font-size="10"
						fill="#6b7280"
					>{xl.label}</text>
				{/each}

				<!-- X-axis baseline -->
				<line
					x1="0"
					y1={chartHeight}
					x2={chartWidth}
					y2={chartHeight}
					stroke="#d1d5db"
					stroke-width="1"
				/>
			</g>
		</svg>
	{/if}
</div>
