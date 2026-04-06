import { writable } from 'svelte/store';
import { browser } from '$app/environment';

function getInitialTheme(): boolean {
	if (!browser) return false;
	const stored = localStorage.getItem('meridianiq-theme');
	if (stored !== null) return stored === 'dark';
	return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

export const isDark = writable<boolean>(getInitialTheme());

export function toggleTheme(): void {
	isDark.update((dark) => {
		const next = !dark;
		if (browser) {
			localStorage.setItem('meridianiq-theme', next ? 'dark' : 'light');
			document.documentElement.classList.toggle('dark', next);
		}
		return next;
	});
}

export function initTheme(): void {
	if (!browser) return;
	const dark = getInitialTheme();
	document.documentElement.classList.toggle('dark', dark);
	isDark.set(dark);
}
