<script lang="ts">
	// Cycle 4 W2 PR-B — revision confirmation card.
	//
	// INLINE card (NOT modal) below the upload result. Mounts after upload
	// completes, calls /detect-revision-of, conditionally renders if a
	// candidate parent is found. User confirms (writes revision_history row
	// via /confirm-revision-of) or skips (treats as new project).
	//
	// ## Calibration-honest framing (ADR-0022 Amendment 2)
	//
	// The backend returns a ``confidence`` float (0.9 saturated on exact name
	// match) but this UI does NOT render it as a high-trust signal. Framing
	// uses the i18n ``revision.confirm_card_help`` key: "Matched on project
	// name and program. Confirm to link as a new revision in this program
	// lineage, or skip to treat as a new project." — explicit and honest
	// about WHY the heuristic suggested this candidate, NOT a probability.
	//
	// ## Defensive contract
	//
	// - Detect failure → console.warn + don't render the card. Revision
	//   detection is OPT-IN feedback; it must not block the upload flow.
	// - Confirm failure (409 cap, 409 cross-program, 404, etc.) → toast
	//   error with the server-provided detail message; card stays visible
	//   so the user can retry or skip.
	// - Skip → no backend call, no toast, just dismiss.
	//
	// ## a11y
	//
	// ``role="region"`` + ``aria-labelledby`` on the card. Both action
	// buttons get ``aria-describedby`` pointing at the help text so screen
	// readers carry the context when focus lands on a button.
	//
	// ## Pattern reference
	//
	// Inline card shape mirrors ``LifecyclePhaseCard.svelte`` (status pill +
	// body + action row). Form pattern (props, $state, $derived, error
	// surfacing) mirrors ``LifecycleOverrideDialog.svelte``.

	import { ApiError, confirmRevisionOf, detectRevisionOf, skipRevisionOf } from '$lib/api';
	import { trackEvent } from '$lib/analytics';
	import { locale, t } from '$lib/i18n';
	import { formatDate } from '$lib/i18n/format';
	import { error as toastError, success } from '$lib/toast';

	interface Props {
		projectId: string;
		onConfirmed?: (revisionId: string, revisionNumber: number) => void;
		onSkipped?: () => void;
	}

	let { projectId, onConfirmed, onSkipped }: Props = $props();

	// Detect-state machine: ``loading`` → ``ready_with_candidate`` |
	// ``no_candidate`` | ``detect_failed`` | ``auth_expired``. The card
	// body renders on ``ready_with_candidate``; the loading hint renders
	// on ``loading``; ``auth_expired`` renders a hint to refresh; the
	// other terminal states collapse silently.
	let detectState = $state<
		| 'loading'
		| 'ready_with_candidate'
		| 'no_candidate'
		| 'detect_failed'
		| 'auth_expired'
	>('loading');
	let candidateProjectId = $state<string | null>(null);
	let candidateProjectName = $state<string | null>(null);
	let candidateDataDate = $state<string | null>(null);
	let candidateRevisionCount = $state<number>(0);

	// Confirm-state machine: ``idle`` → ``submitting`` → ``confirmed``
	// (terminal — card stays visible briefly then onConfirmed callback fires
	// the toast and parent dismisses).
	let confirmState = $state<'idle' | 'submitting' | 'confirmed'>('idle');
	let confirmError = $state<string | null>(null);

	let canConfirm = $derived(
		detectState === 'ready_with_candidate' && confirmState === 'idle'
	);

	// Generation counter (DA exit-council fix-up #P1-1) — increments on every
	// detect call. Stale promise resolutions check the generation before
	// committing state. Without this, a re-mount with a different projectId
	// could resolve the prior detect AFTER the new one has completed,
	// overwriting state with the wrong upload's candidate. Combined with
	// ``{#key result.project_id}`` in the parent (upload/+page.svelte), this
	// is belt-and-suspenders — the {#key} forces unmount+remount, and the
	// generation check catches the case if the parent ever drops the {#key}.
	let detectGen = 0;

	$effect(() => {
		// Run detection on (re)mount. ``$effect`` reruns on projectId change.
		// ``projectId`` is read here to subscribe to its rune; the body uses
		// the closure value via runDetect.
		void projectId;
		runDetect();
	});

	async function runDetect(): Promise<void> {
		const myGen = ++detectGen;
		detectState = 'loading';
		try {
			const res = await detectRevisionOf(projectId);
			if (myGen !== detectGen) {
				// Stale resolution — a newer detect for a different projectId
				// has started; do NOT commit this response's state.
				return;
			}
			if (res.candidate_project_id) {
				candidateProjectId = res.candidate_project_id;
				candidateProjectName = res.candidate_project_name;
				candidateDataDate = res.candidate_data_date;
				candidateRevisionCount = res.candidate_revision_count;
				detectState = 'ready_with_candidate';
			} else {
				detectState = 'no_candidate';
			}
		} catch (err) {
			if (myGen !== detectGen) return;
			const msg = err instanceof Error ? err.message : String(err);
			console.warn('detectRevisionOf failed:', err);
			trackEvent('revision_detect_failed', {
				project_id: projectId,
				error: msg
			});
			// DA exit-council fix-up #P1-3: distinguish auth-expired from
			// other transient failures. 401 typically surfaces in the error
			// message body. Auth-expired renders a hint instead of silently
			// collapsing — operator gets a path back via page refresh.
			if (/\b401\b|unauthori[sz]ed|token expired/i.test(msg)) {
				detectState = 'auth_expired';
			} else {
				detectState = 'detect_failed';
			}
		}
	}

	/**
	 * Single-pass placeholder interpolation that does NOT recursively
	 * interpret user-supplied values. ``str.replace('{x}', userValue)``
	 * is unsafe when ``userValue`` contains a ``{y}`` substring that the
	 * NEXT replace call would consume — corrupting the template (DA
	 * exit-council fix-up #P2-4). This regex-based single-pass treats
	 * ``{key}`` as a token boundary and substitutes from the values map
	 * once, leaving user-supplied ``{date}``-shaped substrings as
	 * literal text.
	 */
	function interpolate(template: string, values: Record<string, string>): string {
		return template.replace(/\{(\w+)\}/g, (match, key) =>
			Object.prototype.hasOwnProperty.call(values, key) ? values[key] : match
		);
	}

	async function handleConfirm(): Promise<void> {
		if (!canConfirm || !candidateProjectId) return;
		confirmError = null;
		confirmState = 'submitting';
		try {
			const res = await confirmRevisionOf(projectId, candidateProjectId);
			confirmState = 'confirmed';
			trackEvent('revision_confirmed', {
				project_id: projectId,
				parent_project_id: candidateProjectId,
				revision_number: res.revision_number
			});
			success(
				interpolate($t('revision.confirmed_toast'), {
					N: String(res.revision_number),
					name: candidateProjectName ?? ''
				})
			);
			onConfirmed?.(res.revision_id, res.revision_number);
		} catch (err) {
			// Issue #86 (Cycle 5 W3-D): structured error_code drives UX
			// branching. ``current_not_found`` / ``parent_not_found`` mean
			// the project moved or the candidate is stale — auto-collapse
			// the card (call onSkipped) so the user is not stuck staring
			// at an action they cannot complete. Other 4xx (cross_program,
			// cap_reached, no_xer_bytes, unique_collision, permission_denied)
			// keep the card visible with the human-readable message.
			//
			// DA exit-council on PR #83 fix-up #P1-2 used a fragile text
			// regex for cap-class detection — replaced here with the
			// machine-readable ``error_code``. Legacy string-detail
			// responses (errorCode === null) fall through to the message.
			const errorCode = err instanceof ApiError ? err.errorCode : null;
			const msg = err instanceof Error ? err.message : String(err);

			if (errorCode === 'current_not_found' || errorCode === 'parent_not_found') {
				trackEvent('revision_confirm_auto_collapsed', {
					project_id: projectId,
					candidate_project_id: candidateProjectId,
					error_code: errorCode
				});
				toastError($t(`revision.error_${errorCode}`));
				// Auto-collapse:
				// - Internal DOM: flip detectState to no_candidate so the
				//   card branch's {#if} collapses regardless of what the
				//   parent does. Defensive: prevents stuck "Linking…"
				//   button if the parent forgets to dismount us.
				// - Parent: call onSkipped so the parent updates lineage
				//   state (same terminal effect as the user clicking
				//   "Treat as new project").
				detectState = 'no_candidate';
				confirmState = 'idle';
				onSkipped?.();
				return;
			}

			const friendly =
				errorCode === 'cap_reached'
					? $t('revision.cap_reached')
					: errorCode === 'cross_program'
						? $t('revision.error_cross_program')
						: msg;
			confirmError = friendly;
			toastError(friendly);
			confirmState = 'idle';
		}
	}

	async function handleSkip(): Promise<void> {
		trackEvent('revision_skipped', {
			project_id: projectId,
			candidate_project_id: candidateProjectId
		});
		// Cycle 5 W3-E (issue #84): record the skip server-side so detect
		// stops surfacing this candidate. Reconsider via the project-detail
		// page's "Confirm as revision of..." action which calls
		// clear-revision-skips. Best-effort — if the skip-record call
		// fails (network blip), we still call onSkipped so the UI dismisses
		// the card; user can re-skip on next visit.
		if (candidateProjectId) {
			try {
				await skipRevisionOf(projectId, candidateProjectId);
			} catch (err) {
				console.warn('skipRevisionOf failed (best-effort):', err);
			}
		}
		onSkipped?.();
	}

	// Issue #85 (DA P3-2 from PR #83): legacy ``iso.slice(0, 10)`` returned
	// raw YYYY-MM-DD. Replaced with ``formatDate(iso, $locale)`` from
	// ``$lib/i18n/format`` — locale-aware (Apr 15, 2026 / 15 abr. 2026 /
	// 15 abr 2026 across en/pt-BR/es) with ``timeZone: 'UTC'`` enforced
	// for P6 data_date TZ-naive semantics. Called markup-side via
	// ``formatDate(candidateDataDate, $locale)`` so $locale reactivity
	// re-renders on locale switch.
</script>

{#if detectState === 'loading'}
	<!-- Loading hint — defends against silent slow paths (DA fix-up #P2-1) -->
	<p
		class="mt-4 text-xs text-gray-500 dark:text-gray-400 italic"
		role="status"
		aria-live="polite"
	>
		{$t('revision.checking')}
	</p>
{:else if detectState === 'auth_expired'}
	<!-- DA exit-council fix-up #P1-3: surface auth-expired explicitly -->
	<p
		class="mt-4 text-xs text-amber-700 dark:text-amber-300"
		role="status"
		aria-live="polite"
	>
		{$t('revision.auth_expired_hint')}
	</p>
{:else if detectState === 'ready_with_candidate' && confirmState !== 'confirmed'}
	<section
		aria-labelledby="revision-confirm-title"
		class="mt-4 rounded-lg border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/40 p-4"
	>
		<div class="flex flex-wrap items-start gap-3">
			<svg
				aria-hidden="true"
				class="w-5 h-5 mt-0.5 flex-none text-amber-600 dark:text-amber-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			<div class="min-w-0 flex-1">
				<h3
					id="revision-confirm-title"
					class="text-sm font-semibold text-amber-900 dark:text-amber-200"
				>
					{$t('revision.confirm_card_title')}
				</h3>
				<p
					id="revision-confirm-body"
					class="mt-1 text-sm text-amber-900/90 dark:text-amber-100/90"
				>
					{interpolate($t('revision.confirm_card_body'), {
						name: candidateProjectName ?? '—',
						date: formatDate(candidateDataDate, $locale),
						count: String(candidateRevisionCount)
					})}
				</p>
				<p
					id="revision-confirm-help"
					class="mt-2 text-xs text-amber-800/80 dark:text-amber-300/80"
				>
					{$t('revision.confirm_card_help')}
				</p>
				{#if confirmError}
					<p
						class="mt-2 text-xs text-rose-700 dark:text-rose-400"
						role="alert"
					>
						{confirmError}
					</p>
				{/if}
			</div>
		</div>

		<div class="mt-3 flex flex-wrap gap-2 justify-end">
			<button
				type="button"
				onclick={handleSkip}
				disabled={confirmState === 'submitting'}
				aria-describedby="revision-confirm-help"
				class="px-3 py-1.5 text-sm rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-amber-500"
			>
				{$t('revision.skip_button')}
			</button>
			<button
				type="button"
				onclick={handleConfirm}
				disabled={!canConfirm}
				aria-describedby="revision-confirm-help"
				class="px-3 py-1.5 text-sm rounded bg-amber-600 hover:bg-amber-700 text-white disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-amber-500"
			>
				{confirmState === 'submitting'
					? $t('revision.confirming')
					: $t('revision.confirm_button')}
			</button>
		</div>
	</section>
{/if}
