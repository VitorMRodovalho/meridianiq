<script lang="ts">
	interface Props {
		value: number;
		min?: number;
		max?: number;
		title?: string;
		label?: string;
		size?: number;
		bands?: { threshold: number; color: string }[];
	}

	let {
		value,
		min = 0,
		max = 100,
		title = '',
		label = '',
		size = 180,
		bands = [
			{ threshold: 50, color: '#ef4444' },
			{ threshold: 70, color: '#f59e0b' },
			{ threshold: 85, color: '#3b82f6' },
			{ threshold: 100, color: '#10b981' },
		],
	}: Props = $props();

	const cx = $derived(size / 2);
	const cy = $derived(size / 2 + 10);
	const r = $derived(size / 2 - 16);
	const strokeW = 16;

	// Arc from -180deg to 0deg (semicircle, left to right)
	const startAngle = -Math.PI;
	const endAngle = 0;

	function angleForValue(v: number): number {
		const pct = Math.max(0, Math.min(1, (v - min) / (max - min)));
		return startAngle + pct * (endAngle - startAngle);
	}

	function arcPath(fromAngle: number, toAngle: number, radius: number): string {
		const x1 = cx + radius * Math.cos(fromAngle);
		const y1 = cy + radius * Math.sin(fromAngle);
		const x2 = cx + radius * Math.cos(toAngle);
		const y2 = cy + radius * Math.sin(toAngle);
		const largeArc = toAngle - fromAngle > Math.PI ? 1 : 0;
		return `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`;
	}

	const bandArcs = $derived((() => {
		let prevThreshold = min;
		return bands.map((band) => {
			const from = angleForValue(prevThreshold);
			const to = angleForValue(Math.min(band.threshold, max));
			prevThreshold = band.threshold;
			return { path: arcPath(from, to, r), color: band.color };
		});
	})());

	const needleAngle = $derived(angleForValue(value));
	const needleX = $derived(cx + (r - strokeW / 2) * Math.cos(needleAngle));
	const needleY = $derived(cy + (r - strokeW / 2) * Math.sin(needleAngle));

	const valueColor = $derived((() => {
		for (const band of bands) {
			if (value <= band.threshold) return band.color;
		}
		return bands[bands.length - 1]?.color ?? '#6b7280';
	})());
</script>

<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
	{#if title}
		<p class="text-sm font-medium text-gray-700 mb-2">{title}</p>
	{/if}
	<svg viewBox="0 0 {size} {size / 2 + 30}" class="mx-auto" style="width: {size}px; height: {size / 2 + 30}px" role="img" aria-label="{title}: {value}">
		<!-- Band arcs -->
		{#each bandArcs as band}
			<path d={band.path} fill="none" stroke={band.color} stroke-width={strokeW} stroke-linecap="butt" opacity="0.25" />
		{/each}

		<!-- Value arc (filled portion) -->
		<path
			d={arcPath(startAngle, needleAngle, r)}
			fill="none"
			stroke={valueColor}
			stroke-width={strokeW}
			stroke-linecap="round"
		/>

		<!-- Needle dot -->
		<circle cx={needleX} cy={needleY} r="5" fill={valueColor} stroke="white" stroke-width="2" />

		<!-- Center value -->
		<text x={cx} y={cy - 4} text-anchor="middle" font-size="26" font-weight="700" fill={valueColor}>
			{Math.round(value)}
		</text>
		{#if label}
			<text x={cx} y={cy + 14} text-anchor="middle" font-size="11" fill="#9ca3af">
				{label}
			</text>
		{/if}

		<!-- Min/Max labels -->
		<text x={cx - r} y={cy + 14} text-anchor="middle" font-size="9" fill="#d1d5db">{min}</text>
		<text x={cx + r} y={cy + 14} text-anchor="middle" font-size="9" fill="#d1d5db">{max}</text>
	</svg>
</div>
