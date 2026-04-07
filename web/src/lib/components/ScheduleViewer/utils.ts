/** Convert ISO date string to Date object. */
export function parseDate(iso: string): Date {
	return new Date(iso + 'T00:00:00');
}

/** Days between two ISO date strings. */
export function daysBetween(start: string, end: string): number {
	const s = parseDate(start);
	const e = parseDate(end);
	return Math.round((e.getTime() - s.getTime()) / 86_400_000);
}

/** Format date as short label (e.g. "Jan 15"). */
export function formatDateShort(iso: string): string {
	if (!iso) return '';
	const d = parseDate(iso);
	return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Format date as full (e.g. "2026-01-15"). */
export function formatDateFull(iso: string): string {
	return iso?.slice(0, 10) || '';
}

/** Generate tick marks for the time axis with dynamic density. */
export function generateTimeTicks(
	startDate: string,
	endDate: string,
	zoomLevel: 'day' | 'week' | 'month',
): { date: string; label: string; x: number }[] {
	const start = parseDate(startDate);
	const end = parseDate(endDate);
	const totalDays = Math.max(1, daysBetween(startDate, endDate));
	const ticks: { date: string; label: string; x: number }[] = [];

	// Dynamic step: ensure max ~25 labels to prevent overlap
	const MAX_LABELS = 25;
	let stepDays: number;
	if (zoomLevel === 'month') {
		stepDays = Math.max(30, Math.ceil(totalDays / MAX_LABELS / 30) * 30);
	} else if (zoomLevel === 'week') {
		stepDays = Math.max(7, Math.ceil(totalDays / MAX_LABELS / 7) * 7);
	} else {
		// Day zoom: adapt step if too many days
		stepDays = Math.max(1, Math.ceil(totalDays / MAX_LABELS));
	}

	const current = new Date(start);

	while (current <= end) {
		const iso = current.toISOString().slice(0, 10);
		const dayOffset = daysBetween(startDate, iso);
		const x = dayOffset / totalDays;

		let label: string;
		if (stepDays >= 28 || zoomLevel === 'month') {
			label = current.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
		} else if (stepDays >= 5) {
			label = current.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
		} else {
			label = current.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
		}

		ticks.push({ date: iso, label, x });
		current.setDate(current.getDate() + stepDays);
	}

	return ticks;
}

/** Status to color mapping. */
export const STATUS_COLORS: Record<string, string> = {
	complete: '#10b981',
	active: '#3b82f6',
	not_started: '#9ca3af',
};

/** Get bar color for an activity. */
export function getBarColor(status: string, isCritical: boolean): string {
	if (isCritical && status !== 'complete') return '#ef4444';
	return STATUS_COLORS[status] || '#9ca3af';
}
