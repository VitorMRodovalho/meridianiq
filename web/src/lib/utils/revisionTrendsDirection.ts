// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// Direction → Tailwind text-class mapping for the /revision-trends
// change-points list. Extracted from +page.svelte so it can be unit-
// tested independently of the page render (DA P0 #2 on Cycle 6 W3
// wave 4: the chart marker color was covered, the page list color
// was not — schema-helper drift would have passed silently).
//
// Color tokens (amber-700/emerald-700/gray-600 light + amber-400/
// emerald-400/gray-400 dark) match the chart marker hex set:
//   slip       → amber-700 #b45309
//   improvement → emerald-700 #047857
//   flat        → gray-600 #4b5563
// — verified WCAG-AA contrast against bg-white + bg-gray-900.
// Unknown direction values fall through to neutral gray.

export function directionTextClass(direction: string): string {
	const base = 'font-medium min-w-12';
	if (direction === 'slip') return `text-amber-700 dark:text-amber-400 ${base}`;
	if (direction === 'improvement') return `text-emerald-700 dark:text-emerald-400 ${base}`;
	return `text-gray-600 dark:text-gray-400 ${base}`;
}
