<script lang="ts">
	import { generateTimeTicks } from './utils';
	import { t, locale, dateLocale } from '$lib/i18n';

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

	// BCP-47 tag for date VALUE localization (#176) — labels come from $t.
	const dl = $derived(dateLocale($locale));

	const chartWidth = $derived(width - padLeft);
	const axis = $derived(generateTimeTicks(startDate, endDate, zoomLevel, undefined, dl));

	const todayX = $derived(() => {
		if (!startDate || !endDate) return -1;
		const start = new Date(startDate + 'T00:00:00').getTime();
		const end = new Date(endDate + 'T00:00:00').getTime();
		const now = new Date().setHours(0, 0, 0, 0);
		if (now < start || now > end) return -1;
		return padLeft + ((now - start) / (end - start)) * chartWidth;
	});

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
	<!-- Background (two-tier header: coarse band over fine band) -->
	<rect x={padLeft} y="0" width={chartWidth} height="40" fill="#f8fafc" class="dark:fill-gray-800" />

	<!-- Major tier: coarse context bands (year over month, or month over week/day) -->
	{#each axis.major as m}
		{@const mx = padLeft + m.x * chartWidth}
		{@const mxEnd = padLeft + m.xEnd * chartWidth}
		<line x1={mx} y1="0" x2={mx} y2="40" stroke="#e5e7eb" stroke-width="1" class="dark:stroke-gray-700" />
		<text x={(mx + mxEnd) / 2} y="13" text-anchor="middle" class="text-[9px] font-semibold fill-gray-600 dark:fill-gray-300 select-none">
			{m.label}
		</text>
	{/each}

	<!-- Divider between the two tiers -->
	<line x1={padLeft} y1="20" x2={width} y2="20" stroke="#e5e7eb" stroke-width="1" class="dark:stroke-gray-700" />

	<!-- Minor tier: fine ticks + labels -->
	{#each axis.minor as tick}
		{@const x = padLeft + tick.x * chartWidth}
		<line x1={x} y1="34" x2={x} y2="40" stroke="#d1d5db" stroke-width="1" class="dark:stroke-gray-600" />
		<text {x} y="31" text-anchor="middle" class="text-[8px] fill-gray-500 dark:fill-gray-400 select-none">
			{tick.label}
		</text>
	{/each}

	<!-- Data date marker -->
	{#if dateDateX() >= 0}
		<line x1={dateDateX()} y1="0" x2={dateDateX()} y2="9999" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4 3" opacity="0.7" />
		<text x={dateDateX()} y="10" text-anchor="middle" class="text-[7px] fill-amber-600 font-bold select-none">DD</text>
	{/if}

	<!-- Today line -->
	{#if todayX() >= 0}
		<line x1={todayX()} y1="0" x2={todayX()} y2="9999" stroke="#10b981" stroke-width="1.5" opacity="0.6" />
		<text x={todayX()} y="10" text-anchor="middle" class="text-[7px] fill-green-600 font-bold select-none">{$t('schedule.viewer.today')}</text>
	{/if}

	<!-- Bottom border -->
	<line x1={padLeft} y1="40" x2={width} y2="40" stroke="#e5e7eb" stroke-width="1" class="dark:stroke-gray-700" />
</g>
