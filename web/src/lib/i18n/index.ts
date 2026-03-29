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
