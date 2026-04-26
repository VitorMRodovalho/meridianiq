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
	| 'recovering'
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

/**
 * Optional configuration for `useWebSocketProgress`.
 *
 * `recoveryPoller` — ADR-0019 §"W1 — D4". Frontend mitigation for the
 * transient-disconnect-equals-permanent-failure problem inherited from
 * v4.0.0: when the WS closes with a generic `connection_lost` (TLS
 * hiccup, Fly.io single-instance restart blip, ~5–15s) AFTER the
 * composable reached `running` state, the heavy job on the backend is
 * usually still executing. Instead of immediately flipping to `error`,
 * the composable enters `recovering` and polls this caller-provided
 * function on `recoveryIntervalMs` cadence. The poller returns:
 *   - a non-null id  → recovery succeeded; status flips to `done` with
 *     that id as `simulationId` and `onTerminal('done')` fires.
 *   - `null`         → still running, keep polling.
 *   - throws         → give up; status flips to `error` with
 *     `connection_lost`.
 * If `recoveryTimeoutMs` elapses without success, status flips to
 * `error`. Authoritative close codes (4401/4403/4404) bypass recovery
 * — they signal a deliberate server decision, not a transient blip.
 *
 * If `recoveryPoller` is not supplied, the composable's behavior is
 * unchanged from v4.0.1 — `connection_lost` flips straight to `error`.
 * The risk page passes a poller that hits
 * `GET /api/v1/risk/simulations`. Optimize callers don't pass one
 * because optimize results aren't persisted to an id-addressable store
 * (CLAUDE.md known gotcha).
 */
export interface UseWebSocketProgressOptions {
	recoveryPoller?: (jobId: string) => Promise<string | null>;
	/** Total recovery window in ms. Default 60_000 (1 minute). */
	recoveryTimeoutMs?: number;
	/** Poll interval in ms. Default 5_000 (5 seconds). */
	recoveryIntervalMs?: number;
}

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
	/**
	 * Clear error state + reset progress to `idle` so the same composable
	 * instance can be reused for another `start()`. Does NOT open a new
	 * socket. Preserves `onTerminal` subscriptions — the caller owns
	 * listener lifecycle via the unsubscribe fn returned by `onTerminal`.
	 *
	 * For explicit teardown (component unmount, instance being thrown
	 * away) call `destroy()` instead — it additionally clears the
	 * listener set so closures the caller registered cannot outlive the
	 * instance.
	 */
	reset(): void;
	/**
	 * Explicit teardown — closes the socket AND clears `terminalListeners`.
	 * Use on component unmount or whenever the composable instance is
	 * being discarded, to break any closure the caller registered via
	 * `onTerminal()` and avoid the latent listener-leak Track 1 F1
	 * accepted as deferred. Idempotent: safe to call multiple times.
	 *
	 * State is reset to `idle` after teardown, so the instance is
	 * technically reusable for another `start()`. **Consumers SHOULD NOT
	 * rely on this** — listeners registered before `destroy()` are gone
	 * and a subsequent run will not notify them, which is exactly the
	 * silent-failure mode `destroy()` exists to prevent in unmount
	 * paths. For re-running the same composable across renders, use
	 * `reset()` (which preserves listeners). For component teardown,
	 * use `destroy()` and let the instance go out of scope.
	 */
	destroy(): void;
	/**
	 * Subscribe to the single terminal transition (done or error).
	 * Returns an unsubscribe function. Multiple subscribers supported.
	 */
	onTerminal(cb: (status: 'done' | 'error') => void): () => void;
}

function _toWsUrl(wsPath: string): string {
	// wsPath example: "/api/v1/ws/progress/<uuid>"
	if (BASE) {
		// Anchored prefix match so `https?:` at a non-scheme position
		// (e.g. `httpbin.example.com`) cannot mis-trigger.
		if (/^https?:\/\//.test(BASE)) {
			return BASE.replace(/^http/, 'ws') + wsPath;
		}
		// Protocol-relative (`//host`) — `new WebSocket('//host/...')`
		// throws SyntaxError. Resolve scheme against the current page
		// protocol; requires window, so fall through to SSR guard below.
		if (BASE.startsWith('//')) {
			if (typeof window === 'undefined') {
				throw new Error(
					'VITE_API_URL is protocol-relative; resolution requires window (no SSR support)',
				);
			}
			const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
			return `${scheme}${BASE}${wsPath}`;
		}
		throw new Error(
			`VITE_API_URL must start with http://, https:// or //; got: ${BASE}`,
		);
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
export function useWebSocketProgress(
	opts: UseWebSocketProgressOptions = {},
): WebSocketProgress {
	const state = writable<WSProgressState>({ ..._emptyState });
	let socket: WebSocket | null = null;
	let terminalFired = false;
	let currentJobId: string | null = null;
	let recoveryAborted = false;
	const terminalListeners = new Set<(status: 'done' | 'error') => void>();
	const recoveryPoller = opts.recoveryPoller;
	const recoveryTimeoutMs = opts.recoveryTimeoutMs ?? 60_000;
	const recoveryIntervalMs = opts.recoveryIntervalMs ?? 5_000;

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
		if (event.type === 'auth_check') {
			// ADR-0019 §"W1 — D3" heartbeat — server is checking that
			// our JWT is still valid AND keeping the WS alive across
			// idle timeouts. The frame contains no actionable payload
			// for the client; silently drop without flipping state.
			return;
		}
		// `error` event from the producer side.
		_patch({ status: 'error', error: event.message || 'simulation_failed' });
		_fireTerminal('error');
		_closeSocket();
	}

	async function _attemptRecovery(jobId: string): Promise<void> {
		// ADR-0019 §"W1 — D4". Caller has not registered a poller →
		// preserve v4.0.1 behavior (connection_lost → error).
		if (!recoveryPoller) {
			_patch({ status: 'error', error: 'connection_lost' });
			_fireTerminal('error');
			return;
		}
		_patch({ status: 'recovering' });
		const startTs = Date.now();
		while (Date.now() - startTs < recoveryTimeoutMs) {
			// Cancellation: `destroy()` / `reset()` flip `recoveryAborted`
			// to break out of an in-flight loop, preventing phantom polls
			// after component unmount or instance reuse.
			if (recoveryAborted) return;
			if (terminalFired) return; // Caller may have called markDone/markError mid-recovery
			let result: string | null;
			try {
				result = await recoveryPoller(jobId);
			} catch {
				// Poller rejected → give up; the caller's REST surface
				// is unhealthy enough that polling won't recover.
				if (recoveryAborted) return;
				_patch({ status: 'error', error: 'connection_lost' });
				_fireTerminal('error');
				return;
			}
			if (recoveryAborted) return;
			if (result) {
				_patch({ status: 'done', pct: 100, simulationId: result });
				_fireTerminal('done');
				return;
			}
			await new Promise<void>((r) => setTimeout(r, recoveryIntervalMs));
		}
		if (recoveryAborted) return;
		// Window elapsed — declare failure.
		_patch({ status: 'error', error: 'connection_lost' });
		_fireTerminal('error');
	}

	async function _openSocket(wsPath: string): Promise<void> {
		if (typeof window === 'undefined') {
			throw new Error('WebSocket unavailable in this environment');
		}
		const { data } = await supabase.auth.getSession();
		const token = data.session?.access_token;
		// ADR-0019 §"W1 — D3" — opt the connection into the
		// server-initiated `auth_check` heartbeat. Backend keeps the
		// v4.0.1 silent-streaming behavior for clients that don't
		// signal `hb=1`, so cached/legacy frontend bundles continue to
		// work after a backend deploy without seeing the new frame.
		const params = new URLSearchParams();
		params.set('hb', '1');
		if (token) params.set('token', token);
		const wsUrl = `${_toWsUrl(wsPath)}?${params.toString()}`;

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
				// ADR-0019 §"W1 — D4". `connection_lost` (unknown close
				// code) is the only reason eligible for recovery — it
				// indicates a transient transport blip. Authoritative
				// close codes (4401/4403/4404) signal deliberate server
				// decisions and bypass the recovery branch. Recovery
				// only runs when we made it to `running`; pre-open
				// failures already short-circuited via `openErrored`.
				if (reason === 'connection_lost' && currentJobId) {
					void _attemptRecovery(currentJobId);
					return;
				}
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
		currentJobId = job.job_id;
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
		// Intentionally DOES NOT touch `terminalListeners` — subscriptions
		// outlive the run so that re-using the composable after a terminal
		// event does not silently drop already-attached callers. Caller
		// removes its listener via the unsubscribe fn returned by
		// `onTerminal`. For listener teardown, see `destroy()`.
		// `recoveryAborted` flip aborts any in-flight `_attemptRecovery`
		// loop so it doesn't keep polling for the previous run.
		recoveryAborted = true;
		_closeSocket();
		terminalFired = false;
		currentJobId = null;
		state.set({ ..._emptyState });
		// Re-enable for the next run. ``start()`` doesn't read this
		// flag — it's purely the recovery-loop opt-out signal.
		recoveryAborted = false;
	}

	function destroy(): void {
		// Counterpart to `reset()`: tears down the listener set so any
		// closure the caller registered via `onTerminal()` does not
		// outlive the instance. Caller is expected to discard the
		// composable after this. Idempotent — `Set.clear()` and the
		// `_closeSocket` guard tolerate repeated calls. Note: state
		// is reset to idle so a subsequent `start()` would technically
		// succeed, but listeners are gone — see the JSDoc on
		// `WebSocketProgress.destroy` for why we don't poison the
		// instance instead.
		// Like `reset()`, flip `recoveryAborted` so any in-flight
		// recovery loop stops polling against a torn-down component
		// (phantom-fetch + log-noise prevention).
		recoveryAborted = true;
		_closeSocket();
		terminalListeners.clear();
		terminalFired = false;
		currentJobId = null;
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
		destroy,
		onTerminal,
	};
}
