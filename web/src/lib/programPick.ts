// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// Choosing a schedule's program before it is uploaded: read the project's
// short name from the file in the browser, and suggest one of the user's
// programs. The suggestion is advisory; the user confirms or changes it.

/** Bytes read from the start of a file to find the project's name. */
export const NAME_SCAN_BYTES = 512 * 1024;

/** Decode bytes as UTF-8, falling back to Windows-1252 (P6's usual export). */
export function decodeText(bytes: Uint8Array): string {
	try {
		return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
	} catch {
		return new TextDecoder('windows-1252').decode(bytes);
	}
}

/** The first project's ``proj_short_name`` in XER text, or null. */
export function shortNameFromXer(text: string): string | null {
	const lines = text.split(/\r?\n/);
	let inProject = false;
	let fields: string[] | null = null;
	for (const line of lines) {
		const cells = line.split('\t');
		if (cells[0] === '%T') {
			if (inProject) return null;
			inProject = cells[1] === 'PROJECT';
			fields = null;
		} else if (inProject && cells[0] === '%F') {
			fields = cells.slice(1);
		} else if (inProject && fields && cells[0] === '%R') {
			const value = cells[1 + fields.indexOf('proj_short_name')];
			return fields.includes('proj_short_name') && value?.trim() ? value.trim() : null;
		}
	}
	return null;
}

/** The project title in Microsoft Project XML text, or null. */
export function shortNameFromXml(text: string): string | null {
	const match = /<(Name|Title)>([^<]{1,200})<\/\1>/.exec(text);
	return match ? match[2].trim() || null : null;
}

/** Read the project's short name from the start of an uploaded file. */
export async function readShortName(file: File): Promise<string | null> {
	try {
		const bytes = new Uint8Array(await file.slice(0, NAME_SCAN_BYTES).arrayBuffer());
		const text = decodeText(bytes);
		return file.name.toLowerCase().endsWith('.xml')
			? shortNameFromXml(text)
			: shortNameFromXer(text);
	} catch {
		return null;
	}
}

/**
 * A name reduced to what stays the same between updates of one schedule:
 * lower case, separators collapsed, and trailing update, revision or date
 * tokens removed ("ALPHA-UP12" and "Alpha Rev 3" both become "alpha").
 */
export function normaliseName(name: string): string {
	let s = name.toLowerCase().replace(/[_\-./\\]+/g, ' ').replace(/\s+/g, ' ').trim();
	const tail =
		/\s*(?:\b(?:up|upd|update|rev|revision|r|u|v|dd|data\s*date)\s*#?\s*\d+|\b\d{4}(?:\s\d{1,2}){0,2}|\b\d+)$/;
	for (let i = 0; i < 4 && tail.test(s); i++) s = s.replace(tail, '').trim();
	return s;
}

function commonPrefix(a: string, b: string): number {
	let i = 0;
	while (i < a.length && i < b.length && a[i] === b[i]) i++;
	return i;
}

export interface ProgramOption {
	id: string;
	name: string;
}

export interface Suggestion {
	program: ProgramOption;
	/** The program name the file's name resembles. */
	matched: string;
}

/** Shortest shared start that counts as a resemblance. */
export const MIN_SHARED = 4;
/** Share of the longer name the shared start must cover. */
export const MIN_RATIO = 0.6;

/**
 * The user's program whose name best resembles ``shortName``, or null.
 * Equal after normalising wins; otherwise the longest shared start, if it
 * is at least ``MIN_SHARED`` characters and ``MIN_RATIO`` of the longer name.
 */
export function suggestProgram(
	shortName: string | null,
	programs: ProgramOption[]
): Suggestion | null {
	if (!shortName) return null;
	const want = normaliseName(shortName);
	if (!want) return null;
	let best: { score: number; s: Suggestion } | null = null;
	for (const program of programs) {
		const have = normaliseName(program.name);
		if (!have) continue;
		let score: number;
		if (have === want) {
			score = 2;
		} else {
			const shared = commonPrefix(have, want);
			const ratio = shared / Math.max(have.length, want.length);
			if (shared < MIN_SHARED || ratio < MIN_RATIO) continue;
			score = ratio;
		}
		if (!best || score > best.score) {
			best = { score, s: { program, matched: program.name } };
		}
	}
	return best?.s ?? null;
}

/** The user's program with this exact name, ignoring case and outer spaces. */
export function programNamed(name: string, programs: ProgramOption[]): ProgramOption | null {
	const want = name.trim().toLowerCase();
	return want ? (programs.find((p) => p.name.trim().toLowerCase() === want) ?? null) : null;
}

/** What the picker hands to the API: one existing program or a new name. */
export type ProgramChoice = { programId: string } | { newProgramName: string };
