<script lang="ts">
	interface BarItem {
		label: string;
		value: number;
		color?: string;
		threshold?: number;
	}

	interface Props {
		data: BarItem[];
		title?: string;
		height?: number;
		horizontal?: boolean;
		showValues?: boolean;
		formatValue?: (v: number) => string;
		thresholdColor?: string;
	}

	let {
		data,
		title = '',
		height = 220,
		horizontal = false,
		showValues = true,
		formatValue = (v: number) => v.toFixed(1),
		thresholdColor = '#dc2626',
	}: Props = $props();

	const PADDING = { top: 16, right: 16, bottom: 48, left: 52 };
	const WIDTH = 480;

	const chartWidth = $derived(WIDTH - PADDING.left - PADDING.right);
	const chartHeight = $derived(height - PADDING.top - PADDING.bottom);

	const maxVal = $derived(Math.max(...data.map((d) => Math.max(d.value, d.threshold ?? 0)), 1));
	const yMax = $derived(maxVal * 1.15);

	const defaultColors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

	// Precomputed bar dimensions
	const hBarH = $derived(Math.min(28, data.length > 0 ? (chartHeight - 8) / data.length - 4 : 28));
	const vBarW = $derived(Math.min(48, data.length > 0 ? (chartWidth - 8) / data.length - 4 : 48));
	const vGap = $derived(data.length > 0 ? (chartWidth - vBarW * data.length) / (data.length + 1) : 0);

	function barColor(item: BarItem, i: number): string {
		return item.color ?? defaultColors[i % defaultColors.length];
	}
</script>

<div class="bg-white border border-gray-200 rounded-lg p-4">
	{#if title}
		<p class="text-sm font-medium text-gray-700 mb-3">{title}</p>
	{/if}
	{#if data.length === 0}
		<div class="flex items-center justify-center text-gray-400 text-sm" style="height: {height}px">
			No data
		</div>
	{:else if horizontal}
		<!-- Horizontal bars -->
		<svg viewBox="0 0 {WIDTH} {height}" preserveAspectRatio="xMidYMid meet" class="w-full" style="height: {height}px" role="img" aria-label="{title}">
			<g transform="translate({PADDING.left + 40}, {PADDING.top})">
				{#each data as item, i}
					{@const y = i * (hBarH + 4)}
					{@const w = (item.value / yMax) * (chartWidth - 40)}
					<!-- Label -->
					<text x="-4" y={y + hBarH / 2} text-anchor="end" dominant-baseline="middle" font-size="10" fill="#6b7280">
						{item.label.length > 12 ? item.label.slice(0, 12) + '...' : item.label}
					</text>
					<!-- Bar -->
					<rect x="0" y={y} width={Math.max(0, w)} height={hBarH} rx="3" fill={barColor(item, i)} opacity="0.85">
						<title>{item.label}: {formatValue(item.value)}</title>
					</rect>
					<!-- Threshold marker -->
					{#if item.threshold !== undefined}
						{@const tx = (item.threshold / yMax) * (chartWidth - 40)}
						<line x1={tx} y1={y - 2} x2={tx} y2={y + hBarH + 2} stroke={thresholdColor} stroke-width="2" stroke-dasharray="4,2" />
					{/if}
					<!-- Value label -->
					{#if showValues}
						<text x={Math.max(0, w) + 4} y={y + hBarH / 2} dominant-baseline="middle" font-size="10" fill="#374151">
							{formatValue(item.value)}
						</text>
					{/if}
				{/each}
			</g>
		</svg>
	{:else}
		<!-- Vertical bars -->
		<svg viewBox="0 0 {WIDTH} {height}" preserveAspectRatio="xMidYMid meet" class="w-full" style="height: {height}px" role="img" aria-label="{title}">
			<g transform="translate({PADDING.left}, {PADDING.top})">
				{#each data as item, i}
					{@const x = vGap + i * (vBarW + vGap)}
					{@const h = (item.value / yMax) * chartHeight}
					{@const y = chartHeight - h}
					<!-- Bar -->
					<rect x={x} y={y} width={vBarW} height={h} rx="3" fill={barColor(item, i)} opacity="0.85">
						<title>{item.label}: {formatValue(item.value)}</title>
					</rect>
					<!-- Threshold marker -->
					{#if item.threshold !== undefined}
						{@const ty = chartHeight - (item.threshold / yMax) * chartHeight}
						<line x1={x - 4} y1={ty} x2={x + vBarW + 4} y2={ty} stroke={thresholdColor} stroke-width="2" stroke-dasharray="4,2" />
					{/if}
					<!-- Value label -->
					{#if showValues}
						<text x={x + vBarW / 2} y={y - 4} text-anchor="middle" font-size="9" fill="#374151">
							{formatValue(item.value)}
						</text>
					{/if}
					<!-- X label -->
					<text x={x + vBarW / 2} y={chartHeight + 14} text-anchor="middle" font-size="9" fill="#6b7280"
						transform="rotate(-30, {x + vBarW / 2}, {chartHeight + 14})">
						{item.label.length > 10 ? item.label.slice(0, 10) + '..' : item.label}
					</text>
				{/each}
				<!-- Baseline -->
				<line x1="0" y1={chartHeight} x2={chartWidth} y2={chartHeight} stroke="#d1d5db" stroke-width="1" />
			</g>
		</svg>
	{/if}
</div>
