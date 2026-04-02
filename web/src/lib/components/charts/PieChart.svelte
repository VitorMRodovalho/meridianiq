<script lang="ts">
	interface Slice {
		label: string;
		value: number;
		color?: string;
	}

	interface Props {
		data: Slice[];
		title?: string;
		size?: number;
		donut?: boolean;
	}

	let {
		data,
		title = '',
		size = 200,
		donut = true,
	}: Props = $props();

	const defaultColors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#64748b'];

	const total = $derived(data.reduce((s, d) => s + d.value, 0));
	const cx = $derived(size / 2);
	const cy = $derived(size / 2);
	const r = $derived(size / 2 - 8);
	const innerR = $derived(donut ? r * 0.55 : 0);

	const arcs = $derived((() => {
		if (total === 0) return [];
		let startAngle = -Math.PI / 2;
		return data.filter((d) => d.value > 0).map((d, i) => {
			const pct = d.value / total;
			const angle = pct * Math.PI * 2;
			const endAngle = startAngle + angle;
			const largeArc = angle > Math.PI ? 1 : 0;

			const x1 = cx + r * Math.cos(startAngle);
			const y1 = cy + r * Math.sin(startAngle);
			const x2 = cx + r * Math.cos(endAngle);
			const y2 = cy + r * Math.sin(endAngle);

			const ix1 = cx + innerR * Math.cos(startAngle);
			const iy1 = cy + innerR * Math.sin(startAngle);
			const ix2 = cx + innerR * Math.cos(endAngle);
			const iy2 = cy + innerR * Math.sin(endAngle);

			const path = donut
				? `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} L ${ix2} ${iy2} A ${innerR} ${innerR} 0 ${largeArc} 0 ${ix1} ${iy1} Z`
				: `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`;

			const result = {
				path,
				color: d.color ?? defaultColors[i % defaultColors.length],
				label: d.label,
				value: d.value,
				pct: (pct * 100).toFixed(0),
			};

			startAngle = endAngle;
			return result;
		});
	})());
</script>

<div class="bg-white border border-gray-200 rounded-lg p-4">
	{#if title}
		<p class="text-sm font-medium text-gray-700 mb-3">{title}</p>
	{/if}
	{#if total === 0}
		<div class="flex items-center justify-center text-gray-400 text-sm" style="height: {size}px">
			No data
		</div>
	{:else}
		<div class="flex items-center gap-4 flex-wrap justify-center">
			<svg viewBox="0 0 {size} {size}" class="shrink-0" style="width: {size}px; height: {size}px" role="img" aria-label="{title}">
				{#each arcs as arc}
					<path d={arc.path} fill={arc.color} stroke="white" stroke-width="2">
						<title>{arc.label}: {arc.value} ({arc.pct}%)</title>
					</path>
				{/each}
				{#if donut}
					<text x={cx} y={cy - 6} text-anchor="middle" font-size="20" font-weight="700" fill="#1f2937">
						{total}
					</text>
					<text x={cx} y={cy + 12} text-anchor="middle" font-size="10" fill="#9ca3af">
						total
					</text>
				{/if}
			</svg>
			<!-- Legend -->
			<div class="flex flex-col gap-1.5">
				{#each arcs as arc}
					<div class="flex items-center gap-2 text-xs">
						<span class="w-3 h-3 rounded-sm shrink-0" style="background: {arc.color}"></span>
						<span class="text-gray-600">{arc.label}</span>
						<span class="font-medium text-gray-800 ml-auto">{arc.value} ({arc.pct}%)</span>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
