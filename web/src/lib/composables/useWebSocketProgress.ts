// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// W5/W6 of Cycle 1 v4.0 (path A fallback per ADR-0009 Amendment 2).
//
// WebSocket progress composable for long-running analytics jobs.
// Consumes the channel published by the backend at
// `/api/v1/ws/progress/{job_id}` (see ADR-0013 server-generated
// job_id + ownership binding + stale-channel reaper).
//
// Flow the caller orchestrates:
//   1. `const p = useWebSocketProgress()`  — zero-cost, no socket yet
//   2. `const jobId = await p.start()`     — POST /jobs/progress/start
//      + open WS. Resolves when socket is open (or rejects on start
//      failure). On resolution the backend has allocated + bound the
//      channel to the current user.
//   3. Caller triggers the heavy endpoint with `?job_id=${jobId}`.
//   4. Composable flips state through `'running'` → `'done' | 'error'`
//      as events arrive. The socket auto-closes on terminal event.
//   5. `p.close()` is idempotent; caller invokes it in a `finally`
//      block to guarantee cleanup on cancellation paths.
//
// Deliberate non-features:
//   - No auto-reconnect. ADR-0013 explicitly states that missed
//     events do not replay, so reconnecting would be dishonest UX.
//     Pre-terminal disconnect flips status → 'error' with message
//     `connection_lost`; the caller should fall back to refreshing
//     the result list after the POST resolves.
//   - No Page Visibility pause/resume. WebSockets are push, so there
//     is nothing to suspend while the tab is hidden.
//
// SSR-safe: every browser API access is guarded behind
// `typeof window !== 'undefined'` so adapter-static prerender does
// not trip.

import { writable, get, type Readable } from 'svelte/store';
import { startProgressJob } from '../api';
import { supabase } from '../supabase';
import type { WSProgressEvent } from '../types';

const BASE = import.meta.env.VITE_API_URL || '';

export type WSProgressStatus =
	| 'idle'
	| 'starting'
	| 'connecting'
	| 'running'
	| 'done'
	| 'error';

export interface WSProgressState {
	status: WSProgressStatus;
	done: number;
	total: number;
	pct: number;
	error: string | null;
	simulationId: string | null;
}

const _emptyState: WSProgressState = {
	status: 'idle',
	done: 0,
	total: 0,
	pct: 0,
	error: null,
	simulationId: null,
};

export interface WebSocketProgress {
	/** Current status — `idle` before `start()`, `done` / `error` after terminal. */
	readonly status: WSProgressStatus;
	/** Completed work units reported by the backend (0 before first event). */
	readonly done: number;
	/** Total work units; stays 0 until the first progress event. */
	readonly total: number;
	/** Convenience percentage (0..100) computed from `done` / `total`. */
	readonly pct: number;
	/** Semantic error string on `error` status; `null` otherwise. */
	readonly error: string | null;
	/** Simulation id returned by the `done` terminal event (risk sim only). */
	readonly simulationId: string | null;
	/**
	 * Readable Svelte store of the full reactive state. Consumers in
	 * `.svelte` files can auto-subscribe via the `$store` syntax — bind
	 * the returned value to a local `const` and read it as `$state.pct`
	 * inside the template. Every WebSocket frame triggers a store update
	 * so the template re-renders without manual polling.
	 */
	readonly state: Readable<WSProgressState>;
	/**
	 * Allocate a job, open the WebSocket and return the job_id. Resolves
	 * when the socket has accepted the connection; the caller is then
	 * free to invoke the heavy endpoint with `?job_id=<jobId>`.
	 */
	start(): Promise<string>;
	/**
	 * Pure cleanup: close the socket if still open. Does NOT mutate
	 * status — callers that want to force a terminal state must call
	 * `markDone` / `markError` first. This design intentionally avoids
	 * the race where a successful REST response completes before the WS
	 * `done` frame arrives: calling `close()` in a `finally` block no
	 * longer flips the state machine to `cancelled`.
	 */
	close(): void;
	/**
	 * Authoritative "simulation completed" signal from the caller (typically
	 * the HTTP response). Idempotent: no-op if a terminal already fired via
	 * the WS path. This is the race-fix companion to pure-cleanup `close()`.
	 */
	markDone(simulationId?: string | null): void;
	/**
	 * Authoritative "simulation failed" signal from the caller (typically a
	 * caught exception). Idempotent. See `markDone`.
	 */
	markError(message: string): void;
	/** Clear error state + go back to `idle`. Does NOT open a new socket. */
	reset(): void;
	/**
	 * Subscribe to the single terminal transition (done or error).
	 * Returns an unsubscribe function. Multiple subscribers supported.
	 */
	onTerminal(cb: (status: 'done' | 'error') => void): () => void;
}

function _toWsUrl(wsPath: string): string {
	// wsPath example: "/api/v1/ws/progress/<uuid>"
	if (BASE) {
		return BASE.replace(/^http/, 'ws') + wsPath;
	}
	// Same-origin fallback for local dev / integration tests.
	if (typeof window !== 'undefined') {
		const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
		return `${scheme}//${window.location.host}${wsPath}`;
	}
	return wsPath;
}

function _mapCloseReason(code: number): string {
	// Mirror ADR-0013 close codes into stable strings the UI can i18n.
	if (code === 4401) return 'auth_expired';
	if (code === 4403) return 'forbidden';
	if (code === 4404) return 'job_not_found';
	return 'connection_lost';
}

/**
 * Factory for a per-consumer WebSocket progress composable. Each call
 * returns an isolated instance — two pages running simulations in
 * parallel get independent sockets and independent state.
 */
export function useWebSocketProgress(): WebSocketProgress {
	const state = writable<WSProgressState>({ ..._emptyState });
	let socket: WebSocket | null = null;
	let terminalFired = false;
	const terminalListeners = new Set<(status: 'done' | 'error') => void>();

	function _patch(next: Partial<WSProgressState>): void {
		state.update((s) => ({ ...s, ...next }));
	}

	function _fireTerminal(status: 'done' | 'error'): void {
		if (terminalFired) return;
		terminalFired = true;
		for (const cb of terminalListeners) cb(status);
	}

	function _closeSocket(): void {
		if (socket) {
			try {
				socket.close();
			} catch {
				/* already closing — ignore */
			}
			socket = null;
		}
	}

	function _handleEvent(event: WSProgressEvent): void {
		if (event.type === 'progress') {
			_patch({
				status: 'running',
				done: event.done,
				total: event.total,
				pct: event.pct,
			});
			return;
		}
		if (event.type === 'done') {
			_patch({
				status: 'done',
				pct: 100,
				simulationId: event.simulation_id ?? null,
			});
			_fireTerminal('done');
			_closeSocket();
			return;
		}
		// `error` event from the producer side.
		_patch({ status: 'error', error: event.message || 'simulation_failed' });
		_fireTerminal('error');
		_closeSocket();
	}

	async function _openSocket(wsPath: string): Promise<void> {
		if (typeof window === 'undefined') {
			throw new Error('WebSocket unavailable in this environment');
		}
		const { data } = await supabase.auth.getSession();
		const token = data.session?.access_token;
		const wsUrl = _toWsUrl(wsPath) + (token ? `?token=${encodeURIComponent(token)}` : '');

		return new Promise<void>((resolve, reject) => {
			let opened = false;
			let openErrored = false;
			const ws = new WebSocket(wsUrl);
			socket = ws;

			ws.onopen = (): void => {
				opened = true;
				_patch({ status: 'running' });
				resolve();
			};
			ws.onmessage = (evt): void => {
				try {
					const parsed = JSON.parse(evt.data) as WSProgressEvent;
					_handleEvent(parsed);
				} catch {
					// Malformed frame from backend — not a terminal condition.
					// Silently drop; keep the socket open for well-formed frames.
				}
			};
			ws.onerror = (): void => {
				if (!opened) {
					openErrored = true;
					_patch({ status: 'error', error: 'connection_failed' });
					_fireTerminal('error');
					reject(new Error('WebSocket failed to connect'));
				}
				// Post-open errors are surfaced through `onclose` with a
				// reason code; do not fire `error` status twice.
			};
			ws.onclose = (evt): void => {
				socket = null;
				// `onerror` already patched + terminal-fired on pre-open
				// failure; avoid clobbering the more-specific reason with
				// the generic `_mapCloseReason(evt.code)` here.
				if (openErrored || terminalFired) return;
				const reason = _mapCloseReason(evt.code);
				_patch({ status: 'error', error: reason });
				_fireTerminal('error');
			};
		});
	}

	async function start(): Promise<string> {
		const current = get(state);
		if (current.status !== 'idle') {
			throw new Error(`start() called while in status=${current.status}; call reset() first`);
		}
		_patch({ status: 'starting' });
		let job: { job_id: string; ws_url: string };
		try {
			job = await startProgressJob();
		} catch (e) {
			const msg = e instanceof Error ? e.message : 'start_failed';
			_patch({ status: 'error', error: msg });
			_fireTerminal('error');
			throw e;
		}
		_patch({ status: 'connecting' });
		try {
			await _openSocket(job.ws_url);
		} catch (e) {
			// `_openSocket` already patched state + fired terminal.
			throw e;
		}
		return job.job_id;
	}

	function close(): void {
		// Pure cleanup — intentionally no status mutation. Callers hit
		// `close()` in a `finally` block after the heavy REST response
		// resolves; if we marked status=cancelled here we would race the
		// WS `done` frame and misclassify successful runs. Callers that
		// truly want to cancel use `markError('cancelled')`.
		_closeSocket();
	}

	function markDone(simulationId?: string | null): void {
		if (terminalFired) return;
		_patch({
			status: 'done',
			pct: 100,
			simulationId: simulationId ?? null,
		});
		_fireTerminal('done');
		_closeSocket();
	}

	function markError(message: string): void {
		if (terminalFired) return;
		_patch({ status: 'error', error: message || 'error' });
		_fireTerminal('error');
		_closeSocket();
	}

	function reset(): void {
		_closeSocket();
		terminalFired = false;
		terminalListeners.clear();
		state.set({ ..._emptyState });
	}

	function onTerminal(cb: (status: 'done' | 'error') => void): () => void {
		terminalListeners.add(cb);
		return () => {
			terminalListeners.delete(cb);
		};
	}

	return {
		get status(): WSProgressStatus {
			return get(state).status;
		},
		get done(): number {
			return get(state).done;
		},
		get total(): number {
			return get(state).total;
		},
		get pct(): number {
			return get(state).pct;
		},
		get error(): string | null {
			return get(state).error;
		},
		get simulationId(): string | null {
			return get(state).simulationId;
		},
		state: { subscribe: state.subscribe } as Readable<WSProgressState>,
		start,
		close,
		markDone,
		markError,
		reset,
		onTerminal,
	};
}
