import { describe, it, expect } from 'vitest';
import { dateLocale } from './index';

describe('dateLocale — app locale → BCP-47 tag for Intl date formatting (#176)', () => {
	it('maps each app locale to its Intl tag', () => {
		expect(dateLocale('en')).toBe('en-US');
		expect(dateLocale('pt-BR')).toBe('pt-BR');
		expect(dateLocale('es')).toBe('es');
	});

	it('returned tags are actually supported by the runtime ICU (full-icu in Node/CI)', () => {
		for (const tag of [dateLocale('en'), dateLocale('pt-BR'), dateLocale('es')]) {
			expect(Intl.DateTimeFormat.supportedLocalesOf(tag)).toContain(tag);
		}
	});
});
