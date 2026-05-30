<script lang="ts">
	interface Props {
		value: number;
		min?: number;
		max?: number;
		title?: string;
		label?: string;
		size?: number;
		bands?: { threshold: number; color: string }[];
		/**
		 * Formats the centre readout. Defaults to integer rounding so the 11
		 * 0–100 score callers stay byte-identical; EVM SPI/CPI callers pass
		 * `(v) => v.toFixed(2)` so 1.05 renders as "1.05", not "1".
		 */
		valueFormat?: (v: number) => string;
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
		valueFormat = (v: number) => Math.round(v).toString(),
	}: Props = $props();

	// Guard non-finite input: a NaN / undefined value must NOT leak into SVG
	// coordinates (it stringifies to "NaN" inside path/cx/cy attributes) nor
	// fall through the band loop to the last band (green = "healthy" — a
	// misleading verdict for missing data). null ⇒ render the gauge empty:
	// "--" centre, no needle, neutral arc.
	const safeValue = $derived<number | null>(Number.isFinite(value) ? value : null);
	const NEUTRAL = '#9ca3af';

	const cx = $derived(size / 2);
	const cy = $derived(size / 2 + 10);
	const r = $derived(size / 2 - 16);
	const strokeW = 16;

	// Arc from -180deg to 0deg (semicircle, left to right)
	const startAngle = -Math.PI;
	const endAngle = 0;

	function angleForValue(v: number): number {
		const span = max - min || 1; // guard degenerate max === min (÷0 → NaN)
		const pct = Math.max(0, Math.min(1, (v - min) / span));
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

	// Needle / value-arc geometry — null when the value is non-finite so the
	// markup can skip rendering entirely rather than emit NaN coordinates.
	const needleAngle = $derived<number | null>(safeValue === null ? null : angleForValue(safeValue));
	const needleX = $derived<number | null>(needleAngle === null ? null : cx + (r - strokeW / 2) * Math.cos(needleAngle));
	const needleY = $derived<number | null>(needleAngle === null ? null : cy + (r - strokeW / 2) * Math.sin(needleAngle));

	const valueColor = $derived((() => {
		if (safeValue === null) return NEUTRAL;
		for (const band of bands) {
			if (safeValue <= band.threshold) return band.color;
		}
		return bands[bands.length - 1]?.color ?? '#6b7280';
	})());

	const displayValue = $derived(safeValue === null ? '--' : valueFormat(safeValue));
</script>

<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
	{#if title}
		<p class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{title}</p>
	{/if}
	<svg viewBox="0 0 {size} {size / 2 + 30}" class="mx-auto" style="width: {size}px; height: {size / 2 + 30}px" role="img" aria-label={title ? `${title}: ${displayValue}` : displayValue}>
		<!-- Band arcs -->
		{#each bandArcs as band}
			<path d={band.path} fill="none" stroke={band.color} stroke-width={strokeW} stroke-linecap="butt" opacity="0.25" />
		{/each}

		<!-- Value arc (filled portion) — skipped for non-finite input -->
		{#if needleAngle !== null}
			<path
				d={arcPath(startAngle, needleAngle, r)}
				fill="none"
				stroke={valueColor}
				stroke-width={strokeW}
				stroke-linecap="round"
			/>
		{/if}

		<!-- Needle dot — skipped for non-finite input -->
		{#if needleX !== null && needleY !== null}
			<circle cx={needleX} cy={needleY} r="5" fill={valueColor} stroke="white" stroke-width="2" />
		{/if}

		<!-- Center value -->
		<text x={cx} y={cy - 4} text-anchor="middle" font-size="26" font-weight="700" fill={valueColor}>
			{displayValue}
		</text>
		{#if label}
			<text x={cx} y={cy + 14} text-anchor="middle" font-size="11" fill="#9ca3af" class="dark:fill-gray-500">
				{label}
			</text>
		{/if}

		<!-- Min/Max labels -->
		<text x={cx - r} y={cy + 14} text-anchor="middle" font-size="9" fill="#d1d5db" class="dark:fill-gray-600">{min}</text>
		<text x={cx + r} y={cy + 14} text-anchor="middle" font-size="9" fill="#d1d5db" class="dark:fill-gray-600">{max}</text>
	</svg>
</div>
