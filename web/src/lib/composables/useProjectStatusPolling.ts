// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// W3 of Cycle 1 v4.0 — per-project status reactive helper.
//
// Reads from the global `computingProjects` store (single aggregate
// poll per user, FE pre-check P1). When a project leaves the pending
// set the helper returns 'ready' so consumer components can re-fetch
// any data that was waiting on materialization (typical case: the
// LifecyclePhaseCard re-fetching its summary after the W3 inference
// engine flips a fresh artifact).
//
// Svelte 5 runes idiom: this helper is a function that returns plain
// reactive accessors. Components call it inside a `$effect` or in
// reactive scope.

import { onDestroy } from 'svelte';
import { get } from 'svelte/store';
import { computingProjects, startComputingPoll } from '../stores/computing';
import type { ProjectStatus } from '../types';

export interface ProjectStatusPolling {
	/** Current best-known status. ``ready`` once the project leaves the pending set. */
	readonly status: ProjectStatus;
	/** True while the project is in the pending or failed set. */
	readonly isComputing: boolean;
	/** ISO timestamp of the last successful aggregate poll. */
	readonly lastPolled: string | null;
	/** Subscribe to status transitions; returns an unsubscribe fn. */
	onChange: (cb: (status: ProjectStatus) => void) => () => void;
}

/**
 * Subscribe to a single project's status via the global polling store.
 *
 * The composable starts the global poll (idempotent), so the first
 * caller in the page tree implicitly opts the user into the banner +
 * status updates. Subsequent callers just attach a listener.
 *
 * Cleanup is automatic via `onDestroy`. The global poll itself
 * continues running for other consumers — explicit teardown happens
 * at sign-out by calling `stopComputingPoll()` directly.
 */
export function useProjectStatusPolling(
	projectId: string,
	opts: { onTerminal?: (status: ProjectStatus) => void } = {}
): ProjectStatusPolling {
	startComputingPoll();

	let lastObserved: ProjectStatus | null = null;
	const listeners = new Set<(status: ProjectStatus) => void>();

	const _resolveStatus = (): ProjectStatus => {
		const snap = get(computingProjects);
		return snap.statuses.get(projectId) ?? 'ready';
	};

	const _resolveLastPolled = (): string | null => get(computingProjects).lastPolled;

	const unsub = computingProjects.subscribe((snap) => {
		const next: ProjectStatus = snap.statuses.get(projectId) ?? 'ready';
		if (lastObserved !== null && lastObserved !== next) {
			for (const cb of listeners) cb(next);
			if ((next === 'ready' || next === 'failed') && opts.onTerminal) {
				opts.onTerminal(next);
			}
		}
		lastObserved = next;
	});

	onDestroy(() => {
		unsub();
		listeners.clear();
	});

	return {
		get status(): ProjectStatus {
			return _resolveStatus();
		},
		get isComputing(): boolean {
			// Council P2 (FE end-of-wave): only 'pending' counts as
			// "computing in the background". 'failed' is terminal —
			// surfacing it as "still working" misleads the UI into the
			// wrong empty / waiting state.
			return _resolveStatus() === 'pending';
		},
		get lastPolled(): string | null {
			return _resolveLastPolled();
		},
		onChange(cb): () => void {
			listeners.add(cb);
			return () => {
				listeners.delete(cb);
			};
		},
	};
}
