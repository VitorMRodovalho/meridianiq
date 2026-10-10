// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import Harness from '$lib/__fixtures__/ProgramPickerHarness.svelte';

const programs = [
	{ id: 'p1', name: 'ALPHA-UP01' },
	{ id: 'p2', name: 'Bravo' }
];

function choice(): unknown {
	return JSON.parse(screen.getByTestId('choice').textContent || 'null');
}

afterEach(() => cleanup());

describe('ProgramPicker', () => {
	it('pre-selects the program the file name resembles', () => {
		render(Harness, { programs, shortName: 'ALPHA-UP12' });
		expect(choice()).toEqual({ programId: 'p1' });
		expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('p1');
	});

	it('offers a new program named after the file when nothing resembles it', () => {
		render(Harness, { programs, shortName: 'Charlie' });
		expect(choice()).toEqual({ newProgramName: 'Charlie' });
	});

	it('follows the user switching to an existing program', async () => {
		render(Harness, { programs, shortName: 'Charlie' });
		const [existing] = screen.getAllByRole('radio');
		await fireEvent.click(existing);
		const select = screen.getByRole('combobox') as HTMLSelectElement;
		await fireEvent.change(select, { target: { value: 'p2' } });
		expect(choice()).toEqual({ programId: 'p2' });
	});

	it('has no choice while the new name is blank', async () => {
		render(Harness, { programs: [], shortName: null });
		expect(choice()).toBeNull();
		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: '  New one ' } });
		expect(choice()).toEqual({ newProgramName: 'New one' });
	});

	it('warns when a new name is already a program, and can switch to it', async () => {
		render(Harness, { programs, shortName: 'Charlie' });
		const input = screen.getByRole('textbox');
		await fireEvent.input(input, { target: { value: 'bravo' } });
		const switchButton = screen.getByRole('button');
		await fireEvent.click(switchButton);
		expect(choice()).toEqual({ programId: 'p2' });
	});

	it('leaves out the program a schedule is moving from', () => {
		render(Harness, { programs, shortName: 'ALPHA-UP12', excludeId: 'p1' });
		expect(choice()).toEqual({ newProgramName: 'ALPHA-UP12' });
		expect(screen.queryByRole('option', { name: /ALPHA-UP01/ })).toBeNull();
	});

	it('offers nothing to choose while the program list loads', () => {
		render(Harness, { programs: [], shortName: 'ALPHA-UP12', loading: true });
		expect(choice()).toBeNull();
		expect(screen.queryAllByRole('radio')).toHaveLength(0);
	});

	it('says 1 revision, not 1 revisions', () => {
		render(Harness, { programs: [{ id: 'p', name: 'Solo', revision_count: 1 }], shortName: 'Solo' });
		expect(screen.getByRole('option').textContent).toMatch(/1 revision\b/);
	});
});
