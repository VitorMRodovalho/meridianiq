// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// /admin/ai helpers: the grant limits stay inside the API's bounds (so a 422 can
// only be about the address), spend keeps fractions of a cent, and an account
// without a stored address is still named. Plus: every i18n key the page
// references exists in every locale.

import { describe, expect, it } from 'vitest';

import {
	AI_GRANT_MAX_DAILY_QUESTIONS,
	AI_GRANT_MAX_MONTHLY_USD,
	BUDGET_FORMAT,
	SPEND_FORMAT,
	accountLabel,
	formatUsd,
	grantLimitsValid,
	ledgerUnavailable
} from './aiAdmin';
import en from './i18n/en';
import ptBR from './i18n/pt-BR';
import es from './i18n/es';
// The page's source text, to find every key it references.
import pageSource from '../routes/admin/ai/+page.svelte?raw';

describe('grantLimitsValid', () => {
	it('accepts empty limits (the account uses the defaults)', () => {
		expect(grantLimitsValid(null, null)).toBe(true);
	});

	it('daily: whole numbers from 0 to the maximum', () => {
		expect(AI_GRANT_MAX_DAILY_QUESTIONS).toBe(10_000);
		expect(grantLimitsValid(0, null)).toBe(true);
		expect(grantLimitsValid(20, null)).toBe(true);
		expect(grantLimitsValid(10_000, null)).toBe(true);
		expect(grantLimitsValid(10_001, null)).toBe(false);
		expect(grantLimitsValid(-1, null)).toBe(false);
		expect(grantLimitsValid(1.5, null)).toBe(false);
		expect(grantLimitsValid(Number.NaN, null)).toBe(false);
		expect(grantLimitsValid(Number.POSITIVE_INFINITY, null)).toBe(false);
	});

	it('monthly: 0 to the maximum', () => {
		expect(AI_GRANT_MAX_MONTHLY_USD).toBe(100_000);
		expect(grantLimitsValid(null, 0)).toBe(true);
		expect(grantLimitsValid(null, 5)).toBe(true);
		expect(grantLimitsValid(null, 100_000)).toBe(true);
		expect(grantLimitsValid(null, 100_000.01)).toBe(false);
		expect(grantLimitsValid(null, 1e9)).toBe(false);
		expect(grantLimitsValid(null, -0.01)).toBe(false);
		expect(grantLimitsValid(null, Number.NaN)).toBe(false);
		expect(grantLimitsValid(null, Number.POSITIVE_INFINITY)).toBe(false);
	});

	it('monthly: at most 6 decimal places, including the exponent form below 1e-6', () => {
		expect(grantLimitsValid(null, 0.1)).toBe(true);
		expect(grantLimitsValid(null, 12.345678)).toBe(true);
		expect(grantLimitsValid(null, 0.000001)).toBe(true);
		expect(grantLimitsValid(null, 99_999.999999)).toBe(true);
		expect(grantLimitsValid(null, 12.3456789)).toBe(false);
		expect(grantLimitsValid(null, 0.0000001)).toBe(false); // String() gives "1e-7"
		expect(grantLimitsValid(null, 1.5e-7)).toBe(false);
	});

	it('one bad limit fails the pair', () => {
		expect(grantLimitsValid(10_001, 5)).toBe(false);
		expect(grantLimitsValid(20, 100_001)).toBe(false);
	});
});

describe('formatUsd', () => {
	it('spend keeps up to 4 fraction digits: 0.004 is not $0.00', () => {
		expect(formatUsd('0.004', 'en', SPEND_FORMAT)).toBe('$0.004');
		expect(formatUsd('0.0123', 'en', SPEND_FORMAT)).toBe('$0.0123');
		expect(formatUsd('5', 'en', SPEND_FORMAT)).toBe('$5.00');
		expect(formatUsd('1234.5', 'en', SPEND_FORMAT)).toBe('$1,234.50');
	});

	// Control: the budget format really does round a fraction of a cent away,
	// so the spend assertions above measure the difference between the two.
	it('control: budgets keep 2 digits, which would show 0.004 as $0.00', () => {
		expect(formatUsd('0.004', 'en', BUDGET_FORMAT)).toBe('$0.00');
		expect(formatUsd('5', 'en', BUDGET_FORMAT)).toBe('$5.00');
	});

	it('follows the locale', () => {
		expect(formatUsd('0.004', 'pt-BR', SPEND_FORMAT)).toContain('0,004');
	});

	it('shows a dash for missing or unreadable amounts, never $0', () => {
		for (const value of [null, undefined, '', '  ', 'abc']) {
			expect(formatUsd(value, 'en', SPEND_FORMAT)).toBe('—');
		}
	});
});

describe('ledgerUnavailable', () => {
	it('is true only for the ledger reason', () => {
		expect(ledgerUnavailable({ reason: 'ai_ledger_unavailable' })).toBe(true);
		for (const reason of [null, 'ai_disabled', 'ai_global_budget', 'ai_ledger']) {
			expect(ledgerUnavailable({ reason })).toBe(false);
		}
		expect(ledgerUnavailable(null)).toBe(false);
		expect(ledgerUnavailable(undefined)).toBe(false);
	});
});

describe('accountLabel', () => {
	it('uses the address, else the user id (never "null")', () => {
		expect(accountLabel({ email: 'a@example.com', user_id: 'u-1' })).toBe('a@example.com');
		expect(accountLabel({ email: null, user_id: 'u-1' })).toBe('u-1');
		expect(accountLabel({ email: '', user_id: 'u-1' })).toBe('u-1');
	});
});

describe('/admin/ai i18n keys', () => {
	// Every quoted string that looks like a key in the namespaces the page uses,
	// whether passed to $t() directly or through a labelKey table.
	const referenced = [
		...new Set(
			[...pageSource.matchAll(/'((?:admin_ai|common|error|org_detail)\.[a-z0-9_]+)'/g)].map((m) => m[1])
		)
	].sort();

	const added = [
		'admin_ai.availability_label',
		'admin_ai.last_failure',
		'admin_ai.last_failure_none',
		'admin_ai.ledger_unavailable',
		'admin_ai.ledger_unavailable_list',
		'admin_ai.reserve_per_question',
		'admin_ai.calls_heading',
		'admin_ai.calls_completed',
		'admin_ai.calls_failed',
		'admin_ai.calls_unknown',
		'admin_ai.calls_reserved',
		'admin_ai.outcome_unknown',
		'admin_ai.outcome_unknown_stale'
	];

	it('the scan sees the page, including the keys added for the report fields', () => {
		expect(referenced.length).toBeGreaterThan(40);
		for (const key of added) expect(referenced).toContain(key);
	});

	for (const [name, dict] of Object.entries({ en, 'pt-BR': ptBR, es })) {
		it(`every key the page references exists in ${name}`, () => {
			const missing = referenced.filter((key) => !(key in dict));
			expect({ locale: name, missing }).toEqual({ locale: name, missing: [] });
		});
	}

	it('the limits message names every bound it is given', () => {
		for (const dict of [en, ptBR, es]) {
			for (const slot of ['{daily_max}', '{monthly_max}', '{decimals}']) {
				expect(dict['admin_ai.invalid_limits']).toContain(slot);
			}
		}
	});
});
