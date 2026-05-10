// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// Inaugural Vitest + @testing-library/svelte v5 component test for
// MeridianIQ. Cycle 5 W3-B per ADR-0024 — issue #87 closure.
//
// ## Scope cap (frontend-ux-reviewer entry-council on #87)
//
// Exactly 3 tests on RevisionConfirmCard:
//   1. happy path — detect returns a candidate, card renders with name
//   2. **race regression** — rapid re-mount with new projectId; the
//      stale resolution from the prior detect must NOT overwrite state
//      (DA exit-council fix-up #P1-1 from PR #83 — `detectGen` counter)
//   3. no-candidate — detect returns null, no card renders
//
// Other components, snapshot tests, lint integration, CI gating — all
// explicitly out of scope for this PR.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, cleanup, waitFor } from '@testing-library/svelte';
import RevisionConfirmCard from './RevisionConfirmCard.svelte';

// Deferred resolvers so tests can drive the order in which two
// concurrent detect calls complete (race regression).
const detectResolvers: Array<(payload: unknown) => void> = [];
const detectRejecters: Array<(err: Error) => void> = [];
const detectCalls: string[] = [];

vi.mock('$lib/api', () => ({
	detectRevisionOf: vi.fn((projectId: string) => {
		detectCalls.push(projectId);
		return new Promise((resolve, reject) => {
			detectResolvers.push(resolve);
			detectRejecters.push(reject);
		});
	}),
	confirmRevisionOf: vi.fn(),
}));

vi.mock('$lib/analytics', () => ({
	trackEvent: vi.fn(),
}));

vi.mock('$lib/toast', () => ({
	error: vi.fn(),
	success: vi.fn(),
}));

beforeEach(() => {
	detectResolvers.length = 0;
	detectRejecters.length = 0;
	detectCalls.length = 0;
});

afterEach(() => {
	cleanup();
});

function happyPayload(overrides: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		candidate_project_id: 'parent-1',
		candidate_project_name: 'Project Alpha',
		candidate_data_date: '2026-04-01T00:00:00Z',
		candidate_revision_count: 2,
		confidence: 0.9,
		methodology: 'name+program',
		...overrides,
	};
}

describe('RevisionConfirmCard', () => {
	it('renders the candidate name when detect succeeds (happy path)', async () => {
		const { findByRole, queryByRole } = render(RevisionConfirmCard, {
			props: { projectId: 'p-new' },
		});
		// Pre-resolve: card has not rendered yet (loading state shows the
		// checking hint instead).
		expect(queryByRole('region')).toBeNull();

		// Resolve with a candidate payload.
		detectResolvers[0]!(happyPayload());

		// findByRole awaits the next render tick after $effect commits state.
		const region = await findByRole('region');
		expect(region.textContent).toContain('Project Alpha');
	});

	it('does NOT overwrite state when a stale detect resolves after a newer one (race regression)', async () => {
		// Mount with projectId p-old — kicks off detect call #0.
		const { rerender, findByRole } = render(RevisionConfirmCard, {
			props: { projectId: 'p-old' },
		});
		expect(detectCalls).toEqual(['p-old']);

		// Re-render with projectId p-new — kicks off detect call #1 via $effect.
		await rerender({ projectId: 'p-new' });
		expect(detectCalls).toEqual(['p-old', 'p-new']);

		// Resolve the NEWER call first (the one that should win).
		detectResolvers[1]!(happyPayload({ candidate_project_name: 'NEW Winner' }));
		const region = await findByRole('region');
		expect(region.textContent).toContain('NEW Winner');

		// Now resolve the STALE call. The detectGen counter must reject this
		// resolution (myGen !== detectGen) and leave the card showing
		// "NEW Winner" — NOT "STALE Loser".
		detectResolvers[0]!(happyPayload({ candidate_project_name: 'STALE Loser' }));

		// Yield the microtask queue so the stale .then() runs.
		await Promise.resolve();
		await Promise.resolve();

		expect(region.textContent).toContain('NEW Winner');
		expect(region.textContent).not.toContain('STALE Loser');
	});

	it('renders nothing when detect returns no candidate', async () => {
		const { container, queryByRole } = render(RevisionConfirmCard, {
			props: { projectId: 'p-orphan' },
		});

		detectResolvers[0]!(happyPayload({ candidate_project_id: null }));

		// Wait for the loading hint to disappear — the only way to know the
		// component finished its no-candidate transition. Then assert the
		// terminal state: no region, no leftover status hint.
		await waitFor(() => {
			expect(container.querySelector('[role="status"]')).toBeNull();
		});
		expect(queryByRole('region')).toBeNull();
	});
});
