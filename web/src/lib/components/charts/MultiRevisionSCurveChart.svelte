<script lang="ts">
	import type { RevisionCurveSchema, ChangePointMarkerSchema } from '$lib/types';
	import {
		getCurveColor,
		getCurveStrokeWidth,
		getLegendChipHeight,
	} from './MultiRevisionSCurveChart.palette';

	interface Props {
		curves: RevisionCurveSchema[];
		changePoints?: ChangePointMarkerSchema[];
		height?: number;
		title?: string;
		ariaLabel?: string;
		emptyLabel?: string;
		executedLabel?: string;
		changePointLabel?: string;
		legendCollapsedSummary?: (n: number) => string;
		directionLabels?: { slip: string; improvement: string; flat: string };
	}

	let {
		curves,
		changePoints = [],
		height = 360,
		title = '',
		ariaLabel = 'Multi-revision S-curve overlay',
		emptyLabel = 'No revisions to display.',
		executedLabel = 'Executed',
		changePointLabel = 'Change point',
		legendCollapsedSummary = (n: number) => `${n} revisions — show legend`,
		directionLabels = { slip: 'Slip', improvement: 'Improvement', flat: 'Flat' },
	}: Props = $props();

	// Mobile legend-collapse state (issue #97 part 2 / DA P2 #12 from PR #95).
	// On <640px viewports with N>8 revisions, the legend wraps to 4-5 rows
	// and pushes methodology disclosure off-screen on first paint. Wrap in
	// <details> always-in-DOM (LifecyclePhaseCard.svelte pattern); summary
	// shown only when shouldCollapse=true (sm:hidden via conditional render).
	//
	// Initial-mobile-collapse vs resize-to-mobile-preserve (DA exit-council
	// P0 #2 fix on PR #109): legendOpen defaults to true so the legend is
	// visible by default on tablet/desktop. On the FIRST detection of
	// shouldCollapse=true (initial mobile load with N>8), the effect
	// collapses once. Subsequent resizes (e.g., tablet rotate landscape →
	// portrait) do NOT re-collapse — `initialCollapseDone` ensures the
	// auto-collapse runs at most once per chart instance, preserving the
	// user's manual toggle state across viewport changes.
	let isMobile = $state(false);
	let legendOpen = $state(true);
	let initialCollapseDone = $state(false);

	$effect(() => {
		if (typeof window === 'undefined') return;
		const mq = window.matchMedia('(max-width: 640px)');
		isMobile = mq.matches;
		// Initial-paint check: collapse once if mobile + N>8 at first mount.
		// Subsequent resize events do NOT trigger this branch.
		if (!initialCollapseDone) {
			initialCollapseDone = true;
			if (mq.matches && curves.length > 8) {
				legendOpen = false;
			}
		}
		const handler = (e: MediaQueryListEvent) => {
			isMobile = e.matches;
			// Intentionally do NOT re-collapse on resize: preserve user's
			// manual toggle state. P0 #2 fix.
		};
		mq.addEventListener('change', handler);
		return () => mq.removeEventListener('change', handler);
	});

	const shouldCollapse = $derived(isMobile && curves.length > 8);
	// <details open> attribute: when shouldCollapse=false, always open
	// (renders legend chips inline). When shouldCollapse=true, controlled
	// by user click on <summary>.
	const detailsOpen = $derived(!shouldCollapse || legendOpen);

	const WIDTH = 800;
	const PAD_TOP = 28;
	const PAD_BOTTOM = 56;
	const PAD_LEFT = 56;
	const PAD_RIGHT = 56;

	const chartW = WIDTH - PAD_LEFT - PAD_RIGHT;
	const chartH = $derived(height - PAD_TOP - PAD_BOTTOM);

	// Calendar-aligned X-axis per AACE RP 29R-03 §"Window analysis":
	// each revision's curve is shifted by (data_date − earliest_data_date)
	// so revisions are calendar-aligned, not stacked on a shared day-0.
	// Falls back to pooled day_offset (with disclosure note) if any curve
	// is missing data_date (anonymous uploads, etc.) — DA exit-council
	// finding P1#4.
	const calendarShifts = $derived.by((): number[] | null => {
		if (curves.length === 0) return null;
		const ds = curves.map((c) => c.data_date);
		if (ds.some((d) => d == null || d === '')) return null;
		const ms = ds.map((d) => Date.parse(d!));
		if (ms.some((m) => Number.isNaN(m))) return null;
		const earliest = Math.min(...ms);
		return ms.map((m) => Math.round((m - earliest) / 86_400_000));
	});

	const isCalendarAligned = $derived(calendarShifts !== null);

	function curveShift(idx: number): number {
		return calendarShifts ? calendarShifts[idx] : 0;
	}

	const xMax = $derived.by(() => {
		let max = 0;
		for (let i = 0; i < curves.length; i++) {
			const shift = curveShift(i);
			for (const p of curves[i].points) {
				const x = p.day_offset + shift;
				if (x > max) max = x;
			}
		}
		return max || 1;
	});

	function xPos(absDay: number): number {
		return (absDay / xMax) * chartW;
	}

	function yPos(pct: number): number {
		// pct is fraction 0..1; clamp.
		const v = Math.max(0, Math.min(1, pct));
		return chartH - v * chartH;
	}

	function buildPlannedPath(c: RevisionCurveSchema, idx: number): string {
		if (c.points.length === 0) return '';
		const shift = curveShift(idx);
		return c.points
			.map(
				(p, i) =>
					`${i === 0 ? 'M' : 'L'}${xPos(p.day_offset + shift).toFixed(1)},${yPos(p.planned_cumulative_pct).toFixed(1)}`
			)
			.join(' ');
	}

	function buildActualPath(c: RevisionCurveSchema, idx: number): string {
		if (!c.is_executed) return '';
		// Skip points where actual is null (older revisions, or future-of-data-date).
		const shift = curveShift(idx);
		const segments: string[] = [];
		let started = false;
		for (const p of c.points) {
			if (p.actual_cumulative_pct == null) {
				started = false;
				continue;
			}
			const cmd = started ? 'L' : 'M';
			segments.push(
				`${cmd}${xPos(p.day_offset + shift).toFixed(1)},${yPos(p.actual_cumulative_pct).toFixed(1)}`
			);
			started = true;
		}
		return segments.join(' ');
	}

	// Palette + per-revision encoding (color + stroke-width + legend-chip
	// height) are sourced from `./MultiRevisionSCurveChart.palette` so the
	// 11-swatch hex list, the WCAG measurement methodology, and the
	// stroke-width-as-age rationale all live behind one auditable import.
	// Issue #108: prior HSL hue-cycle palette was replaced because (a) it
	// failed WCAG 1.4.11 around hue~80° and (b) any opacity weighting on
	// the old curves made composited contrast fall below 3:1 for every
	// swatch in the feasible Y band — see palette file header.

	// Y-axis ticks (0%, 25%, 50%, 75%, 100%).
	const yTicks = $derived.by(() => {
		const ticks: { value: number; y: number; label: string }[] = [];
		for (let i = 0; i <= 4; i++) {
			const v = i * 0.25;
			ticks.push({ value: v, y: yPos(v), label: `${Math.round(v * 100)}%` });
		}
		return ticks;
	});

	// X-axis ticks (~6 labels).
	const xTicks = $derived.by(() => {
		if (xMax <= 0) return [];
		const targetCount = 6;
		const step = Math.max(1, Math.ceil(xMax / targetCount));
		const ticks: { x: number; label: string }[] = [];
		for (let v = 0; v <= xMax; v += step) {
			ticks.push({ x: xPos(v), label: `D+${v}` });
		}
		return ticks;
	});

	// Direction → visual mapping. Color + dasharray both vary so the
	// encoding is not color-only (WCAG 1.4.1). The dotted flat dasharray
	// also disambiguates flat markers from the single-revision gray
	// planned-curve fallback (`SINGLE_CURVE_COLOR` in the palette module).
	function directionVisual(direction: string): {
		color: string;
		darkStrokeClass: string;
		darkFillClass: string;
		dashArray: string;
	} {
		switch (direction) {
			case 'slip':
				return {
					color: '#b45309',
					darkStrokeClass: 'dark:stroke-amber-400',
					darkFillClass: 'dark:fill-amber-400',
					dashArray: '4 3',
				};
			case 'improvement':
				return {
					color: '#047857',
					darkStrokeClass: 'dark:stroke-emerald-400',
					darkFillClass: 'dark:fill-emerald-400',
					dashArray: '2 2 6 2',
				};
			case 'flat':
				return {
					color: '#4b5563',
					darkStrokeClass: 'dark:stroke-gray-400',
					darkFillClass: 'dark:fill-gray-400',
					dashArray: '1 3',
				};
			default:
				// Unknown direction — likely a future backend value the frontend
				// hasn't been updated for. Render flat-styled but log so the
				// regression surfaces in Sentry breadcrumbs (auto-captured from
				// console.warn) rather than failing silent.
				// eslint-disable-next-line no-console
				console.warn(
					'[MultiRevisionSCurveChart] unknown change-point direction:',
					direction,
				);
				return {
					color: '#4b5563',
					darkStrokeClass: 'dark:stroke-gray-400',
					darkFillClass: 'dark:fill-gray-400',
					dashArray: '1 3',
				};
		}
	}

	function directionLabelOf(direction: string): string {
		if (direction === 'slip') return directionLabels.slip;
		if (direction === 'improvement') return directionLabels.improvement;
		return directionLabels.flat;
	}

	// Change-point markers — vertical lines positioned at the START
	// (data_date) of the curve at `revision_index`, NOT at its planned-finish
	// day. The CUSUM fires at the moment the new revision is detected to
	// have shifted regime — that moment is the revision's data_date, which
	// is day_offset=0 of that curve in calendar-aligned space. DA exit-
	// council finding P1#3.
	const changePointVisuals = $derived.by(() => {
		return changePoints
			.map((cp) => {
				const c = curves[cp.revision_index];
				if (!c) return null;
				const shift = curveShift(cp.revision_index);
				const visual = directionVisual(cp.direction);
				return {
					x: xPos(0 + shift),
					description: cp.description,
					direction: cp.direction,
					directionLabel: directionLabelOf(cp.direction),
					strokeColor: visual.color,
					darkStrokeClass: visual.darkStrokeClass,
					darkFillClass: visual.darkFillClass,
					dashArray: visual.dashArray,
					// 1-based fallback aligning with the endpoint-label and page
					// changePointLabel rendering. Issue #98 item 5 + frontend-
					// ux-reviewer entry-council BLOCKING #2 on PR #109: chart
					// was internally inconsistent (one site 0-based, another
					// 1-based); aligned to 1-based per least-surprise.
					revisionLabel:
						c.revision_number != null ? `R${c.revision_number}` : `#${cp.revision_index + 1}`,
				};
			})
			.filter((v): v is NonNullable<typeof v> => v !== null);
	});

	// Endpoint labels (R1..RN) at each curve's terminal point. Hidden when
	// N>8 to avoid pixel-collision pile-up at upper-right; legend chips
	// below carry the same identification. DA exit-council finding P2#11.
	//
	// `color` is the curve hex (used for the endpoint DOT, which is a
	// graphical object covered by WCAG 1.4.11 at 3:1 and verified at
	// palette-construction time). The endpoint TEXT label is decoupled
	// from this color in the template via a fixed `fill="#374151"` +
	// `class="dark:fill-gray-300"` pair so 1.4.3 (4.5:1) for normal text
	// is satisfied independently of the palette swatch's luminance — see
	// palette file header for the dual-bg infeasibility derivation that
	// forces the decoupling. Issue #108.
	const endpointLabels = $derived.by(() => {
		if (curves.length > 8) return [];
		return curves
			.map((c, i) => {
				if (c.points.length === 0) return null;
				const last = c.points[c.points.length - 1];
				const shift = curveShift(i);
				return {
					x: xPos(last.day_offset + shift),
					y: yPos(last.planned_cumulative_pct),
					label: c.revision_number != null ? `R${c.revision_number}` : `#${i + 1}`,
					color: getCurveColor(i, curves.length),
				};
			})
			.filter((v): v is NonNullable<typeof v> => v !== null);
	});

	// All-empty curves edge case: curves.length > 0 but every curve has
	// points=[] (defensive backend output, e.g., CPM failed for all
	// revisions). DA exit-council finding P2#7 — distinguish from
	// "no revisions" empty state.
	//
	// Issue #98 item 2 (DA P3 #14 from PR #95) + frontend-ux-reviewer entry-
	// council nice-to-have #11 + DA exit-council P2 #9 on PR #109: extend to
	// also cover the degenerate-X case where points are populated but all
	// day_offsets=0 (single-day project with multiple revisions all at d=0).
	// Renders explicit empty-state instead of "D+0..D+1" axis with no curves.
	//
	// **Reachability uncertainty acknowledged**: DA P2 #9 flagged that the
	// backend's ability to emit all-zero day_offset curves has not been
	// explicitly verified. Adding this defense without proof of need is
	// regret-bait per DA. Kept here as a one-line guard with this comment;
	// if backend guarantee says "extract_planned_curve always emits ≥2
	// distinct day_offsets when activities have non-zero CPM finishes", a
	// future cleanup PR should drop the second clause.
	const isAllEmpty = $derived(
		curves.length > 0 &&
			(curves.every((c) => c.points.length === 0) ||
				curves.every((c) => c.points.every((p) => p.day_offset === 0))),
	);

	// Multi-executed defensive z-order (issue #98 item 4 / DA P3 #16 from PR #95).
	// Backend invariant: only the most recent revision should have is_executed=true.
	// Defensive: find the LAST is_executed curve via findLast (ES2023). If the
	// invariant is violated, the chart renders only that last curve's actual
	// path; the page-level `clientWarnings` derivation surfaces a user-visible
	// note in trends.notes (frontend-ux-reviewer entry-council SHOULD-FIX #6
	// on PR #109: console.warn alone hides the bug).
	// findLastIndex (ES2023, target esnext, supported by all modern browsers)
	// per DA exit-council P1 #6 fix on PR #109: idiomatic 1-line replacement
	// for the manual reverse-loop earlier draft.
	const lastExecutedIndex = $derived(curves.findLastIndex((c) => c.is_executed));
</script>

<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
	{#if title}
		<div class="flex items-center justify-between mb-2">
			<p class="text-sm font-semibold text-gray-700 dark:text-gray-300">{title}</p>
			<span class="text-[9px] text-gray-400">AACE RP 29R-03</span>
		</div>
	{/if}

	{#if curves.length === 0 || isAllEmpty}
		<div
			class="flex items-center justify-center text-gray-400 dark:text-gray-500 text-sm"
			style="height: {height}px"
		>
			{emptyLabel}
		</div>
	{:else}
		<svg
			viewBox="0 0 {WIDTH} {height}"
			preserveAspectRatio="xMidYMid meet"
			class="w-full"
			style="height: {height}px"
			role="img"
			aria-label={ariaLabel}
		>
			<g transform="translate({PAD_LEFT}, {PAD_TOP})">
				<!-- Y-axis grid + labels -->
				{#each yTicks as tick}
					<line
						x1="0"
						y1={tick.y}
						x2={chartW}
						y2={tick.y}
						stroke="#e5e7eb"
						stroke-width="0.5"
						class="dark:stroke-gray-700"
					/>
					<text
						x="-8"
						y={tick.y + 3}
						text-anchor="end"
						font-size="9"
						fill="#9ca3af"
						class="dark:fill-gray-500"
					>
						{tick.label}
					</text>
				{/each}

				<!-- X-axis labels -->
				{#each xTicks as tick}
					<text
						x={tick.x}
						y={chartH + 16}
						text-anchor="middle"
						font-size="9"
						fill="#9ca3af"
						class="dark:fill-gray-500"
					>
						{tick.label}
					</text>
				{/each}

				<!-- Planned curves (z-order: oldest first, most recent on top).
				     Stroke-width encodes revision age (oldest=thinnest, newest=
				     thickest); opacity is fixed at 1.0 so the curve's rendered
				     contrast equals the palette swatch's measured contrast and
				     each curve clears WCAG 1.4.11 against bg-white and
				     bg-gray-900. `vector-effect="non-scaling-stroke"` pins the
				     stroke at device-pixel width even after the SVG viewBox is
				     scaled by the responsive `w-full` wrapper — without it, a
				     1.0px stroke at a small viewport (SVG scaled <1.0×) drops
				     below 1 device pixel and antialiases into a contrast-lossy
				     ghost. Issue #108. -->
				{#each curves as c, i}
					{@const d = buildPlannedPath(c, i)}
					{#if d}
						<path
							{d}
							fill="none"
							stroke={getCurveColor(i, curves.length)}
							stroke-width={getCurveStrokeWidth(i, curves.length)}
							vector-effect="non-scaling-stroke"
						/>
					{/if}
				{/each}

				<!-- Executed curve (heavy overlay on top of its planned counterpart).
				     Defensive z-order per issue #98 item 4: render only the LAST
				     is_executed curve (backend invariant: only most-recent should be
				     flagged). If multiple are flagged, the page-level clientWarnings
				     surfaces a user-visible note. -->
				{#if lastExecutedIndex >= 0}
					{@const d = buildActualPath(curves[lastExecutedIndex], lastExecutedIndex)}
					{#if d}
						<!-- Executed-overlay opacity 0.95 keeps the stroke ≥3:1
						     against both bg-white and bg-gray-900 (Y_blue≈0.219
						     composited at α=0.95). vector-effect parallels the
						     planned-curve treatment. Issue #108. -->
						<path
							{d}
							fill="none"
							stroke="#3b82f6"
							stroke-width="3"
							opacity="0.95"
							vector-effect="non-scaling-stroke"
						/>
					{/if}
				{/if}

				<!-- Change-point vertical markers — direction-aware color + dasharray
				     per issue #105. Color encodes direction (slip/improvement/flat),
				     dasharray provides the non-color redundancy required by WCAG 1.4.1
				     (frontend-ux-reviewer entry-council P1-1). `<title>` carries the
				     direction word for AT users. -->
				{#each changePointVisuals as cp}
					<line
						x1={cp.x}
						y1="0"
						x2={cp.x}
						y2={chartH}
						stroke={cp.strokeColor}
						class={cp.darkStrokeClass}
						stroke-width="1"
						stroke-dasharray={cp.dashArray}
						opacity="0.55"
					>
						<title>{cp.revisionLabel}: {cp.directionLabel} — {cp.description}</title>
					</line>
					<text
						x={cp.x}
						y="-6"
						text-anchor="middle"
						font-size="8"
						fill={cp.strokeColor}
						class={cp.darkFillClass}
					>
						{cp.revisionLabel}
					</text>
				{/each}

				<!-- Endpoint labels (R1..RN). Dot keeps the curve color (3:1
				     graphical object per WCAG 1.4.11). Text fill decoupled to
				     gray-700 / gray-300 so it clears 4.5:1 against either bg
				     mode regardless of palette swatch — issue #108. -->
				{#each endpointLabels as ep}
					<circle cx={ep.x} cy={ep.y} r="3" fill={ep.color} />
					<text
						x={ep.x + 6}
						y={ep.y + 3}
						font-size="9"
						fill="#374151"
						class="dark:fill-gray-300"
						font-weight="500"
					>
						{ep.label}
					</text>
				{/each}

				<!-- Axes -->
				<line
					x1="0"
					y1="0"
					x2="0"
					y2={chartH}
					stroke="#d1d5db"
					stroke-width="1"
					class="dark:stroke-gray-600"
				/>
				<line
					x1="0"
					y1={chartH}
					x2={chartW}
					y2={chartH}
					stroke="#d1d5db"
					stroke-width="1"
					class="dark:stroke-gray-600"
				/>
			</g>
		</svg>

		<!-- Legend (chips, flex-wrap for mobile). Issue #97 part 2 / DA P2 #12
		     mobile collapse: when shouldCollapse=true (mobile <640px AND
		     curves.length > 8), wrapped in <details> with summary; on
		     desktop or N≤8 the summary is omitted and legend renders inline.
		     Always-in-DOM <details> per LifecyclePhaseCard precedent. -->
		<details
			class="mt-3"
			open={detailsOpen}
			ontoggle={(e) => (legendOpen = e.currentTarget.open)}
		>
			{#if shouldCollapse}
				<summary class="text-xs cursor-pointer text-gray-600 dark:text-gray-400 list-none">
					<!-- list-none alone hides the disclosure marker on both webkit
					     and Firefox/Gecko (verified by frontend-ux-reviewer council
					     P2 #7). Earlier draft also added [&::-webkit-details-marker]:hidden
					     which was webkit-only redundant defense; dropped per DA
					     exit-council P2 #7 fix on PR #109. -->
					{legendCollapsedSummary(curves.length)}
				</summary>
			{/if}
			<div class="{shouldCollapse ? 'mt-2' : ''} flex flex-wrap gap-x-4 gap-y-1 px-2 text-xs">
				<!-- Legend chip height mirrors curve stroke-width so legend +
				     chart encode age via the same channel (oldest thinnest,
				     newest thickest). Width fixed at 16px. Background color is
				     the palette swatch (WCAG 1.4.11 graphical, ≥3:1 dual-bg
				     verified). Text uses Tailwind text-gray-600/-400 which is
				     already 1.4.3-compliant. Issue #108. -->
				{#each curves as c, i}
					<div class="flex items-center gap-1.5">
						<span
							class="inline-block"
							style="width: 16px; height: {getLegendChipHeight(i, curves.length)}px; background-color: {getCurveColor(i, curves.length)}"
						></span>
						<span class="text-gray-600 dark:text-gray-400">
							{c.revision_number != null ? `R${c.revision_number}` : `#${i + 1}`}
							{#if c.data_date}
								<span class="text-gray-400 dark:text-gray-500">
									— {c.data_date}
								</span>
							{/if}
						</span>
					</div>
				{/each}
				{#if curves.some((c) => c.is_executed)}
					<div class="flex items-center gap-1.5">
						<span class="inline-block w-4 h-1" style="background-color: #3b82f6"></span>
						<span class="text-gray-600 dark:text-gray-400">{executedLabel}</span>
					</div>
				{/if}
				{#if changePointVisuals.length > 0}
					<div class="flex items-center gap-1.5">
						<span
							class="inline-block w-3 h-px border-t border-dashed border-gray-500 dark:border-gray-400"
						></span>
						<span class="text-gray-600 dark:text-gray-400">{changePointLabel}</span>
					</div>
				{/if}
			</div>
		</details>
	{/if}
</div>
