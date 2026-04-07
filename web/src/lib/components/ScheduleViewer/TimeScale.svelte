<script lang="ts">
	import { generateTimeTicks } from './utils';

	interface Props {
		startDate: string;
		endDate: string;
		zoomLevel: 'day' | 'week' | 'month';
		width: number;
		padLeft: number;
		dataDate?: string;
	}

	let {
		startDate,
		endDate,
		zoomLevel,
		width,
		padLeft,
		dataDate = '',
	}: Props = $props();

	const chartWidth = $derived(width - padLeft);
	const ticks = $derived(generateTimeTicks(startDate, endDate, zoomLevel));

	const dateDateX = $derived(() => {
		if (!dataDate || !startDate || !endDate) return -1;
		const start = new Date(startDate + 'T00:00:00').getTime();
		const end = new Date(endDate + 'T00:00:00').getTime();
		const dd = new Date(dataDate + 'T00:00:00').getTime();
		if (dd < start || dd > end) return -1;
		return padLeft + ((dd - start) / (end - start)) * chartWidth;
	});
</script>

<g class="time-scale">
	<!-- Background -->
	<rect x={padLeft} y="0" width={chartWidth} height="28" fill="#f8fafc" class="dark:fill-gray-800" />

	<!-- Tick lines and labels -->
	{#each ticks as tick}
		{@const x = padLeft + tick.x * chartWidth}
		<line x1={x} y1="28" x2={x} y2="32" stroke="#d1d5db" stroke-width="1" />
		<text {x} y="18" text-anchor="middle" class="text-[8px] fill-gray-500 dark:fill-gray-400 select-none">
			{tick.label}
		</text>
	{/each}

	<!-- Data date marker -->
	{#if dateDateX() >= 0}
		<line x1={dateDateX()} y1="0" x2={dateDateX()} y2="9999" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4 3" opacity="0.7" />
		<text x={dateDateX()} y="10" text-anchor="middle" class="text-[7px] fill-amber-600 font-bold select-none">DD</text>
	{/if}

	<!-- Bottom border -->
	<line x1={padLeft} y1="28" x2={width} y2="28" stroke="#e5e7eb" stroke-width="1" />
</g>
