// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// Vitest unit tests for the WebSocket progress composable.
// Covers the state machine, the markDone/markError race-fix contracts,
// the close()-is-pure-cleanup promise, and the reset()-preserves-
// terminalListeners invariant introduced in the Track 1 polish wave.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

vi.mock('../api', () => ({
	startProgressJob: vi.fn(async () => ({
		job_id: 'job-test',
		ws_url: '/api/v1/ws/progress/job-test',
	})),
}));

vi.mock('../supabase', () => ({
	supabase: {
		auth: {
			getSession: vi.fn(async () => ({
				data: { session: { access_token: 'fake-token' } },
			})),
		},
	},
}));

// Capture the most recently constructed WebSocket so tests can drive
// its lifecycle events manually.
class FakeWebSocket {
	static instances: FakeWebSocket[] = [];
	onopen: ((evt?: Event) => void) | null = null;
	onmessage: ((evt: { data: string }) => void) | null = null;
	onerror: ((evt?: Event) => void) | null = null;
	onclose: ((evt: { code: number; reason?: string }) => void) | null = null;
	closeCalled = false;
	url: string;

	constructor(url: string) {
		this.url = url;
		FakeWebSocket.instances.push(this);
	}

	close(): void {
		this.closeCalled = true;
	}

	static latest(): FakeWebSocket {
		const ws = FakeWebSocket.instances.at(-1);
		if (!ws) throw new Error('no WebSocket constructed yet');
		return ws;
	}

	static reset(): void {
		FakeWebSocket.instances = [];
	}
}

// Install the fake before importing the composable — `new WebSocket(...)`
// resolves against `globalThis.WebSocket` at call time.
beforeEach(() => {
	FakeWebSocket.reset();
	(globalThis as Record<string, unknown>).WebSocket = FakeWebSocket;
});

afterEach(() => {
	vi.restoreAllMocks();
});

// Helper: poll the microtask queue until the composable's internal
// Promise chain has reached `new WebSocket(...)`. `start()` awaits
// startProgressJob() and then `supabase.auth.getSession()` before it
// constructs the socket, so a single `setTimeout(0)` flush is not
// always enough.
async function waitForWs(): Promise<FakeWebSocket> {
	for (let i = 0; i < 100; i++) {
		await new Promise((r) => setTimeout(r, 0));
		if (FakeWebSocket.instances.length > 0) return FakeWebSocket.latest();
	}
	throw new Error('WebSocket was never constructed within 100 microtask ticks');
}

// Drive a composable from idle → running using the fake socket.
async function driveToRunning(p: {
	start: () => Promise<string>;
}): Promise<FakeWebSocket> {
	const startPromise = p.start();
	const ws = await waitForWs();
	ws.onopen?.();
	await startPromise;
	return ws;
}

describe('useWebSocketProgress', () => {
	describe('start() lifecycle', () => {
		it('transitions idle → starting → connecting → running on open', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const stateSnapshots: string[] = [];
			p.state.subscribe((s) => stateSnapshots.push(s.status));

			const startPromise = p.start();
			const ws = await waitForWs();
			// By the time waitForWs() returns, we've passed through
			// 'starting' and 'connecting' in the state machine.
			expect(stateSnapshots).toContain('starting');
			expect(stateSnapshots).toContain('connecting');

			ws.onopen?.();
			await startPromise;
			expect(get(p.state).status).toBe('running');
		});

		it('rejects start() if already past idle and reset() not called first', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();

			await driveToRunning(p);
			await expect(p.start()).rejects.toThrow(/call reset\(\) first/);
		});
	});

	describe('progress events', () => {
		it('updates done/total/pct on progress event', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const ws = await driveToRunning(p);

			ws.onmessage?.({
				data: JSON.stringify({ type: 'progress', done: 5, total: 10, pct: 50 }),
			});
			expect(get(p.state).done).toBe(5);
			expect(get(p.state).total).toBe(10);
			expect(get(p.state).pct).toBe(50);
			expect(get(p.state).status).toBe('running');
		});

		it('malformed frames are dropped without flipping state', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const ws = await driveToRunning(p);

			ws.onmessage?.({ data: 'not-json' });
			expect(get(p.state).status).toBe('running');
		});
	});

	describe('terminal via WS done event', () => {
		it('flips status to done, pct=100, captures simulation_id', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const ws = await driveToRunning(p);

			ws.onmessage?.({
				data: JSON.stringify({ type: 'done', simulation_id: 'sim-123' }),
			});
			const s = get(p.state);
			expect(s.status).toBe('done');
			expect(s.pct).toBe(100);
			expect(s.simulationId).toBe('sim-123');
		});

		it('fires onTerminal listeners exactly once', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const onTerm = vi.fn();
			p.onTerminal(onTerm);

			const ws = await driveToRunning(p);

			ws.onmessage?.({ data: JSON.stringify({ type: 'done' }) });
			ws.onmessage?.({ data: JSON.stringify({ type: 'done' }) });

			expect(onTerm).toHaveBeenCalledTimes(1);
			expect(onTerm).toHaveBeenCalledWith('done');
		});
	});

	describe('close() is pure cleanup (race-fix)', () => {
		it('does NOT flip status when called before terminal', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			await driveToRunning(p);

			p.close();
			// Status stays at running — no 'cancelled'/'done'/'error' flip.
			expect(get(p.state).status).toBe('running');
		});

		it('does NOT fire onTerminal when called before terminal', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const onTerm = vi.fn();
			p.onTerminal(onTerm);

			await driveToRunning(p);

			p.close();
			expect(onTerm).not.toHaveBeenCalled();
		});
	});

	describe('markDone / markError (authoritative HTTP-side terminals)', () => {
		it('markDone sets done + fires listener, idempotent', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const onTerm = vi.fn();
			p.onTerminal(onTerm);

			await driveToRunning(p);

			p.markDone('sim-42');
			p.markDone('sim-42');
			expect(get(p.state).status).toBe('done');
			expect(get(p.state).simulationId).toBe('sim-42');
			expect(onTerm).toHaveBeenCalledTimes(1);
		});

		it('markError sets error + fires listener, idempotent', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const onTerm = vi.fn();
			p.onTerminal(onTerm);

			await driveToRunning(p);

			p.markError('boom');
			p.markError('boom2');
			expect(get(p.state).status).toBe('error');
			expect(get(p.state).error).toBe('boom');
			expect(onTerm).toHaveBeenCalledTimes(1);
		});

		it('markDone is a no-op after WS done already terminated', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const onTerm = vi.fn();
			p.onTerminal(onTerm);

			const ws = await driveToRunning(p);

			ws.onmessage?.({
				data: JSON.stringify({ type: 'done', simulation_id: 'ws-sim' }),
			});
			p.markDone('http-sim');

			// WS fired first — simulationId stays from WS.
			expect(get(p.state).simulationId).toBe('ws-sim');
			expect(onTerm).toHaveBeenCalledTimes(1);
		});
	});

	describe('reset() — Track 1 F1 contract', () => {
		it('preserves onTerminal listeners across a reset+rerun cycle', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const onTerm = vi.fn();
			p.onTerminal(onTerm);

			// First run
			const ws1 = await driveToRunning(p);
			ws1.onmessage?.({ data: JSON.stringify({ type: 'done' }) });
			expect(onTerm).toHaveBeenCalledTimes(1);

			// Reset and re-run — listener must still fire.
			p.reset();
			expect(get(p.state).status).toBe('idle');

			const ws2 = await driveToRunning(p);
			ws2.onmessage?.({ data: JSON.stringify({ type: 'done' }) });
			expect(onTerm).toHaveBeenCalledTimes(2);
		});

		it('onTerminal unsubscribe fn still works after reset', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const onTerm = vi.fn();
			const unsubscribe = p.onTerminal(onTerm);

			const ws1 = await driveToRunning(p);
			ws1.onmessage?.({ data: JSON.stringify({ type: 'done' }) });
			expect(onTerm).toHaveBeenCalledTimes(1);

			p.reset();
			unsubscribe();

			const ws2 = await driveToRunning(p);
			ws2.onmessage?.({ data: JSON.stringify({ type: 'done' }) });
			// Unsubscribed — still 1.
			expect(onTerm).toHaveBeenCalledTimes(1);
		});
	});

	describe('destroy() — explicit listener cleanup (ADR-0019 §W0 D11)', () => {
		it('clears terminalListeners (subscribed callbacks no longer fire)', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const onTerm = vi.fn();
			p.onTerminal(onTerm);

			p.destroy();

			// Re-driving after destroy: even if the consumer mistakenly
			// reuses the instance and the WS fires a done event, the
			// previously-registered listener must NOT be invoked.
			const ws = await driveToRunning(p);
			ws.onmessage?.({ data: JSON.stringify({ type: 'done' }) });
			expect(onTerm).not.toHaveBeenCalled();
		});

		it('closes the socket', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const ws = await driveToRunning(p);

			p.destroy();

			expect(ws.closeCalled).toBe(true);
		});

		it('is idempotent — calling twice does not throw', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			await driveToRunning(p);

			expect(() => {
				p.destroy();
				p.destroy();
			}).not.toThrow();
		});

		it('resets state to idle so callers reading state after destroy see empty', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const ws = await driveToRunning(p);
			ws.onmessage?.({
				data: JSON.stringify({ type: 'progress', done: 5, total: 10, pct: 50 }),
			});
			expect(get(p.state).status).toBe('running');

			p.destroy();

			expect(get(p.state).status).toBe('idle');
			expect(get(p.state).pct).toBe(0);
		});
	});

	describe('auth_check heartbeat (ADR-0019 §W1 D3)', () => {
		it('silently drops auth_check frames without flipping state', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const ws = await driveToRunning(p);

			// Send a few auth_check heartbeats — state must stay running.
			ws.onmessage?.({ data: JSON.stringify({ type: 'auth_check', ts: 1000 }) });
			ws.onmessage?.({ data: JSON.stringify({ type: 'auth_check', ts: 1030 }) });

			expect(get(p.state).status).toBe('running');
			// done counter should not have advanced — auth_check is not progress.
			expect(get(p.state).done).toBe(0);
		});
	});

	describe('recoveryPoller (ADR-0019 §W1 D4)', () => {
		it('without poller, connection_lost flips straight to error (v4.0.1 parity)', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const ws = await driveToRunning(p);

			ws.onclose?.({ code: 1006 });

			expect(get(p.state).status).toBe('error');
			expect(get(p.state).error).toBe('connection_lost');
		});

		it('with poller, connection_lost enters recovering and resolves done when poller returns id', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const poller = vi.fn(async () => 'risk-0042');
			const p = useWebSocketProgress({
				recoveryPoller: poller,
				recoveryIntervalMs: 1, // tight loop for the test
				recoveryTimeoutMs: 1000,
			});
			const ws = await driveToRunning(p);

			ws.onclose?.({ code: 1006 });

			// Recovery enters; let microtasks drain
			await new Promise((r) => setTimeout(r, 20));

			expect(poller).toHaveBeenCalled();
			expect(get(p.state).status).toBe('done');
			expect(get(p.state).simulationId).toBe('risk-0042');
		});

		it('with poller returning null, stays in recovering and keeps polling until timeout', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const poller = vi.fn(async () => null);
			const p = useWebSocketProgress({
				recoveryPoller: poller,
				recoveryIntervalMs: 1,
				recoveryTimeoutMs: 30,
			});
			const ws = await driveToRunning(p);

			ws.onclose?.({ code: 1006 });

			// During recovery window, status is 'recovering'
			await new Promise((r) => setTimeout(r, 5));
			expect(get(p.state).status).toBe('recovering');

			// After window elapses, declares failure.
			await new Promise((r) => setTimeout(r, 50));
			expect(get(p.state).status).toBe('error');
			expect(get(p.state).error).toBe('connection_lost');
			expect(poller.mock.calls.length).toBeGreaterThanOrEqual(2);
		});

		it('with poller throwing, gives up immediately with error', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const poller = vi.fn(async () => {
				throw new Error('REST is also down');
			});
			const p = useWebSocketProgress({
				recoveryPoller: poller,
				recoveryIntervalMs: 1,
				recoveryTimeoutMs: 1000,
			});
			const ws = await driveToRunning(p);

			ws.onclose?.({ code: 1006 });
			await new Promise((r) => setTimeout(r, 20));

			expect(get(p.state).status).toBe('error');
			expect(get(p.state).error).toBe('connection_lost');
			// Poller called once and rejected — no more attempts.
			expect(poller).toHaveBeenCalledTimes(1);
		});

		it('destroy() during recovery aborts the poll loop (no phantom polls)', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const poller = vi.fn(async () => null);
			const p = useWebSocketProgress({
				recoveryPoller: poller,
				recoveryIntervalMs: 5,
				recoveryTimeoutMs: 1000,
			});
			const ws = await driveToRunning(p);

			ws.onclose?.({ code: 1006 });

			// Let recovery enter and fire at least one poll.
			await new Promise((r) => setTimeout(r, 20));
			const callsBeforeDestroy = poller.mock.calls.length;
			expect(callsBeforeDestroy).toBeGreaterThanOrEqual(1);

			p.destroy();

			// Wait past several would-be poll intervals; no further polls.
			await new Promise((r) => setTimeout(r, 50));
			expect(poller.mock.calls.length).toBe(callsBeforeDestroy);
		});

		it('authoritative close codes (4401) bypass recovery even with poller', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const poller = vi.fn(async () => 'should-not-be-called');
			const p = useWebSocketProgress({ recoveryPoller: poller });
			const ws = await driveToRunning(p);

			ws.onclose?.({ code: 4401 });

			expect(get(p.state).status).toBe('error');
			expect(get(p.state).error).toBe('auth_expired');
			expect(poller).not.toHaveBeenCalled();
		});
	});

	describe('WebSocket close reason mapping (ADR-0013)', () => {
		it('maps code 4401 to auth_expired', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const ws = await driveToRunning(p);

			ws.onclose?.({ code: 4401 });
			expect(get(p.state).status).toBe('error');
			expect(get(p.state).error).toBe('auth_expired');
		});

		it('maps unknown close code to connection_lost', async () => {
			const { useWebSocketProgress } = await import('./useWebSocketProgress');
			const p = useWebSocketProgress();
			const ws = await driveToRunning(p);

			ws.onclose?.({ code: 1006 });
			expect(get(p.state).status).toBe('error');
			expect(get(p.state).error).toBe('connection_lost');
		});
	});
});
