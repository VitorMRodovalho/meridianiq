<script lang="ts">
	interface WaterfallItem {
		label: string;
		value: number;
		isTotal?: boolean;
	}

	interface Props {
		data: WaterfallItem[];
		title?: string;
		height?: number;
		positiveColor?: string;
		negativeColor?: string;
		totalColor?: string;
		formatValue?: (v: number) => string;
	}

	let {
		data,
		title = '',
		height = 240,
		positiveColor = '#10b981',
		negativeColor = '#ef4444',
		totalColor = '#3b82f6',
		formatValue = (v: number) => v.toFixed(1),
	}: Props = $props();

	const PADDING = { top: 16, right: 16, bottom: 52, left: 52 };
	const WIDTH = 480;

	const chartWidth = $derived(WIDTH - PADDING.left - PADDING.right);
	const chartHeight = $derived(height - PADDING.top - PADDING.bottom);

	// Compute cumulative positions
	const bars = $derived((() => {
		let running = 0;
		const result: { label: string; start: number; end: number; value: number; isTotal: boolean; color: string }[] = [];
		for (const item of data) {
			if (item.isTotal) {
				result.push({
					label: item.label,
					start: 0,
					end: item.value,
					value: item.value,
					isTotal: true,
					color: totalColor,
				});
				running = item.value;
			} else {
				const start = running;
				running += item.value;
				result.push({
					label: item.label,
					start,
					end: running,
					value: item.value,
					isTotal: false,
					color: item.value >= 0 ? positiveColor : negativeColor,
				});
			}
		}
		return result;
	})());

	const allVals = $derived(bars.flatMap((b) => [b.start, b.end]));
	const minVal = $derived(Math.min(0, ...allVals));
	const maxVal = $derived(Math.max(0, ...allVals));
	const valRange = $derived(maxVal - minVal || 1);
	const yPad = $derived(valRange * 0.1);
	const yLo = $derived(minVal - yPad);
	const yHi = $derived(maxVal + yPad);
	const ySpan = $derived(yHi - yLo || 1);

	function py(v: number): number {
		return chartHeight - ((v - yLo) / ySpan) * chartHeight;
	}

	const barW = $derived(Math.min(40, (chartWidth - 8) / data.length - 6));
	const gap = $derived((chartWidth - barW * data.length) / (data.length + 1));
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
				<!-- Zero line -->
				<line x1="0" y1={py(0)} x2={chartWidth} y2={py(0)} stroke="#d1d5db" stroke-width="1" />

				{#each bars as bar, i}
					{@const x = gap + i * (barW + gap)}
					{@const y1 = py(Math.max(bar.start, bar.end))}
					{@const y2 = py(Math.min(bar.start, bar.end))}
					{@const barH = Math.max(1, y2 - y1)}

					<!-- Bar -->
					<rect x={x} y={y1} width={barW} height={barH} rx="2" fill={bar.color} opacity="0.85">
						<title>{bar.label}: {formatValue(bar.value)}</title>
					</rect>

					<!-- Connector line to next bar -->
					{#if i < bars.length - 1 && !bar.isTotal}
						<line
							x1={x + barW}
							y1={py(bar.end)}
							x2={gap + (i + 1) * (barW + gap)}
							y2={py(bar.end)}
							stroke="#9ca3af"
							stroke-width="1"
							stroke-dasharray="3,2"
						/>
					{/if}

					<!-- Value label -->
					<text
						x={x + barW / 2}
						y={bar.value >= 0 ? y1 - 4 : y2 + 12}
						text-anchor="middle"
						font-size="9"
						fill="#374151"
					>
						{bar.value >= 0 ? '+' : ''}{formatValue(bar.value)}
					</text>

					<!-- X label -->
					<text
						x={x + barW / 2}
						y={chartHeight + 14}
						text-anchor="middle"
						font-size="9"
						fill="#6b7280"
						transform="rotate(-30, {x + barW / 2}, {chartHeight + 14})"
					>
						{bar.label.length > 10 ? bar.label.slice(0, 10) + '..' : bar.label}
					</text>
				{/each}
			</g>
		</svg>
	{/if}
</div>
