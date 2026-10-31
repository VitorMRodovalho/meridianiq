// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// The computing poll follows the signed-in state (issue #332).
//
// `/api/v1/projects/pending-statuses` requires a session. The poll used to
// start unconditionally from the root layout, so every signed-out page load
// sent one request and logged a 401. Each case loads fresh copies of the
// store and of `auth.ts`, because both keep module-level state.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { User } from '@supabase/supabase-js';

const getPendingStatuses = vi.fn();

vi.mock('../api', () => ({ getPendingStatuses }));

async function load() {
	vi.resetModules();
	const auth = await import('../auth');
	const computing = await import('./computing');
	let snapshot = { statuses: new Map<string, string>() };
	const unsubscribe = computing.computingProjects.subscribe((s) => {
		snapshot = s as typeof snapshot;
	});
	return { auth, computing, unsubscribe, state: () => snapshot };
}

const SIGNED_IN = { id: 'user-a' } as User;

function pending(projectId: string) {
	return {
		items: [{ project_id: projectId, status: 'pending' }],
		polled_at: '2026-10-31T00:00:00Z',
	};
}

beforeEach(() => {
	vi.useFakeTimers();
	getPendingStatuses.mockReset();
});

afterEach(() => {
	vi.useRealTimers();
});

describe('computing poll and the signed-in state', () => {
	it('sends no request while signed out', async () => {
		const { computing, unsubscribe } = await load();

		computing.startComputingPoll();
		await vi.advanceTimersByTimeAsync(10_000);

		expect(getPendingStatuses).not.toHaveBeenCalled();
		unsubscribe();
	});

	it('starts when a session appears after the poll was requested', async () => {
		getPendingStatuses.mockResolvedValue(pending('p1'));
		const { auth, computing, unsubscribe, state } = await load();

		computing.startComputingPoll();
		auth.user.set(SIGNED_IN);
		await vi.advanceTimersByTimeAsync(0);

		expect(getPendingStatuses).toHaveBeenCalledTimes(1);
		expect(state().statuses.get('p1')).toBe('pending');
		computing.stopComputingPoll();
		unsubscribe();
	});

	it('stops and clears the statuses on sign-out', async () => {
		getPendingStatuses.mockResolvedValue(pending('p1'));
		const { auth, computing, unsubscribe, state } = await load();
		auth.user.set(SIGNED_IN);
		computing.startComputingPoll();
		await vi.advanceTimersByTimeAsync(0);
		const callsWhileSignedIn = getPendingStatuses.mock.calls.length;

		auth.user.set(null);
		await vi.advanceTimersByTimeAsync(30_000);

		expect(state().statuses.size).toBe(0);
		expect(getPendingStatuses).toHaveBeenCalledTimes(callsWhileSignedIn);
		unsubscribe();
	});

	it('drops an answer that arrives after sign-out', async () => {
		let resolve: (value: unknown) => void = () => {};
		getPendingStatuses.mockReturnValue(new Promise((r) => (resolve = r)));
		const { auth, computing, unsubscribe, state } = await load();
		auth.user.set(SIGNED_IN);
		computing.startComputingPoll();
		await vi.advanceTimersByTimeAsync(0);

		auth.user.set(null);
		resolve(pending('p1'));
		await vi.advanceTimersByTimeAsync(0);

		expect(state().statuses.size).toBe(0);
		unsubscribe();
	});

	it('polls again after signing back in', async () => {
		getPendingStatuses.mockResolvedValue(pending('p1'));
		const { auth, computing, unsubscribe } = await load();
		computing.startComputingPoll();
		auth.user.set(SIGNED_IN);
		await vi.advanceTimersByTimeAsync(0);
		auth.user.set(null);
		await vi.advanceTimersByTimeAsync(0);
		const before = getPendingStatuses.mock.calls.length;

		auth.user.set(SIGNED_IN);
		await vi.advanceTimersByTimeAsync(0);

		expect(getPendingStatuses.mock.calls.length).toBe(before + 1);
		computing.stopComputingPoll();
		unsubscribe();
	});
});
