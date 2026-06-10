import { writable, derived } from 'svelte/store';
import en from './en';
import ptBR from './pt-BR';
import es from './es';

export type Locale = 'en' | 'pt-BR' | 'es';

const translations: Record<Locale, Record<string, string>> = {
	en,
	'pt-BR': ptBR,
	es,
};

export const locale = writable<Locale>('en');

export const t = derived(locale, ($locale) => {
	const dict = translations[$locale] || translations.en;
	return (key: string, fallback?: string): string => {
		return dict[key] || translations.en[key] || fallback || key;
	};
});

/** Map an app locale to a BCP-47 tag for Intl date formatting.
 *  Best-effort tag validation only: on a runtime whose ICU lacks the locale
 *  data we return 'en-US' explicitly rather than relying on the engine's own
 *  silent fallback (toLocaleDateString does NOT throw on missing data — the
 *  try/catch covers only a hypothetical supportedLocalesOf failure). */
export function dateLocale(loc: Locale): string {
	const tag = loc === 'en' ? 'en-US' : loc;
	try {
		return Intl.DateTimeFormat.supportedLocalesOf(tag).length > 0 ? tag : 'en-US';
	} catch {
		return 'en-US';
	}
}

export function detectLocale(): Locale {
	if (typeof navigator === 'undefined') return 'en';
	const lang = navigator.language;
	if (lang.startsWith('pt')) return 'pt-BR';
	if (lang.startsWith('es')) return 'es';
	return 'en';
}

export const availableLocales: { code: Locale; label: string }[] = [
	{ code: 'en', label: 'English' },
	{ code: 'pt-BR', label: 'Portugues (BR)' },
	{ code: 'es', label: 'Espanol' },
];
