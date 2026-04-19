// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// W3 of Cycle 1 v4.0 — global "computing projects" store.
//
// Polls `/api/v1/projects/pending-statuses` (the W3 banner aggregator
// introduced to avoid the N-poller-per-N-projects storm flagged by
// frontend-ux-reviewer). One poll per logged-in user is enough to
// power both the sticky `ComputingBanner` AND any per-project
// awareness (e.g. the LifecyclePhaseCard waiting to re-fetch its
// summary after status flips ready).
//
// Discipline (per FE pre-check):
// - 3 s default interval.
// - Auto-pause when `document.visibilityState === 'hidden'`; resume on
//   visibilitychange with an immediate one-shot poll.
// - Exponential backoff on 5xx / network errors (3 → 6 → 12 → 24 s,
//   capped at 30 s) up to MAX_CONSECUTIVE_ERRORS, then pauses with
//   a one-shot manual `pollNow()` retry path.
// - 401 / 403 / 404 are terminal — stop polling so we never paint a
//   stale UI from a session that has already expired.
// - SSR-safe: all browser APIs (`document`, `setInterval`,
//   `setTimeout`) are guarded behind `typeof window !== 'undefined'`
//   so the adapter-static prerender on Cloudflare Pages does not
//   trip.

import { readable, type Readable } from 'svelte/store';
import type { PendingStatusItem, ProjectStatus } from '../types';

const DEFAULT_INTERVAL_MS = 3000;
const MAX_BACKOFF_MS = 30_000;
const MAX_CONSECUTIVE_ERRORS = 10;

export interface ComputingState {
	/** Map of project_id → current non-terminal status. */
	statuses: Map<string, ProjectStatus>;
	/** True between scheduled polls; false when paused (visibility / backoff stopped). */
	isPolling: boolean;
	/** Number of consecutive failed polls; resets to 0 on success. */
	consecutiveErrors: number;
	/** ISO timestamp of the last successful poll. */
	lastPolled: string | null;
}

const _emptyState: ComputingState = {
	statuses: new Map(),
	isPolling: false,
	consecutiveErrors: 0,
	lastPolled: null,
};

let _started = false;
let _setState: ((value: ComputingState) => void) | null = null;
let _state: ComputingState = _emptyState;
let _timer: ReturnType<typeof setTimeout> | null = null;
let _visibilityListener: (() => void) | null = null;
let _stopRequested = false;

function _publish(next: Partial<ComputingState>): void {
	_state = { ..._state, ...next };
	_setState?.(_state);
}

async function _pollOnce(): Promise<void> {
	// Lazy import to avoid pulling supabase / api wiring at module load
	// time — keeps SSR / tree-shaking friendly.
	const { getPendingStatuses } = await import('../api');
	try {
		const result = await getPendingStatuses();
		const next = new Map<string, ProjectStatus>();
		for (const item of result.items as PendingStatusItem[]) {
			next.set(item.project_id, item.status);
		}
		_publish({
			statuses: next,
			consecutiveErrors: 0,
			lastPolled: result.polled_at ?? new Date().toISOString(),
			isPolling: !_stopRequested,
		});
	} catch (err) {
		// Treat 401 / 403 / 404 as terminal: do not flip backoff, just stop.
		const message = err instanceof Error ? err.message : String(err);
		const isTerminal =
			message.includes('401') ||
			message.includes('403') ||
			message.includes('404') ||
			/unauthor/i.test(message);
		if (isTerminal) {
			console.warn('computing-poll: terminal error, stopping', message);
			stopComputingPoll();
			return;
		}
		_publish({
			consecutiveErrors: _state.consecutiveErrors + 1,
			isPolling: !_stopRequested,
		});
	}
}

function _scheduleNext(): void {
	if (typeof window === 'undefined') return;
	if (_stopRequested) return;
	if (_state.consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
		// Hand off to manual retry — no auto-resume.
		_publish({ isPolling: false });
		return;
	}
	if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
		// Don't schedule while the tab is hidden; visibilitychange will resume.
		_publish({ isPolling: false });
		return;
	}
	const backoff =
		_state.consecutiveErrors === 0
			? DEFAULT_INTERVAL_MS
			: Math.min(MAX_BACKOFF_MS, DEFAULT_INTERVAL_MS * Math.pow(2, _state.consecutiveErrors));
	_publish({ isPolling: true });
	_timer = setTimeout(async () => {
		_timer = null;
		await _pollOnce();
		_scheduleNext();
	}, backoff);
}

/** Force a single poll regardless of schedule (used by manual retry button). */
export async function pollNow(): Promise<void> {
	if (_timer !== null) {
		clearTimeout(_timer);
		_timer = null;
	}
	// Reset error counter so the next backoff starts fresh.
	_publish({ consecutiveErrors: 0 });
	await _pollOnce();
	_scheduleNext();
}

export function startComputingPoll(): void {
	if (typeof window === 'undefined') return;
	if (_started) return;
	_started = true;
	_stopRequested = false;
	_publish({ isPolling: true });

	if (typeof document !== 'undefined') {
		_visibilityListener = (): void => {
			if (document.visibilityState === 'visible' && !_stopRequested) {
				if (_timer === null) {
					// Resume with an immediate fetch + scheduled cycle.
					void pollNow();
				}
			} else if (document.visibilityState === 'hidden') {
				if (_timer !== null) {
					clearTimeout(_timer);
					_timer = null;
				}
				_publish({ isPolling: false });
			}
		};
		document.addEventListener('visibilitychange', _visibilityListener);
	}

	// Kick off — first request fires immediately, then schedules.
	void (async () => {
		await _pollOnce();
		_scheduleNext();
	})();
}

export function stopComputingPoll(): void {
	_stopRequested = true;
	_started = false;
	if (_timer !== null) {
		clearTimeout(_timer);
		_timer = null;
	}
	if (typeof document !== 'undefined' && _visibilityListener) {
		document.removeEventListener('visibilitychange', _visibilityListener);
		_visibilityListener = null;
	}
	_publish({ isPolling: false });
}

/**
 * Reactive computing-projects store. Subscribes the consumer to the
 * polled state. Components reading this store should NOT call
 * start/stop themselves — the layout-level kicker owns that lifecycle.
 */
export const computingProjects: Readable<ComputingState> = readable<ComputingState>(
	_emptyState,
	(set) => {
		_setState = set;
		// Push the current snapshot to the new subscriber immediately so
		// late-mounting components receive whatever the layout already
		// fetched.
		set(_state);
		return () => {
			_setState = null;
		};
	}
);
