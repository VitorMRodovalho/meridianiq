<script lang="ts">
	import { onMount, tick } from 'svelte';
	import {
		getAiAdmin,
		grantAiAccess,
		revokeAiAccess,
		approveAiRequest,
		dismissAiRequest,
		ApiError,
		type AiAccessRequestItem,
		type AiAdminConfig,
		type AiAdminSummary,
		type AiEntitlement,
		type AiMonthCalls
	} from '$lib/api';
	import { supabase } from '$lib/supabase';
	import { t, locale, dateLocale } from '$lib/i18n';
	import { formatNumber } from '$lib/i18n/format';
	import { interpolate } from '$lib/aiGate';
	import {
		AI_GRANT_MAX_DAILY_QUESTIONS,
		AI_GRANT_MAX_MONTHLY_USD,
		AI_GRANT_MONTHLY_MAX_DECIMALS,
		BUDGET_FORMAT,
		SPEND_FORMAT,
		accountLabel,
		formatUsd,
		grantLimitsValid,
		ledgerUnavailable,
		pendingRequests,
		pendingRequestsTotal
	} from '$lib/aiAdmin';

	// The first GET is the guard: nothing below the heading renders until it
	// answers 200, so a signed-out or non-superadmin visitor never sees the form.
	let phase: 'checking' | 'signed_out' | 'forbidden' | 'failed' | 'ready' = $state('checking');
	let summary: AiAdminSummary | null = $state(null);

	// Grant form
	let grantEmail = $state('');
	let grantDaily: number | null | undefined = $state(null);
	let grantMonthly: number | null | undefined = $state(null);
	let grantNote = $state('');
	let granting = $state(false);
	let grantError = $state('');
	let emailInput: HTMLInputElement | undefined = $state();

	// Revoke
	let revokingId = $state('');
	let revokeError = $state('');

	// The last grant or revoke that succeeded, announced by an always-mounted status region.
	let changeStatus = $state('');
	let listHeading: HTMLHeadingElement | undefined = $state();

	// Access requests: one approve or dismiss at a time, for every row.
	let requestActionId = $state('');
	let requestActionKind: 'approve' | 'dismiss' | '' = $state('');
	let requestError = $state('');
	// Announced by the section's always-mounted status region: a success, or
	// the informational "no longer pending".
	let requestNotice = $state('');
	let requestNoticeIsSuccess = $state(false);
	let requestsHeading: HTMLHeadingElement | undefined = $state();

	// Null means the requests could not be read, never "none".
	const requests = $derived(pendingRequests<AiAccessRequestItem>(summary));
	const requestsTotal = $derived(pendingRequestsTotal(summary));

	const configRows: { field: keyof AiAdminConfig; labelKey: string }[] = [
		{ field: 'enabled', labelKey: 'admin_ai.config_enabled' },
		{ field: 'api_key_set', labelKey: 'admin_ai.config_api_key_set' },
		{ field: 'model_set', labelKey: 'admin_ai.config_model_set' },
		{ field: 'prices_set', labelKey: 'admin_ai.config_prices_set' },
		{ field: 'global_budget_set', labelKey: 'admin_ai.config_global_budget_set' },
		{ field: 'sdk_available', labelKey: 'admin_ai.config_sdk_available' },
		{ field: 'durable_ledger', labelKey: 'admin_ai.config_durable_ledger' }
	];

	// The route still answers 200 when the usage ledger cannot be read, with the
	// config flags and zeros or empty values in every ledger field. Those zeros
	// were not measured, so they are shown as '—', never as $0 or 0 calls.
	const ledgerDown = $derived(ledgerUnavailable(summary));

	const callRows: { field: keyof AiMonthCalls; labelKey: string }[] = [
		{ field: 'completed', labelKey: 'admin_ai.calls_completed' },
		{ field: 'failed', labelKey: 'admin_ai.calls_failed' },
		{ field: 'unknown', labelKey: 'admin_ai.calls_unknown' },
		{ field: 'reserved', labelKey: 'admin_ai.calls_reserved' }
	];

	onMount(async () => {
		let signedIn = false;
		try {
			const {
				data: { session }
			} = await supabase.auth.getSession();
			signedIn = !!session;
		} catch {
			signedIn = false;
		}
		if (!signedIn) {
			phase = 'signed_out';
			return;
		}
		try {
			summary = await getAiAdmin();
			phase = 'ready';
		} catch (e: unknown) {
			phase = pageStateFor(e) ?? 'failed';
		}
	});

	/** The page-level state an auth failure moves to, or null for any other error. */
	function pageStateFor(e: unknown): 'signed_out' | 'forbidden' | null {
		if (e instanceof ApiError && e.status === 401) return 'signed_out';
		if (e instanceof ApiError && e.status === 403) return 'forbidden';
		return null;
	}

	/** Reload the summary; on failure keep the current one and report false. */
	async function refresh(): Promise<boolean> {
		try {
			summary = await getAiAdmin();
			return true;
		} catch {
			return false;
		}
	}

	/**
	 * True when a grant or revoke may have taken effect although no success came
	 * back: a timeout, a network error or a 5xx. Grant and revoke are single
	 * attempts, so the page reloads the list instead of guessing.
	 */
	function outcomeUnknown(e: unknown): boolean {
		return !(e instanceof ApiError) || e.status === 0 || e.status >= 500;
	}

	/** Reload the list, then say whether what is shown is current. */
	async function unknownOutcomeMessage(): Promise<string> {
		return (await refresh()) ? $t('admin_ai.outcome_unknown') : $t('admin_ai.outcome_unknown_stale');
	}

	function grantFailure(e: unknown): string {
		if (e instanceof ApiError) {
			if (e.errorCode === 'ai_account_not_found') return $t('admin_ai.account_not_found');
			// Limits are checked before sending (grantLimitsValid mirrors the API's
			// bounds), so a 422 is about the address.
			if (e.status === 422) return $t('org_detail.invite_invalid_email');
			if (e.status === 429) return $t('error.rate_limited');
		}
		return $t('admin_ai.grant_failed');
	}

	async function handleGrant(event: SubmitEvent) {
		event.preventDefault();
		const email = grantEmail.trim();
		if (!email || granting) return;
		grantError = '';
		changeStatus = '';
		revokeError = '';
		// An empty field means "use the default", sent as null.
		const daily = typeof grantDaily === 'number' ? grantDaily : null;
		const monthly = typeof grantMonthly === 'number' ? grantMonthly : null;
		if (!grantLimitsValid(daily, monthly)) {
			grantError = interpolate($t('admin_ai.invalid_limits'), {
				daily_max: whole(AI_GRANT_MAX_DAILY_QUESTIONS),
				monthly_max: whole(AI_GRANT_MAX_MONTHLY_USD),
				decimals: String(AI_GRANT_MONTHLY_MAX_DECIMALS)
			});
			return;
		}

		granting = true;
		let granted: AiEntitlement | null = null;
		try {
			granted = await grantAiAccess({
				email,
				daily_questions: daily,
				monthly_budget_usd: monthly,
				note: grantNote.trim() || null
			});
		} catch (e: unknown) {
			const state = pageStateFor(e);
			if (state) {
				phase = state;
				return;
			}
			if (outcomeUnknown(e)) {
				grantError = await unknownOutcomeMessage();
			} else {
				grantError = grantFailure(e);
			}
		} finally {
			granting = false;
		}

		if (granted) {
			if (!(await refresh()) && summary) {
				// The grant succeeded; show it even if the reload failed.
				const done = granted;
				summary = {
					...summary,
					entitlements: [done, ...summary.entitlements.filter((x) => x.user_id !== done.user_id)]
				};
			}
			changeStatus = interpolate($t('admin_ai.granted_done'), { email: granted.email || email });
			grantEmail = '';
			grantDaily = null;
			grantMonthly = null;
			grantNote = '';
			await tick();
			listHeading?.focus();
		} else {
			// The submit button was disabled while the request ran; give focus back
			// to the address so it can be corrected.
			await tick();
			emailInput?.focus();
		}
	}

	async function handleRevoke(ent: AiEntitlement) {
		if (revokingId) return;
		revokingId = ent.user_id;
		revokeError = '';
		grantError = '';
		changeStatus = '';
		let revoked = false;
		try {
			await revokeAiAccess(ent.user_id);
			revoked = true;
		} catch (e: unknown) {
			const state = pageStateFor(e);
			if (state) {
				phase = state;
				return;
			}
			if (e instanceof ApiError && e.errorCode === 'ai_entitlement_not_found') {
				revokeError = $t('admin_ai.revoke_not_found');
				await refresh();
			} else if (outcomeUnknown(e)) {
				revokeError = await unknownOutcomeMessage();
			} else if (e instanceof ApiError && e.status === 429) {
				revokeError = $t('error.rate_limited');
			} else {
				revokeError = $t('admin_ai.revoke_failed');
			}
		} finally {
			revokingId = '';
		}

		if (revoked) {
			if (!(await refresh()) && summary) {
				const now = new Date().toISOString();
				summary = {
					...summary,
					entitlements: summary.entitlements.map((x) =>
						x.user_id === ent.user_id ? { ...x, active: false, revoked_at: now } : x
					)
				};
			}
			changeStatus = interpolate($t('admin_ai.revoked_done'), { email: accountLabel(ent) });
		}
		// The row's button changed or went away: keep keyboard users in the list.
		await tick();
		listHeading?.focus();
	}

	/**
	 * Approve (default limits) or dismiss a pending request. Single attempt;
	 * every button in the list stays disabled until the list is reloaded, and
	 * focus then goes to the section heading, never to the next row.
	 */
	async function handleRequestAction(req: AiAccessRequestItem, kind: 'approve' | 'dismiss') {
		if (requestActionId) return;
		requestActionId = req.user_id;
		requestActionKind = kind;
		requestError = '';
		requestNotice = '';
		changeStatus = '';
		grantError = '';
		revokeError = '';
		const account = accountLabel(req);
		try {
			let done = false;
			let granted: AiEntitlement | null = null;
			try {
				if (kind === 'approve') granted = await approveAiRequest(req.user_id);
				else await dismissAiRequest(req.user_id);
				done = true;
			} catch (e: unknown) {
				const state = pageStateFor(e);
				if (state) {
					phase = state;
					return;
				}
				if (e instanceof ApiError && e.errorCode === 'ai_request_not_found') {
					// Approved, dismissed or withdrawn elsewhere: not an error.
					await refresh();
					requestNoticeIsSuccess = false;
					requestNotice = $t('admin_ai.request_not_found');
				} else if (outcomeUnknown(e)) {
					requestError = await unknownOutcomeMessage();
				} else if (e instanceof ApiError && e.status === 429) {
					requestError = $t('error.rate_limited');
				} else {
					requestError = $t(kind === 'approve' ? 'admin_ai.approve_failed' : 'admin_ai.dismiss_failed');
				}
			}

			if (done) {
				if (!(await refresh()) && summary) {
					// The change succeeded; show it even if the reload failed.
					const listed = summary.requests ?? null;
					const rest = listed ? listed.filter((r) => r.user_id !== req.user_id) : null;
					const removed = listed && rest ? listed.length - rest.length : 0;
					const total = summary.requests_total;
					const entitlement = granted;
					summary = {
						...summary,
						requests: rest,
						requests_total: typeof total === 'number' ? Math.max(0, total - removed) : total,
						entitlements: entitlement
							? [entitlement, ...summary.entitlements.filter((x) => x.user_id !== entitlement.user_id)]
							: summary.entitlements
					};
				}
				requestNoticeIsSuccess = true;
				requestNotice = interpolate(
					$t(kind === 'approve' ? 'admin_ai.approved_done' : 'admin_ai.dismissed_done'),
					{ account }
				);
			}
		} finally {
			requestActionId = '';
			requestActionKind = '';
		}
		// The row went away or changed: keep keyboard users at the top of the list.
		await tick();
		requestsHeading?.focus();
	}

	/** A budget (2 fraction digits). */
	function usd(value: string | null | undefined): string {
		return formatUsd(value, $locale, BUDGET_FORMAT);
	}

	/** Money spent or reserved (up to 4 fraction digits, so $0.004 is not $0.00). */
	function spent(value: string | null | undefined): string {
		return formatUsd(value, $locale, SPEND_FORMAT);
	}

	function whole(value: number | null | undefined): string {
		if (typeof value !== 'number') return '—';
		return formatNumber(value, $locale, { maximumFractionDigits: 0 });
	}

	function when(iso: string | null | undefined): string {
		if (!iso) return '—';
		const parsed = new Date(iso);
		if (Number.isNaN(parsed.getTime())) return '—';
		return parsed.toLocaleString(dateLocale($locale), { dateStyle: 'medium', timeStyle: 'short' });
	}

	function setText(ok: boolean): string {
		return ok ? $t('admin_ai.value_set') : $t('admin_ai.value_missing');
	}

	const inputClass =
		'mt-1 block w-full border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm';
	const cardClass = 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-5';
	const thClass = 'px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase whitespace-nowrap';
</script>

<svelte:head>
	<title>{$t('admin_ai.title')} - MeridianIQ</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<div class="mb-6">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{$t('admin_ai.title')}</h1>
		<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{$t('admin_ai.subtitle')}</p>
	</div>

	{#if phase === 'checking'}
		<div role="status" class="flex items-center gap-2 text-gray-500 dark:text-gray-400 py-12 justify-center">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			{$t('common.loading')}
		</div>
	{:else if phase === 'signed_out'}
		<div class="border border-gray-200 dark:border-gray-700 rounded-lg p-10 text-center bg-white dark:bg-gray-900">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{$t('admin_ai.signin_title')}</h2>			<p class="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">{$t('admin_ai.signin_body')}</p>
			<a
				href="/login"
				class="mt-6 inline-block bg-blue-600 text-white px-6 py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors"
			>
				{$t('common.sign_in')}
			</a>
		</div>
	{:else if phase === 'forbidden'}
		<div role="alert" class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-200 text-sm">
			{$t('admin_ai.forbidden')}
		</div>
	{:else if phase === 'failed' || !summary}
		<div role="alert" class="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-200 text-sm">
			{$t('admin_ai.load_failed')}
		</div>
	{:else}
		{#if ledgerDown}
			<div role="alert" class="p-4 mb-6 bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-lg text-amber-800 dark:text-amber-200 text-sm">
				{$t('admin_ai.ledger_unavailable')}
			</div>
		{/if}

		<section class="{cardClass} mb-6" aria-labelledby="ai-requests-title">
			<h2
				id="ai-requests-title"
				tabindex="-1"
				bind:this={requestsHeading}
				class="text-lg font-semibold text-gray-900 dark:text-gray-100 focus:outline-none"
			>
				{requestsTotal === null
					? $t('admin_ai.requests_heading')
					: interpolate($t('admin_ai.requests_heading_count'), { count: whole(requestsTotal) })}
			</h2>
			<!-- The status region stays mounted so its updates are announced. -->
			<div role="status">
				{#if requestNotice}
					<div
						class="mt-3 p-3 rounded-lg border text-sm {requestNoticeIsSuccess
							? 'bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800 text-green-700 dark:text-green-200'
							: 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200'}"
					>
						{requestNotice}
					</div>
				{/if}
			</div>
			{#if requestError}
				<div role="alert" class="mt-3 p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-200 text-sm">{requestError}</div>
			{/if}

			{#if requests === null}
				<p class="mt-3 p-3 bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-lg text-amber-800 dark:text-amber-200 text-sm">
					{$t('admin_ai.requests_unread')}
				</p>
			{:else if requests.length === 0}
				<p class="mt-2 text-sm text-gray-500 dark:text-gray-400">{$t('admin_ai.requests_empty')}</p>
			{:else}
				<p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
					{interpolate($t('admin_ai.requests_defaults'), {
						daily: whole(summary.defaults.daily_questions),
						monthly: usd(summary.defaults.account_monthly_budget_usd)
					})}
				</p>
				{#if requestsTotal !== null && requestsTotal > requests.length}
					<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
						{interpolate($t('admin_ai.requests_partial'), {
							shown: whole(requests.length),
							total: whole(requestsTotal)
						})}
					</p>
				{/if}
				<ul class="mt-4 space-y-3">
					{#each requests as req (req.user_id)}
						{@const account = accountLabel(req)}
						{@const approving = requestActionId === req.user_id && requestActionKind === 'approve'}
						{@const dismissing = requestActionId === req.user_id && requestActionKind === 'dismiss'}
						<li class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
							<p class="text-sm font-medium text-gray-900 dark:text-gray-100 break-all">{account}</p>
							<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
								{interpolate($t('admin_ai.request_requested'), { when: when(req.requested_at) })}
							</p>
							{#if req.note}
								<!-- The requester's own text: rendered as text, never as HTML. -->
								<p class="mt-2 text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words">{req.note}</p>
							{:else}
								<p class="mt-2 text-sm italic text-gray-500 dark:text-gray-400">{$t('admin_ai.request_no_note')}</p>
							{/if}
							<div class="mt-3 flex flex-col sm:flex-row gap-3">
								<button
									type="button"
									onclick={() => handleRequestAction(req, 'approve')}
									disabled={requestActionId !== ''}
									aria-label={approving ? undefined : interpolate($t('admin_ai.approve_aria'), { account })}
									class="min-h-11 px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 dark:bg-blue-600 text-white dark:text-white hover:bg-blue-700 dark:hover:bg-blue-500 disabled:opacity-50 transition-colors"
								>
									{approving ? $t('admin_ai.btn_approving') : $t('admin_ai.btn_approve')}
								</button>
								<button
									type="button"
									onclick={() => handleRequestAction(req, 'dismiss')}
									disabled={requestActionId !== ''}
									aria-label={dismissing ? undefined : interpolate($t('admin_ai.dismiss_aria'), { account })}
									class="min-h-11 px-4 py-2 rounded-lg text-sm font-medium border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
								>
									{dismissing ? $t('admin_ai.btn_dismissing') : $t('admin_ai.btn_dismiss')}
								</button>
							</div>
						</li>
					{/each}
				</ul>
			{/if}
		</section>

		<div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
			<section class={cardClass} aria-labelledby="ai-status-title">
				<h2 id="ai-status-title" class="text-base font-semibold text-gray-900 dark:text-gray-100">{$t('admin_ai.status_heading')}</h2>
				<dl class="mt-3 space-y-2 text-sm">
					<div class="flex justify-between gap-4">
						<dt class="text-gray-500 dark:text-gray-400">{$t('admin_ai.availability_label')}</dt>
						<dd class="font-medium {summary.available ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}">
							{summary.available ? $t('admin_ai.state_available') : $t('admin_ai.state_unavailable')}
						</dd>
					</div>
					{#if !summary.available}
						<div class="flex justify-between gap-4">
							<dt class="text-gray-500 dark:text-gray-400">{$t('admin_ai.reason_label')}</dt>
							<dd class="font-mono text-xs text-gray-900 dark:text-gray-100 break-all">{summary.reason ?? '—'}</dd>
						</div>
					{/if}
					<div class="flex justify-between gap-4">
						<dt class="text-gray-500 dark:text-gray-400">{$t('admin_ai.model_label')}</dt>
						<dd class="font-mono text-xs text-gray-900 dark:text-gray-100 break-all">{summary.model ?? $t('admin_ai.value_missing')}</dd>
					</div>
					<div class="flex justify-between gap-4">
						<dt class="text-gray-500 dark:text-gray-400">{$t('admin_ai.stale_reservations')}</dt>
						<dd class="font-medium text-gray-900 dark:text-gray-100">{ledgerDown ? '—' : whole(summary.stale_reservations)}</dd>
					</div>
					<div class="flex justify-between gap-4">
						<dt class="text-gray-500 dark:text-gray-400">{$t('admin_ai.last_failure')}</dt>
						<dd class="font-medium text-gray-900 dark:text-gray-100 text-right">
							{ledgerDown ? '—' : summary.last_failure_at ? when(summary.last_failure_at) : $t('admin_ai.last_failure_none')}
						</dd>
					</div>
				</dl>
				<p class="mt-2 text-xs text-gray-500 dark:text-gray-400">{$t('admin_ai.stale_hint')}</p>
			</section>

			<section class={cardClass} aria-labelledby="ai-config-title">
				<h2 id="ai-config-title" class="text-base font-semibold text-gray-900 dark:text-gray-100">{$t('admin_ai.config_heading')}</h2>
				<dl class="mt-3 space-y-2 text-sm">
					{#each configRows as row (row.field)}
						<div class="flex justify-between gap-4">
							<dt class="text-gray-500 dark:text-gray-400 break-words min-w-0">{$t(row.labelKey)}</dt>
							<dd class="shrink-0 font-medium {summary.config[row.field] ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}">
								{setText(summary.config[row.field])}
							</dd>
						</div>
					{/each}
				</dl>
			</section>

			<section class={cardClass} aria-labelledby="ai-spend-title">
				<h2 id="ai-spend-title" class="text-base font-semibold text-gray-900 dark:text-gray-100">{$t('admin_ai.spend_heading')}</h2>
				<dl class="mt-3 space-y-2 text-sm">
					<div class="flex justify-between gap-4">
						<dt class="text-gray-500 dark:text-gray-400">{$t('admin_ai.global_spent')}</dt>
						<dd class="font-medium text-gray-900 dark:text-gray-100">{ledgerDown ? '—' : spent(summary.global_spent_month_usd)}</dd>
					</div>
					<div class="flex justify-between gap-4">
						<dt class="text-gray-500 dark:text-gray-400">{$t('admin_ai.global_budget')}</dt>
						<dd class="font-medium text-gray-900 dark:text-gray-100">
							{summary.global_budget_usd === null ? $t('admin_ai.value_missing') : usd(summary.global_budget_usd)}
						</dd>
					</div>
					<div class="flex justify-between gap-4">
						<dt class="text-gray-500 dark:text-gray-400">{$t('admin_ai.reserve_per_question')}</dt>
						<dd class="font-medium text-gray-900 dark:text-gray-100">
							{summary.reserve_per_question_usd === null ? $t('admin_ai.value_missing') : spent(summary.reserve_per_question_usd)}
						</dd>
					</div>
				</dl>
				<h3 class="mt-4 text-sm font-semibold text-gray-900 dark:text-gray-100">{$t('admin_ai.calls_heading')}</h3>
				<dl class="mt-2 space-y-1 text-sm">
					{#each callRows as row (row.field)}
						<div class="flex justify-between gap-4">
							<dt class="text-gray-500 dark:text-gray-400">{$t(row.labelKey)}</dt>
							<dd class="font-medium text-gray-900 dark:text-gray-100">{ledgerDown ? '—' : whole(summary.month_calls?.[row.field])}</dd>
						</div>
					{/each}
				</dl>
			</section>

			<section class={cardClass} aria-labelledby="ai-defaults-title">
				<h2 id="ai-defaults-title" class="text-base font-semibold text-gray-900 dark:text-gray-100">{$t('admin_ai.defaults_heading')}</h2>
				<dl class="mt-3 space-y-2 text-sm">
					<div class="flex justify-between gap-4">
						<dt class="text-gray-500 dark:text-gray-400">{$t('admin_ai.default_daily')}</dt>
						<dd class="font-medium text-gray-900 dark:text-gray-100">{whole(summary.defaults.daily_questions)}</dd>
					</div>
					<div class="flex justify-between gap-4">
						<dt class="text-gray-500 dark:text-gray-400">{$t('admin_ai.default_monthly')}</dt>
						<dd class="font-medium text-gray-900 dark:text-gray-100">{usd(summary.defaults.account_monthly_budget_usd)}</dd>
					</div>
				</dl>
			</section>
		</div>

		<section class="{cardClass} mb-6" aria-labelledby="ai-grant-title">
			<h2 id="ai-grant-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100">{$t('admin_ai.grant_heading')}</h2>
			<p class="text-sm text-gray-500 dark:text-gray-400 mt-1 mb-4">{$t('admin_ai.grant_hint')}</p>
			{#if grantError}
				<div role="alert" class="p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-200 text-sm mb-4">{grantError}</div>
			{/if}
			<form novalidate onsubmit={handleGrant}>
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
					<label class="block sm:col-span-2">
						<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$t('org_detail.field_email')}</span>
						<input
							type="email"
							maxlength="320"
							autocomplete="off"
							bind:this={emailInput}
							bind:value={grantEmail}
							placeholder={$t('org_detail.placeholder_email')}
							class={inputClass}
						/>
					</label>
					<label class="block">
						<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$t('admin_ai.field_daily')}</span>
						<input
							type="number"
							min="0"
							max={AI_GRANT_MAX_DAILY_QUESTIONS}
							step="1"
							inputmode="numeric"
							bind:value={grantDaily}
							placeholder={interpolate($t('admin_ai.placeholder_default'), { value: whole(summary.defaults.daily_questions) })}
							class={inputClass}
						/>
					</label>
					<label class="block">
						<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$t('admin_ai.field_monthly')}</span>
						<input
							type="number"
							min="0"
							max={AI_GRANT_MAX_MONTHLY_USD}
							step="0.01"
							inputmode="decimal"
							bind:value={grantMonthly}
							placeholder={interpolate($t('admin_ai.placeholder_default'), { value: usd(summary.defaults.account_monthly_budget_usd) })}
							class={inputClass}
						/>
					</label>
					<label class="block sm:col-span-2">
						<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$t('admin_ai.field_note')}</span>
						<input type="text" maxlength="500" bind:value={grantNote} class={inputClass} />
					</label>
				</div>
				<button
					type="submit"
					disabled={granting || !grantEmail.trim()}
					class="px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
				>
					{granting ? $t('admin_ai.btn_granting') : $t('admin_ai.btn_grant')}
				</button>
			</form>
		</section>

		<section aria-labelledby="ai-list-title">
			<h2
				id="ai-list-title"
				tabindex="-1"
				bind:this={listHeading}
				class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3 focus:outline-none"
			>
				{$t('admin_ai.entitlements_heading')}
			</h2>
			<!-- The status region stays mounted so its updates are announced. -->
			<div role="status">
				{#if changeStatus}
					<div class="p-3 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg text-green-700 dark:text-green-200 text-sm mb-3">{changeStatus}</div>
				{/if}
			</div>
			{#if revokeError}
				<div role="alert" class="p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-200 text-sm mb-3">{revokeError}</div>
			{/if}

			{#if summary.entitlements.length === 0}
				<!-- With the ledger down the list is empty because it could not be read,
					 not because nobody was approved. -->
				<div class="{cardClass} text-center text-sm text-gray-500 dark:text-gray-400">
					{ledgerDown ? $t('admin_ai.ledger_unavailable_list') : $t('admin_ai.entitlements_empty')}
				</div>
			{:else}
				<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
						<thead class="bg-gray-50 dark:bg-gray-800">
							<tr>
								<th scope="col" class={thClass}>{$t('admin_ai.col_email')}</th>
								<th scope="col" class={thClass}>{$t('admin_ai.col_active')}</th>
								<th scope="col" class={thClass}>{$t('admin_ai.col_granted')}</th>
								<th scope="col" class={thClass}>{$t('admin_ai.col_daily_limit')}</th>
								<th scope="col" class={thClass}>{$t('admin_ai.col_monthly_budget')}</th>
								<th scope="col" class={thClass}>{$t('admin_ai.col_used_today')}</th>
								<th scope="col" class={thClass}>{$t('admin_ai.col_spent_month')}</th>
								<th scope="col" class={thClass}>{$t('admin_ai.col_note')}</th>
								<th scope="col" class={thClass}>{$t('admin_ai.col_action')}</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
							{#each summary.entitlements as ent (ent.user_id)}
								<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 whitespace-nowrap">
										{#if ent.email}{ent.email}{:else}<span class="font-mono text-xs">{ent.user_id}</span>{/if}
									</td>
									<td class="px-4 py-3 text-sm whitespace-nowrap">
										<span class="px-2 py-0.5 text-xs font-medium rounded-full {ent.active
											? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200'
											: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'}">
											{ent.active ? $t('admin_ai.state_active') : $t('admin_ai.state_revoked')}
										</span>
									</td>
									<td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">{when(ent.granted_at)}</td>
									<td class="px-4 py-3 text-sm text-gray-700 dark:text-gray-300 whitespace-nowrap">
										{ent.daily_questions === null
											? interpolate($t('admin_ai.default_value'), { value: whole(summary.defaults.daily_questions) })
											: whole(ent.daily_questions)}
									</td>
									<td class="px-4 py-3 text-sm text-gray-700 dark:text-gray-300 whitespace-nowrap">
										{ent.monthly_budget_usd === null
											? interpolate($t('admin_ai.default_value'), { value: usd(summary.defaults.account_monthly_budget_usd) })
											: usd(ent.monthly_budget_usd)}
									</td>
									<td class="px-4 py-3 text-sm text-gray-700 dark:text-gray-300 whitespace-nowrap">{whole(ent.used_today)}</td>
									<td class="px-4 py-3 text-sm text-gray-700 dark:text-gray-300 whitespace-nowrap">{spent(ent.spent_month_usd)}</td>
									<td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 max-w-xs break-words">{ent.note ?? '—'}</td>
									<td class="px-4 py-3 text-sm text-right whitespace-nowrap">
										{#if ent.active}
											<button
												type="button"
												onclick={() => handleRevoke(ent)}
												disabled={revokingId !== ''}
												aria-label={interpolate($t('admin_ai.revoke_aria'), { email: accountLabel(ent) })}
												class="text-xs font-medium text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 disabled:opacity-50"
											>
												{revokingId === ent.user_id ? $t('admin_ai.btn_revoking') : $t('admin_ai.btn_revoke')}
											</button>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>
	{/if}
</div>
