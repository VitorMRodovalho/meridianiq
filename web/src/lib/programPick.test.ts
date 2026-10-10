import { describe, expect, it } from 'vitest';
import {
	decodeText,
	normaliseName,
	programNamed,
	readShortName,
	shortNameFromXer,
	shortNameFromXml,
	suggestProgram
} from './programPick';

const XER = [
	'ERMHDR\t22.0\t2026-01-01',
	'%T\tCALENDAR',
	'%F\tclndr_id\tclndr_name',
	'%R\tC1\tStandard',
	'%T\tPROJECT',
	'%F\tproj_id\tproj_short_name\tlast_recalc_date',
	'%R\tP1\tALPHA-UP12\t2026-05-01',
	'%R\tP2\tSECOND\t2026-05-01',
	'%T\tTASK'
].join('\r\n');

describe('shortNameFromXer', () => {
	it('reads the first project row by its column name', () => {
		expect(shortNameFromXer(XER)).toBe('ALPHA-UP12');
	});
	it('is null without a PROJECT table, or when the row is cut off', () => {
		expect(shortNameFromXer('%T\tTASK\n%F\ta\n%R\t1')).toBeNull();
		expect(shortNameFromXer('%T\tPROJECT\n%F\tproj_id\tproj_short_name')).toBeNull();
	});
	it('is null when the column is missing or blank', () => {
		expect(shortNameFromXer('%T\tPROJECT\n%F\tproj_id\n%R\tP1')).toBeNull();
		expect(shortNameFromXer('%T\tPROJECT\n%F\tproj_id\tproj_short_name\n%R\tP1\t  ')).toBeNull();
	});
});

describe('shortNameFromXml', () => {
	it('reads the project name or title', () => {
		expect(shortNameFromXml('<Project><Name>Beta 03</Name></Project>')).toBe('Beta 03');
		expect(shortNameFromXml('<Project><Title>Gamma</Title></Project>')).toBe('Gamma');
		expect(shortNameFromXml('<Project/>')).toBeNull();
	});
});

describe('decodeText', () => {
	it('reads UTF-8, and falls back to Windows-1252', () => {
		expect(decodeText(new TextEncoder().encode('Ação'))).toBe('Ação');
		expect(decodeText(new Uint8Array([0x41, 0xe7, 0xe3, 0x6f]))).toBe('Ação');
	});
	it('keeps UTF-8 when the slice ends inside a character', () => {
		const bytes = new TextEncoder().encode('Construção ã');
		expect(decodeText(bytes.slice(0, bytes.length - 1))).toBe('Construção ');
	});
});

describe('readShortName', () => {
	it('reads a file by its extension', async () => {
		expect(await readShortName(new File([XER], 'a.xer'))).toBe('ALPHA-UP12');
		expect(await readShortName(new File(['<Name>X Y</Name>'], 'a.XML'))).toBe('X Y');
		expect(await readShortName(new File(['garbage'], 'a.xer'))).toBeNull();
	});
});

describe('normaliseName', () => {
	it.each([
		['ALPHA-UP12', 'alpha'],
		['Alpha Rev 3', 'alpha'],
		['alpha_update_04', 'alpha'],
		['Alpha 2026-05', 'alpha'],
		['Alpha 2026-05-01', 'alpha'],
		['Alpha UP#7', 'alpha'],
		['North Tower', 'north tower'],
		['Tower 2 UP03', 'tower']
	])('%s → %s', (raw, want) => {
		expect(normaliseName(raw)).toBe(want);
	});
});

describe('suggestProgram', () => {
	const programs = [
		{ id: 'a', name: 'ALPHA-UP01' },
		{ id: 'b', name: 'Bravo North' },
		{ id: 'c', name: 'Bravo' }
	];
	it('matches across update numbers', () => {
		expect(suggestProgram('ALPHA-UP12', programs)?.program.id).toBe('a');
	});
	it('prefers an equal name over a longer shared start', () => {
		expect(suggestProgram('BRAVO UP2', programs)?.program.id).toBe('c');
	});
	it('accepts a long shared start', () => {
		expect(suggestProgram('Bravo Northside', programs)?.program.id).toBe('b');
	});
	it('says nothing when nothing resembles it', () => {
		expect(suggestProgram('Charlie', programs)).toBeNull();
		expect(suggestProgram('Alp', programs)).toBeNull();
		expect(suggestProgram(null, programs)).toBeNull();
		expect(suggestProgram('Alpha', [])).toBeNull();
	});
	it('names the program it matched, for the reason shown to the user', () => {
		expect(suggestProgram('ALPHA-UP12', programs)?.matched).toBe('ALPHA-UP01');
	});
});

describe('programNamed', () => {
	it('finds an existing name ignoring case and spaces', () => {
		const programs = [{ id: 'a', name: 'Alpha' }];
		expect(programNamed('  ALPHA ', programs)?.id).toBe('a');
		expect(programNamed('Alphabet', programs)).toBeNull();
		expect(programNamed('  ', programs)).toBeNull();
	});
});
