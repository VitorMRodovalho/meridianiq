import { writable } from 'svelte/store';

export interface Toast {
	id: string;
	type: 'success' | 'error' | 'warning' | 'info';
	message: string;
	duration?: number;
}

const { subscribe, update } = writable<Toast[]>([]);

let counter = 0;

export const toasts = { subscribe };

export function toast(type: Toast['type'], message: string, duration = 4000): void {
	const id = `toast-${++counter}`;
	update((all) => [...all, { id, type, message, duration }]);

	if (duration > 0) {
		setTimeout(() => dismiss(id), duration);
	}
}

export function dismiss(id: string): void {
	update((all) => all.filter((t) => t.id !== id));
}

export const success = (msg: string, dur?: number) => toast('success', msg, dur);
export const error = (msg: string, dur?: number) => toast('error', msg, dur ?? 6000);
export const warning = (msg: string, dur?: number) => toast('warning', msg, dur);
export const info = (msg: string, dur?: number) => toast('info', msg, dur);
