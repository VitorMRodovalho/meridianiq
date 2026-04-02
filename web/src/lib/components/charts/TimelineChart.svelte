<script lang="ts">
	interface TimelineItem {
		label: string;
		start: string;
		end?: string;
		color?: string;
		marker?: boolean;
	}

	interface Props {
		data: TimelineItem[];
		title?: string;
		height?: number;
	}

	let {
		data,
		title = '',
		height = 200,
	}: Props = $props();

	const PADDING = { top: 16, right: 16, bottom: 40, left: 120 };
	const WIDTH = 560;

	const chartWidth = $derived(WIDTH - PADDING.left - PADDING.right);
	const chartHeight = $derived(height - PADDING.top - PADDING.bottom);

	const defaultColors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

	const allDates = $derived((() => {
		const dates: number[] = [];
		for (const item of data) {
			dates.push(new Date(item.start).getTime());
			if (item.end) dates.push(new Date(item.end).getTime());
		}
		return dates;
	})());

	const tMin = $derived(allDates.length > 0 ? Math.min(...allDates) : 0);
	const tMax = $derived(allDates.length > 0 ? Math.max(...allDates) : 1);
	const tRange = $derived(tMax - tMin || 86400000);

	function tx(dateStr: string): number {
		const t = new Date(dateStr).getTime();
		return ((t - tMin) / tRange) * chartWidth;
	}

	function formatDate(d: string): string {
		return new Date(d).toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
	}

	const rowH = $derived(Math.min(28, (chartHeight - 8) / data.length - 4));

	// Time axis ticks (4-5 ticks)
	const timeTicks = $derived((() => {
		const count = 4;
		return Array.from({ length: count + 1 }, (_, i) => {
			const t = tMin + (tRange * i) / count;
			return { x: (i / count) * chartWidth, label: formatDate(new Date(t).toISOString()) };
		});
	})());
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
				<!-- Time axis ticks -->
				{#each timeTicks as tick}
					<line x1={tick.x} y1="0" x2={tick.x} y2={chartHeight} stroke="#f3f4f6" stroke-width="1" />
					<text x={tick.x} y={chartHeight + 16} text-anchor="middle" font-size="9" fill="#9ca3af">{tick.label}</text>
				{/each}

				<!-- Items -->
				{#each data as item, i}
					{@const y = i * (rowH + 4)}
					{@const color = item.color ?? defaultColors[i % defaultColors.length]}

					<!-- Label -->
					<text x="-8" y={y + rowH / 2} text-anchor="end" dominant-baseline="middle" font-size="10" fill="#374151">
						{item.label.length > 16 ? item.label.slice(0, 16) + '..' : item.label}
					</text>

					{#if item.marker || !item.end}
						<!-- Diamond marker for milestones -->
						{@const mx = tx(item.start)}
						<polygon
							points="{mx},{y + 2} {mx + rowH / 2},{y + rowH / 2} {mx},{y + rowH - 2} {mx - rowH / 2},{y + rowH / 2}"
							fill={color}
							opacity="0.8"
						>
							<title>{item.label}: {formatDate(item.start)}</title>
						</polygon>
					{:else}
						<!-- Bar for date ranges -->
						{@const x1 = tx(item.start)}
						{@const x2 = tx(item.end)}
						<rect
							x={Math.min(x1, x2)}
							y={y + 2}
							width={Math.max(2, Math.abs(x2 - x1))}
							height={rowH - 4}
							rx="3"
							fill={color}
							opacity="0.75"
						>
							<title>{item.label}: {formatDate(item.start)} — {formatDate(item.end)}</title>
						</rect>
					{/if}
				{/each}

				<!-- Baseline -->
				<line x1="0" y1={chartHeight} x2={chartWidth} y2={chartHeight} stroke="#d1d5db" stroke-width="1" />
			</g>
		</svg>
	{/if}
</div>
