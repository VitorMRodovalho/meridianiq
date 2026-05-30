// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// i18n key-parity guard (W4 — ScheduleViewer hardening wave).
//
// `svelte-check` and the production build do NOT catch a missing/extra translation
// key: the runtime resolver (`src/lib/i18n/index.ts`) falls back silently to English
// (`dict[key] || en[key] || key`), so a locale that drops a key ships looking fine in
// dev and only breaks for pt-BR / es users in production. This test is the only gate
// that prevents that drift.
//
// It is a 3-WAY check: every locale's key set must equal the UNION of all locales'
// keys (no locale may be missing a key that any other declares — including a "phantom"
// key present in pt-BR+es but absent from en). It compares key SETS only, never VALUES
// — divergent values are intentional and out of scope (P6 codes like TF→FT/HT, proper
// nouns, acronyms). Keep this a parity guard, not a translation-quality linter.
//
// Known blind spots (acceptable by design): it cannot see a key DUPLICATED within one
// file (Object.keys dedupes — that is caught separately by the `npm run check` /
// svelte-check TS1117 step), and it does not verify that a key a component REFERENCES
// actually exists (a typo'd $t('...') renders the raw key via the index.ts fallback).

import { describe, expect, it } from 'vitest';
import en from './en';
import ptBR from './pt-BR';
import es from './es';

const locales: Record<string, Record<string, string>> = { en, 'pt-BR': ptBR, es };

// The union of every key declared in any locale. A fully-parity'd set of dictionaries
// has each locale's key set EQUAL to this union.
const union = new Set<string>();
for (const dict of Object.values(locales)) {
	for (const key of Object.keys(dict)) union.add(key);
}

describe('i18n key parity (3-way: en / pt-BR / es)', () => {
	it('declares a non-trivial number of keys', () => {
		expect(union.size).toBeGreaterThan(1000);
	});

	for (const [name, dict] of Object.entries(locales)) {
		it(`${name} declares every key that any locale declares`, () => {
			const keys = new Set(Object.keys(dict));
			// Keys some other locale has but this one is missing — the readable failure
			// lists the exact keys to add, instead of an opaque length mismatch.
			const missing = [...union].filter((key) => !keys.has(key)).sort();
			expect({ locale: name, missing }).toEqual({ locale: name, missing: [] });
		});
	}
});
