// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// Live-WebSocket runtime test for `useWebSocketProgress` (issue #140 — P2).
//
// The companion suite (`useWebSocketProgress.test.ts`) covers 58 unit
// cases against a FakeWebSocket — the state machine, race-fix
// contracts, terminal-listener invariants. That suite never opens a
// real socket, so a hypothetical regression in the browser-WebSocket
// surface (e.g., upstream svelte-check / SvelteKit hydration timing,
// Vite WS plugin, JSON.parse on the `evt.data` channel) ships green
// from CI and only fires when a human loads `/risk` in the browser.
//
// This file plugs that gap with **one** end-to-end live lifecycle:
//   1. Boot an in-process `ws` server on a dynamic port (no fixed
//      port → safe under parallel test workers).
//   2. Replace `globalThis.WebSocket` with a browser-API-shaped
//      wrapper around the Node `ws` client that redirects every
//      `new WebSocket(url)` to that server (the composable's URL
//      construction via `_toWsUrl()` depends on `VITE_API_URL` /
//      `window.location.host`, which we deliberately keep out of
//      scope — the *transport* is what we're exercising).
//   3. Drive a realistic flow: idle → start → server emits 3 progress
//      frames → server emits `done` → client closes itself.
//   4. Assert: state machine reaches `done`, the `simulationId` from
//      the terminal frame is captured, the WebSocket actually closed
//      from the server's perspective (so we know the auto-close in
//      `_handleEvent('done')` is wired to a *real* `socket.close()`).
//
// Single test by design. Per AGENTS.md "Workflow first, agent second"
// + the issue's acceptance ("One automated test exercises a real
// WebSocket lifecycle"), more tests here would re-cover ground the
// mocked suite already pins. If the live transport regresses, this
// one test will fail; the mocked suite localizes which specific
// transition broke.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';
import { createRequire } from 'node:module';
// Type-only imports — stripped at runtime, so Vite's "browser"-field
// resolution of the `ws` package does not interfere. The .d.ts ships
// the full Node-side surface (Server + RawData + Buffer events).
import type {
	WebSocket as NodeWebSocketInstance,
	WebSocketServer as NodeWebSocketServerInstance,
	RawData,
} from 'ws';

// Vitest's jsdom env resolves `import 'ws'` through Vite's resolver,
// which honors the `ws` package's `"browser"` field → returns the
// browser shim (just the WebSocket *client* class, NO `Server`). For
// a live test we need the Node server-side surface. `createRequire`
// bypasses Vite resolution and uses Node's CommonJS resolver, which
// respects the package's `main` field and gives us the full module.
const nodeRequire = createRequire(import.meta.url);
const wsModule = nodeRequire('ws') as typeof import('ws');
const NodeWebSocket = wsModule.WebSocket;
const WebSocketServer = wsModule.WebSocketServer;

vi.mock('../api', () => ({
	startProgressJob: vi.fn(async () => ({
		job_id: 'job-live-test',
		ws_url: '/api/v1/ws/progress/job-live-test',
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

interface ServerSideSocket {
	send: (data: string) => void;
	close: (code?: number, reason?: string) => void;
	onClose: Promise<{ code: number }>;
}

describe('useWebSocketProgress — live WebSocket lifecycle (issue #140)', () => {
	let wss: NodeWebSocketServerInstance;
	let port: number;
	let serverSidePromise: Promise<ServerSideSocket>;

	beforeEach(async () => {
		// Port 0 = OS picks a free port. Each test gets its own server
		// instance, so parallel workers / repeated runs cannot collide.
		wss = new WebSocketServer({ port: 0 });
		await new Promise<void>((resolve) => wss.once('listening', () => resolve()));
		const addr = wss.address();
		if (typeof addr !== 'object' || addr === null) {
			throw new Error('WebSocketServer.address() returned unexpected shape');
		}
		port = addr.port;

		// Promise that the test awaits to grab the server-side handle
		// once the composable opens its socket. Captured here (not in
		// `it`) so the redirecting WebSocket wrapper below can connect
		// before `start()` even returns.
		serverSidePromise = new Promise<ServerSideSocket>((resolve) => {
			wss.once('connection', (sws) => {
				const closeP = new Promise<{ code: number }>((cr) => {
					sws.once('close', (code) => cr({ code }));
				});
				resolve({
					send: (data) => sws.send(data),
					close: (code, reason) => sws.close(code, reason),
					onClose: closeP,
				});
			});
		});

		// Browser-API-shaped wrapper around the Node `ws` client.
		// `useWebSocketProgress._openSocket` builds a URL from
		// `_toWsUrl(wsPath)` + auth query string; we ignore the URL
		// argument entirely and connect to our test server. The hook
		// only touches the surface in the WebSocket spec
		// (`onopen`/`onmessage`/`onerror`/`onclose`/`close()`/`url`),
		// which is exactly what this wrapper exposes.
		//
		// Buffer→string normalization on `onmessage`: the Node `ws`
		// client emits `data` as a Buffer; the hook calls
		// `JSON.parse(evt.data)` expecting a string. We coerce here
		// so the hook code path matches its browser behavior 1:1.
		class TestWebSocket {
			onopen: ((evt?: Event) => void) | null = null;
			onmessage: ((evt: { data: string }) => void) | null = null;
			onerror: ((evt?: Event) => void) | null = null;
			onclose: ((evt: { code: number; reason?: string }) => void) | null = null;
			readonly url: string;
			private readonly _ws: NodeWebSocketInstance;

			constructor(requestedUrl: string) {
				this.url = requestedUrl;
				this._ws = new NodeWebSocket(`ws://localhost:${port}/`);
				this._ws.on('open', () => this.onopen?.());
				this._ws.on('message', (data: RawData) => {
					// `ws` RawData = Buffer | ArrayBuffer | Buffer[]. The hook
					// expects a string for `JSON.parse`. Coerce uniformly.
					let str: string;
					if (Array.isArray(data)) {
						str = Buffer.concat(data).toString('utf8');
					} else if (Buffer.isBuffer(data)) {
						str = data.toString('utf8');
					} else {
						// data: ArrayBuffer
						str = Buffer.from(new Uint8Array(data)).toString('utf8');
					}
					this.onmessage?.({ data: str });
				});
				this._ws.on('error', () => this.onerror?.());
				this._ws.on('close', (code: number, reason: Buffer) =>
					this.onclose?.({ code, reason: reason.toString() }),
				);
			}

			close(): void {
				this._ws.close();
			}
		}

		(globalThis as Record<string, unknown>).WebSocket = TestWebSocket;
	});

	afterEach(async () => {
		await new Promise<void>((resolve) => wss.close(() => resolve()));
		vi.restoreAllMocks();
	});

	it('round-trips 3 progress frames and a terminal `done` over a real socket; client auto-closes on terminal', async () => {
		const { useWebSocketProgress } = await import('./useWebSocketProgress');
		const p = useWebSocketProgress();

		const startPromise = p.start();
		const server = await serverSidePromise;
		// `start()` resolves on `onopen` — the *real* server has now
		// accepted the connection. State should be `running` per the
		// composable's `_openSocket.onopen` patch.
		await startPromise;
		expect(get(p.state).status).toBe('running');

		// Helper: yield to the event loop so the message handler's
		// store patch is observable. Microtask flush alone is not
		// enough — the `ws` client emits 'message' asynchronously.
		const flushMessage = (): Promise<void> =>
			new Promise((r) => setTimeout(r, 10));

		// Progress event 1
		server.send(JSON.stringify({ type: 'progress', done: 1, total: 5, pct: 20 }));
		await flushMessage();
		{
			const s = get(p.state);
			expect(s.status).toBe('running');
			expect(s.done).toBe(1);
			expect(s.total).toBe(5);
			expect(s.pct).toBe(20);
		}

		// Progress event 2
		server.send(JSON.stringify({ type: 'progress', done: 3, total: 5, pct: 60 }));
		await flushMessage();
		expect(get(p.state).pct).toBe(60);
		expect(get(p.state).done).toBe(3);

		// Progress event 3 (boundary — done=total but no terminal frame yet)
		server.send(JSON.stringify({ type: 'progress', done: 5, total: 5, pct: 100 }));
		await flushMessage();
		expect(get(p.state).done).toBe(5);
		// Status must NOT flip to 'done' just because pct=100 — only the
		// terminal frame is authoritative. Pins the contract that
		// `_handleEvent` does not infer 'done' from pct.
		expect(get(p.state).status).toBe('running');

		// Terminal: `done` frame. The composable's `_handleEvent('done')`
		// patches status='done' + calls `_closeSocket()`, which invokes
		// `socket.close()` — the wrapper forwards to the Node ws client
		// which closes the underlying TCP. The server-side 'close' event
		// resolves `server.onClose` below.
		server.send(JSON.stringify({ type: 'done', simulation_id: 'sim-live-1' }));
		await server.onClose;

		const final = get(p.state);
		expect(final.status).toBe('done');
		expect(final.simulationId).toBe('sim-live-1');
		// `pct` is forced to 100 by `_handleEvent('done')` regardless of
		// the last progress frame — pin that branch.
		expect(final.pct).toBe(100);
	}, 10_000);
});
