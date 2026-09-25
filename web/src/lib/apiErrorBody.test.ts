// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
//
// parseErrorBody: every error body shape the API sends becomes a readable
// message, never the raw JSON dump.

import { describe, expect, it, vi } from 'vitest';

// api.ts creates the Supabase client at import; the parser does not need it.
vi.mock('./supabase', () => ({ supabase: {} }));

import { parseErrorBody } from './api';

describe('parseErrorBody', () => {
	it('uses the structured error code and message (issue #86)', () => {
		const body = JSON.stringify({ detail: { error_code: 'cap_reached', message: 'Too many' } });
		expect(parseErrorBody(409, body)).toEqual({ message: 'Too many', errorCode: 'cap_reached' });
	});

	it('uses a string detail', () => {
		expect(parseErrorBody(404, '{"detail":"Organization not found"}')).toEqual({
			message: 'Organization not found',
			errorCode: null
		});
	});

	it('joins Pydantic validation messages instead of dumping the body', () => {
		const body = JSON.stringify({
			detail: [
				{ type: 'string_pattern_mismatch', loc: ['body', 'email'], msg: 'String should match pattern' },
				{ type: 'too_long', loc: ['body', 'name'], msg: 'String should have at most 120 characters' }
			]
		});
		const { message, errorCode } = parseErrorBody(422, body);
		expect(message).toBe('String should match pattern; String should have at most 120 characters');
		expect(message).not.toContain('{');
		expect(errorCode).toBeNull();
	});

	it('reads the slowapi rate-limit body', () => {
		expect(parseErrorBody(429, '{"error":"Rate limit exceeded: 5 per 1 minute"}')).toEqual({
			message: 'Rate limit exceeded: 5 per 1 minute',
			errorCode: null
		});
	});

	it('keeps plain text and falls back to the status', () => {
		expect(parseErrorBody(502, 'Bad Gateway')).toEqual({ message: 'Bad Gateway', errorCode: null });
		expect(parseErrorBody(500, '')).toEqual({ message: 'Request failed: 500', errorCode: null });
	});

	it('keeps the body when a validation list has no messages', () => {
		expect(parseErrorBody(422, '{"detail":[{}]}').message).toBe('{"detail":[{}]}');
	});
});
