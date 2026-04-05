<script lang="ts">
	interface GanttItem {
		id: string;
		label: string;
		start: number;
		duration: number;
		color?: string;
		isCritical?: boolean;
		progress?: number;
	}

	interface Props {
		items: GanttItem[];
		title?: string;
		totalDuration?: number;
		height?: number;
	}

	let {
		items,
		title = '',
		totalDuration = 0,
		height = 0,
	}: Props = $props();

	const WIDTH = 700;
	const PAD = { top: 25, right: 20, bottom: 20, left: 130 };
	const rowH = 22;
	const barH = 14;

	const chartW = $derived(WIDTH - PAD.left - PAD.right);
	const maxDur = $derived(totalDuration || Math.max(...items.map((i) => i.start + i.duration), 1));
	const svgH = $derived(height || PAD.top + items.length * rowH + PAD.bottom);

	function xScale(d: number): number {
		return PAD.left + (d / maxDur) * chartW;
	}

	const timeMarks = $derived(() => {
		const marks: number[] = [];
		const step = Math.max(1, Math.ceil(maxDur / 6));
		for (let d = 0; d <= maxDur; d += step) marks.push(d);
		return marks;
	});
</script>

<div class="bg-white border border-gray-200 rounded-lg p-4">
	{#if title}
		<p class="text-sm font-semibold text-gray-700 mb-2">{title}</p>
	{/if}

	{#if items.length === 0}
		<p class="text-gray-400 text-sm text-center py-6">No activities to display</p>
	{:else}
		<svg viewBox="0 0 {WIDTH} {svgH}" class="w-full" style="min-width: 500px;">
			<!-- Time grid -->
			{#each timeMarks() as mark}
				<line
					x1={xScale(mark)} y1={PAD.top - 5}
					x2={xScale(mark)} y2={svgH - PAD.bottom}
					stroke="#f3f4f6" stroke-width="1"
				/>
				<text x={xScale(mark)} y={PAD.top - 10} text-anchor="middle" class="text-[8px] fill-gray-400">
					D{mark}
				</text>
			{/each}

			<!-- Activity bars -->
			{#each items as item, i}
				{@const y = PAD.top + i * rowH}
				{@const x = xScale(item.start)}
				{@const w = Math.max(2, xScale(item.start + item.duration) - x)}
				{@const fill = item.color || (item.isCritical ? '#ef4444' : '#3b82f6')}

				<!-- Label -->
				<text x={PAD.left - 5} y={y + barH / 2 + 4} text-anchor="end" class="text-[9px] fill-gray-600">
					{item.label.length > 18 ? item.label.slice(0, 18) + '...' : item.label}
				</text>

				<!-- Background bar -->
				<rect {x} {y} width={w} height={barH} rx="2" fill={fill} opacity="0.25" />

				<!-- Progress fill -->
				{#if item.progress && item.progress > 0}
					<rect {x} {y} width={w * Math.min(item.progress / 100, 1)} height={barH} rx="2" {fill} opacity="0.8" />
				{:else}
					<rect {x} {y} width={w} height={barH} rx="2" {fill} opacity="0.7" />
				{/if}

				<!-- Duration label -->
				{#if w > 25}
					<text x={x + w / 2} y={y + barH / 2 + 3} text-anchor="middle" class="text-[7px] fill-white font-medium">
						{item.duration.toFixed(0)}d
					</text>
				{/if}
			{/each}

			<!-- Axes -->
			<line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={svgH - PAD.bottom} stroke="#d1d5db" stroke-width="1" />
		</svg>
	{/if}
</div>
