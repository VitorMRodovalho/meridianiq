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
import { fireEvent, render, cleanup, waitFor } from '@testing-library/svelte';
import RevisionConfirmCard from './RevisionConfirmCard.svelte';
import { ApiError } from '$lib/api';

// Deferred resolvers so tests can drive the order in which two
// concurrent detect calls complete (race regression).
const detectResolvers: Array<(payload: unknown) => void> = [];
const detectRejecters: Array<(err: Error) => void> = [];
const detectCalls: string[] = [];

// Confirm-side: the test re-points `confirmRevisionOf.mockImplementation`
// per-test (some tests reject with ApiError, default is no-op). Decouples
// detect-mock orchestration from confirm-mock orchestration. Wrapped in
// vi.hoisted so the function reference is available when vi.mock hoists
// to the top of the file.
const { confirmMock } = vi.hoisted(() => ({ confirmMock: vi.fn() }));

vi.mock('$lib/api', async () => {
	// Re-export the real `ApiError` class so tests can construct it AND
	// the component import sees the same class identity (instanceof works).
	const actual = await vi.importActual<typeof import('$lib/api')>('$lib/api');
	return {
		ApiError: actual.ApiError,
		detectRevisionOf: vi.fn((projectId: string) => {
			detectCalls.push(projectId);
			return new Promise((resolve, reject) => {
				detectResolvers.push(resolve);
				detectRejecters.push(reject);
			});
		}),
		confirmRevisionOf: confirmMock,
		// Cycle 5 W3-E (issue #84): handleSkip now calls skipRevisionOf
		// best-effort. No-op stub is safe — auto-collapse path doesn't
		// hit Skip button, and the inaugural skip-button test is left
		// to a follow-up.
		skipRevisionOf: vi.fn(async () => ({
			project_id: 'p',
			candidate_project_id: 'c',
			recorded: true,
		})),
	};
});

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
	confirmMock.mockReset();
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
		// DA exit-council PR #114 P1 #1+#3: pin BOTH the loading-hint
		// presence (proves runDetect() actually fired) AND that the mock
		// was hit (proves vi.mock alias resolution works). Without these,
		// the queryByRole(region)===null assertion can pass for the
		// wrong reason (e.g., $effect didn't fire OR the mock was no-op'd
		// and the real detectRevisionOf is hanging on a network call).
		expect(detectCalls).toEqual(['p-new']);
		expect(queryByRole('status')).not.toBeNull();
		expect(queryByRole('region')).toBeNull();

		// Resolve with a candidate payload.
		detectResolvers[0]!(happyPayload());

		// findByRole awaits the next render tick after $effect commits state.
		const region = await findByRole('region');
		expect(region.textContent).toContain('Project Alpha');
	});

	it('does NOT overwrite state when a stale detect resolves after a newer one (race regression)', async () => {
		// DA exit-council PR #114 P1 #2: this test pins ANY staleness-guard
		// mechanism (e.g., the current ``detectGen`` counter at lines
		// 87-117 of RevisionConfirmCard.svelte, OR a hypothetical
		// ``capturedProjectId`` closure check). It does NOT introspect
		// ``detectGen`` directly. A future refactor could replace the
		// counter with an equivalent guard and still pass this test —
		// that's by design (test pins behavior, not implementation).
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

		// Now resolve the STALE call. The staleness guard must reject this
		// resolution and leave the card showing "NEW Winner" — NOT
		// "STALE Loser". Use waitFor instead of magic Promise.resolve()
		// counts (DA P3 #9) — the assertion still holds for several ticks.
		detectResolvers[0]!(happyPayload({ candidate_project_name: 'STALE Loser' }));
		await waitFor(() => {
			expect(region.textContent).toContain('NEW Winner');
			expect(region.textContent).not.toContain('STALE Loser');
		});
	});

	it('auto-collapses the card and calls onSkipped when confirm fails with parent_not_found (issue #86)', async () => {
		// Issue #86 (Cycle 5 W3-D): structured error_code drives
		// auto-collapse on missing-project class errors. Asserts that the
		// component calls `onSkipped` (the parent's "treat as new project"
		// callback) and that the region disappears from the DOM after the
		// confirm rejection.
		const onSkipped = vi.fn();
		confirmMock.mockRejectedValueOnce(
			new ApiError('parent project xyz not found', 404, 'parent_not_found'),
		);

		const { findByRole, queryByRole } = render(RevisionConfirmCard, {
			props: { projectId: 'p-current', onSkipped },
		});
		// Resolve detect so the card renders with a candidate + confirm
		// button is enabled.
		detectResolvers[0]!(happyPayload());
		const region = await findByRole('region');
		const confirmButton = region.querySelector(
			'button:nth-of-type(2)',
		) as HTMLButtonElement | null;
		expect(confirmButton).not.toBeNull();
		await fireEvent.click(confirmButton!);

		await waitFor(() => {
			expect(onSkipped).toHaveBeenCalledTimes(1);
		});
		// Card collapsed.
		expect(queryByRole('region')).toBeNull();
	});

	it('renders nothing when detect returns no candidate', async () => {
		const { container, queryByRole } = render(RevisionConfirmCard, {
			props: { projectId: 'p-orphan' },
		});
		// DA exit-council PR #114 P2 #4: pin the loading→no-candidate
		// TRANSITION (was visible, then disappeared) rather than just the
		// terminal absence. Without this, waitFor(absence) could resolve
		// immediately if the loading hint never rendered (e.g., $effect
		// didn't fire). Pre-resolve assertion forces "loading hint WAS
		// here" before we test "and now it's not".
		expect(detectCalls).toEqual(['p-orphan']);
		expect(container.querySelector('[role="status"]')).not.toBeNull();

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
