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

/** Generate tick marks for the time axis. */
export function generateTimeTicks(
	startDate: string,
	endDate: string,
	zoomLevel: 'day' | 'week' | 'month',
): { date: string; label: string; x: number }[] {
	const start = parseDate(startDate);
	const end = parseDate(endDate);
	const totalDays = Math.max(1, daysBetween(startDate, endDate));
	const ticks: { date: string; label: string; x: number }[] = [];

	const stepDays = zoomLevel === 'day' ? 1 : zoomLevel === 'week' ? 7 : 30;
	const current = new Date(start);

	while (current <= end) {
		const iso = current.toISOString().slice(0, 10);
		const dayOffset = daysBetween(startDate, iso);
		const x = dayOffset / totalDays;

		let label: string;
		if (zoomLevel === 'month') {
			label = current.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
		} else if (zoomLevel === 'week') {
			label = current.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
		} else {
			label = current.getDate().toString();
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
