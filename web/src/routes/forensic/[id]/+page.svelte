<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { getTimeline, getDelayTrend } from '$lib/api';
	import type { TimelineDetailSchema, DelayTrendResponse, WindowSchema } from '$lib/types';

	let timeline: TimelineDetailSchema | null = $state(null);
	let trend: DelayTrendResponse | null = $state(null);
	let loading = $state(true);
	let error = $state('');
	let expandedWindow: number | null = $state(null);

	const timelineId = $derived($page.params.id);

	onMount(async () => {
		try {
			const [tl, tr] = await Promise.all([
				getTimeline(timelineId),
				getDelayTrend(timelineId)
			]);
			timeline = tl;
			trend = tr;
		} catch {
			error = 'Failed to load timeline';
		} finally {
			loading = false;
		}
	});

	function formatDate(d: string | null): string {
		if (!d) return '-';
		return new Date(d).toLocaleDateString();
	}

	function toggleWindow(num: number) {
		expandedWindow = expandedWindow === num ? null : num;
	}

	// Waterfall chart dimensions
	const chartWidth = 700;
	const chartHeight = 200;
	const barPadding = 4;

	function getWaterfallBars(
		windows: WindowSchema[]
	): { x: number; y: number; width: number; height: number; color: string; label: string; days: number }[] {
		if (!windows.length) return [];
		const maxAbs = Math.max(...windows.map((w) => Math.abs(w.delay_days)), 1);
		const barWidth = Math.max(
			20,
			(chartWidth - barPadding * (windows.length + 1)) / windows.length
		);
		const midY = chartHeight / 2;
		const scale = (chartHeight / 2 - 20) / maxAbs;

		return windows.map((w, i) => {
			const h = Math.abs(w.delay_days) * scale;
			const isDelay = w.delay_days > 0;
			return {
				x: barPadding + i * (barWidth + barPadding),
				y: isDelay ? midY - h : midY,
				width: barWidth,
				height: Math.max(h, 2),
				color: isDelay ? '#ef4444' : w.delay_days < 0 ? '#22c55e' : '#9ca3af',
				label: w.window_id,
				days: w.delay_days
			};
		});
	}
</script>

<svelte:head>
	<title>Timeline {timelineId} - MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-7xl mx-auto">
	<div class="mb-6">
		<a href="/forensic" class="text-sm text-blue-600 hover:underline">Back to Forensic Analysis</a>
	</div>

	{#if loading}
		<div class="flex items-center gap-2 text-gray-500">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24"
				><circle
					class="opacity-25"
					cx="12"
					cy="12"
					r="10"
					stroke="currentColor"
					stroke-width="4"
					fill="none"
				/><path
					class="opacity-75"
					fill="currentColor"
					d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
				/></svg
			>
			Loading forensic timeline...
		</div>
	{:else if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">{error}</div>
	{:else if timeline}
		<h1 class="text-2xl font-bold text-gray-900 mb-1">
			{timeline.project_name || 'Forensic Timeline'}
		</h1>
		<p class="text-sm text-gray-500 mb-6">{timeline.timeline_id}</p>

		<!-- Summary Cards -->
		<div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 uppercase">Total Delay</p>
				<p
					class="text-2xl font-bold {timeline.total_delay_days > 0
						? 'text-red-600'
						: timeline.total_delay_days < 0
							? 'text-green-600'
							: 'text-gray-500'}"
				>
					{timeline.total_delay_days > 0 ? '+' : ''}{timeline.total_delay_days.toFixed(0)}d
				</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 uppercase">Windows</p>
				<p class="text-2xl font-bold text-blue-600">{timeline.windows.length}</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 uppercase">Contract End</p>
				<p class="text-lg font-bold text-gray-700">{formatDate(timeline.contract_completion)}</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-lg p-4 text-center">
				<p class="text-xs text-gray-500 uppercase">Current End</p>
				<p class="text-lg font-bold text-gray-700">{formatDate(timeline.current_completion)}</p>
			</div>
		</div>

		<!-- Delay Waterfall Chart -->
		{#if timeline.windows.length > 0}
			{@const bars = getWaterfallBars(timeline.windows)}
			<div class="bg-white border border-gray-200 rounded-lg p-6 mb-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">Delay Waterfall</h2>
				<div class="overflow-x-auto">
					<svg
						viewBox="0 0 {chartWidth} {chartHeight + 40}"
						class="w-full max-w-3xl"
						preserveAspectRatio="xMidYMid meet"
					>
						<!-- Zero line -->
						<line
							x1="0"
							y1={chartHeight / 2}
							x2={chartWidth}
							y2={chartHeight / 2}
							stroke="#d1d5db"
							stroke-width="1"
							stroke-dasharray="4 4"
						/>
						<!-- Labels -->
						<text x="2" y="14" class="text-xs" fill="#9ca3af" font-size="11"
							>Delay</text
						>
						<text
							x="2"
							y={chartHeight - 4}
							class="text-xs"
							fill="#9ca3af"
							font-size="11">Acceleration</text
						>
						<!-- Bars -->
						{#each bars as bar}
							<rect
								x={bar.x}
								y={bar.y}
								width={bar.width}
								height={bar.height}
								fill={bar.color}
								rx="2"
								opacity="0.85"
							/>
							<!-- Day label -->
							<text
								x={bar.x + bar.width / 2}
								y={bar.days >= 0 ? bar.y - 4 : bar.y + bar.height + 12}
								text-anchor="middle"
								font-size="10"
								fill={bar.color}
							>
								{bar.days > 0 ? '+' : ''}{bar.days.toFixed(0)}d
							</text>
							<!-- Window label -->
							<text
								x={bar.x + bar.width / 2}
								y={chartHeight + 24}
								text-anchor="middle"
								font-size="10"
								fill="#6b7280"
							>
								{bar.label}
							</text>
						{/each}
					</svg>
				</div>
			</div>
		{/if}

		<!-- Window Table -->
		<div class="bg-white border border-gray-200 rounded-lg">
			<div class="px-6 py-4 border-b border-gray-200">
				<h2 class="text-lg font-semibold text-gray-900">Analysis Windows</h2>
			</div>
			<div class="overflow-x-auto">
				<table class="min-w-full divide-y divide-gray-200 text-sm">
					<thead class="bg-gray-50">
						<tr>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
								>Window</th
							>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
								>Period</th
							>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
								>Completion Start</th
							>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
								>Completion End</th
							>
							<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase"
								>Delay</th
							>
							<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase"
								>Cumulative</th
							>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase"
								>Driving Activity</th
							>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each timeline.windows as w}
							<tr
								class="hover:bg-gray-50 cursor-pointer"
								onclick={() => toggleWindow(w.window_number)}
							>
								<td class="px-4 py-3 font-medium text-gray-900">{w.window_id}</td>
								<td class="px-4 py-3 text-gray-700"
									>{formatDate(w.start_date)} - {formatDate(w.end_date)}</td
								>
								<td class="px-4 py-3 text-gray-500"
									>{formatDate(w.completion_date_start)}</td
								>
								<td class="px-4 py-3 text-gray-500"
									>{formatDate(w.completion_date_end)}</td
								>
								<td
									class="px-4 py-3 text-right font-medium {w.delay_days > 0
										? 'text-red-600'
										: w.delay_days < 0
											? 'text-green-600'
											: 'text-gray-500'}"
								>
									{w.delay_days > 0 ? '+' : ''}{w.delay_days.toFixed(0)}d
								</td>
								<td
									class="px-4 py-3 text-right font-medium {w.cumulative_delay > 0
										? 'text-red-600'
										: w.cumulative_delay < 0
											? 'text-green-600'
											: 'text-gray-500'}"
								>
									{w.cumulative_delay > 0 ? '+' : ''}{w.cumulative_delay.toFixed(0)}d
								</td>
								<td class="px-4 py-3 font-mono text-gray-700">{w.driving_activity}</td>
							</tr>
							{#if expandedWindow === w.window_number}
								<tr>
									<td colspan="7" class="px-6 py-4 bg-gray-50">
										<div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
											<div>
												<h4 class="font-medium text-gray-900 mb-2">
													Critical Path Changes
												</h4>
												{#if w.cp_activities_joined.length > 0}
													<p class="text-green-700">
														Joined CP: {w.cp_activities_joined.join(', ')}
													</p>
												{/if}
												{#if w.cp_activities_left.length > 0}
													<p class="text-red-700">
														Left CP: {w.cp_activities_left.join(', ')}
													</p>
												{/if}
												{#if w.cp_activities_joined.length === 0 && w.cp_activities_left.length === 0}
													<p class="text-gray-500">
														No critical path changes
													</p>
												{/if}
											</div>
											<div>
												<h4 class="font-medium text-gray-900 mb-2">
													Comparison Summary
												</h4>
												{#if w.comparison_summary}
													<div class="space-y-1 text-gray-600">
														{#if w.comparison_summary.activities_added !== undefined}
															<p>
																Added: {w.comparison_summary.activities_added}
																| Deleted: {w.comparison_summary.activities_deleted}
																| Modified: {w.comparison_summary.activities_modified}
															</p>
														{/if}
														{#if w.comparison_summary.changed_percentage !== undefined}
															<p>
																Changed: {Number(
																	w.comparison_summary.changed_percentage
																).toFixed(1)}%
															</p>
														{/if}
														{#if w.comparison_summary.manipulation_flags !== undefined && Number(w.comparison_summary.manipulation_flags) > 0}
															<p class="text-red-600 font-medium">
																Manipulation flags: {w.comparison_summary
																	.manipulation_flags}
															</p>
														{/if}
													</div>
												{:else}
													<p class="text-gray-500">No comparison data</p>
												{/if}
											</div>
										</div>
									</td>
								</tr>
							{/if}
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
