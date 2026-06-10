<script lang="ts">
	import type { ActivityView } from './types';
	import { formatDateShort } from './utils';
	import { t, locale, dateLocale } from '$lib/i18n';

	interface Props {
		activity: ActivityView;
		x: number;
		y: number;
	}

	let { activity, x, y }: Props = $props();

	const TOOLTIP_W = 320;
	const TOOLTIP_H_EST = 260;

	// BCP-47 tag for date VALUE localization (#176) — labels come from $t.
	const dl = $derived(dateLocale($locale));

	// Viewport edge detection — flip position if near edges
	const pos = $derived.by(() => {
		const vw = typeof window !== 'undefined' ? window.innerWidth : 1200;
		const vh = typeof window !== 'undefined' ? window.innerHeight : 800;

		let left = x + 16;
		let top = y - 20;

		if (left + TOOLTIP_W > vw - 12) left = x - TOOLTIP_W - 16;
		if (top + TOOLTIP_H_EST > vh - 12) top = vh - TOOLTIP_H_EST - 12;
		if (top < 12) top = 12;
		if (left < 12) left = 12;

		return { left, top };
	});

	function statusLabel(s: string): string {
		if (s === 'complete') return $t('schedule.status_complete');
		if (s === 'active') return $t('schedule.status_active');
		return $t('schedule.status_not_started');
	}

	function statusClass(s: string): string {
		if (s === 'complete') return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300';
		if (s === 'active') return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300';
		return 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300';
	}
</script>

<div
	class="fixed z-50 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl pointer-events-none"
	style="left: {pos.left}px; top: {pos.top}px; width: {TOOLTIP_W}px;"
>
	<!-- Header -->
	<div class="px-3 py-2 border-b border-gray-100 dark:border-gray-800">
		<div class="flex items-center gap-2">
			<span class="text-[10px] font-mono text-gray-400">{activity.task_code}</span>
			{#if activity.is_critical}
				<span class="px-1 py-0.5 text-[8px] font-bold bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300 rounded">{$t('schedule.viewer.critical_badge')}</span>
			{/if}
			<span class="px-1.5 py-0.5 text-[8px] font-medium rounded {statusClass(activity.status)}">{statusLabel(activity.status)}</span>
		</div>
		<p class="text-[11px] font-semibold text-gray-900 dark:text-gray-100 mt-0.5 leading-tight">{activity.task_name}</p>
		{#if activity.wbs_path}
			<p class="text-[8px] text-gray-400 mt-0.5 truncate">{activity.wbs_path}</p>
		{/if}
	</div>

	<!-- Dates -->
	<div class="px-3 py-1.5 border-b border-gray-100 dark:border-gray-800">
		<div class="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[10px]">
			<div class="flex justify-between">
				<span class="text-gray-400">{$t('schedule.col_es')}</span>
				<span class="font-mono text-gray-700 dark:text-gray-300">{formatDateShort(activity.early_start, dl)}</span>
			</div>
			<div class="flex justify-between">
				<span class="text-gray-400">{$t('schedule.col_ef')}</span>
				<span class="font-mono text-gray-700 dark:text-gray-300">{formatDateShort(activity.early_finish, dl)}</span>
			</div>
			{#if activity.late_start && activity.late_finish}
				<div class="flex justify-between">
					<span class="text-gray-400">{$t('schedule.col_ls')}</span>
					<span class="font-mono text-gray-700 dark:text-gray-300">{formatDateShort(activity.late_start, dl)}</span>
				</div>
				<div class="flex justify-between">
					<span class="text-gray-400">{$t('schedule.col_lf')}</span>
					<span class="font-mono text-gray-700 dark:text-gray-300">{formatDateShort(activity.late_finish, dl)}</span>
				</div>
			{/if}
			{#if activity.actual_start}
				<div class="flex justify-between">
					<span class="text-gray-400">{$t('schedule.col_as')}</span>
					<span class="font-mono text-green-600">{formatDateShort(activity.actual_start, dl)}</span>
				</div>
			{/if}
			{#if activity.actual_finish}
				<div class="flex justify-between">
					<span class="text-gray-400">{$t('schedule.col_af')}</span>
					<span class="font-mono text-green-600">{formatDateShort(activity.actual_finish, dl)}</span>
				</div>
			{/if}
		</div>
	</div>

	<!-- Metrics -->
	<div class="px-3 py-1.5 border-b border-gray-100 dark:border-gray-800">
		<div class="grid grid-cols-3 gap-2 text-center">
			<div>
				<p class="text-[8px] text-gray-400 uppercase">{$t('schedule.detail_duration')}</p>
				<p class="text-[11px] font-bold text-gray-900 dark:text-gray-100">{activity.duration_days}d</p>
			</div>
			<div>
				<p class="text-[8px] text-gray-400 uppercase">{$t('schedule.detail_remaining')}</p>
				<p class="text-[11px] font-bold text-gray-900 dark:text-gray-100">{activity.remaining_days}d</p>
			</div>
			<div>
				<p class="text-[8px] text-gray-400 uppercase">{$t('schedule.detail_progress')}</p>
				<p class="text-[11px] font-bold {activity.progress_pct >= 100 ? 'text-green-600' : activity.progress_pct > 0 ? 'text-blue-600' : 'text-gray-400'}">{activity.progress_pct}%</p>
			</div>
		</div>
		<div class="grid grid-cols-2 gap-2 text-center mt-1">
			<div>
				<p class="text-[8px] text-gray-400 uppercase">{$t('schedule.detail_total_float')}</p>
				<p class="text-[11px] font-bold {activity.total_float_days < 0 ? 'text-red-600' : activity.total_float_days === 0 ? 'text-amber-600' : 'text-green-600'}">{activity.total_float_days}d</p>
			</div>
			<div>
				<p class="text-[8px] text-gray-400 uppercase">{$t('schedule.detail_free_float')}</p>
				<p class="text-[11px] font-bold text-gray-700 dark:text-gray-300">{activity.free_float_days}d</p>
			</div>
		</div>
	</div>

	<!-- Baseline & Variance (conditional) -->
	{#if activity.baseline_start || activity.baseline_finish}
		<div class="px-3 py-1.5 border-b border-gray-100 dark:border-gray-800">
			<div class="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[10px]">
				{#if activity.baseline_start}
					<div class="flex justify-between">
						<span class="text-gray-400">{$t('schedule.col_bs')}</span>
						<span class="font-mono text-gray-500">{formatDateShort(activity.baseline_start, dl)}</span>
					</div>
				{/if}
				{#if activity.baseline_finish}
					<div class="flex justify-between">
						<span class="text-gray-400">{$t('schedule.col_bf')}</span>
						<span class="font-mono text-gray-500">{formatDateShort(activity.baseline_finish, dl)}</span>
					</div>
				{/if}
				{#if activity.start_variance_days != null}
					<div class="flex justify-between">
						<span class="text-gray-400">{$t('schedule.col_sv')}</span>
						<span class="font-mono font-bold {activity.start_variance_days > 0 ? 'text-red-600' : activity.start_variance_days < 0 ? 'text-green-600' : 'text-gray-500'}">{activity.start_variance_days > 0 ? '+' : ''}{activity.start_variance_days}d</span>
					</div>
				{/if}
				{#if activity.finish_variance_days != null}
					<div class="flex justify-between">
						<span class="text-gray-400">{$t('schedule.col_fv')}</span>
						<span class="font-mono font-bold {activity.finish_variance_days > 0 ? 'text-red-600' : activity.finish_variance_days < 0 ? 'text-green-600' : 'text-gray-500'}">{activity.finish_variance_days > 0 ? '+' : ''}{activity.finish_variance_days}d</span>
					</div>
				{/if}
			</div>
		</div>
	{/if}

	<!-- Flags -->
	{#if activity.constraint_type && activity.constraint_type !== 'CS_MEO'}
		<div class="px-3 py-1 text-[9px]">
			<span class="text-purple-600 font-medium">{$t('schedule.detail_constraint')}: {activity.constraint_type}</span>
			{#if activity.constraint_date}
				<span class="text-gray-400 ml-1">{formatDateShort(activity.constraint_date, dl)}</span>
			{/if}
		</div>
	{/if}

	<!-- Alerts -->
	{#if activity.alerts.length > 0}
		<div class="px-3 py-1.5 flex flex-wrap gap-1">
			{#each activity.alerts as alert}
				<span class="px-1.5 py-0.5 bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-300 rounded text-[8px] font-bold">{alert.replace(/_/g, ' ')}</span>
			{/each}
		</div>
	{/if}
</div>
