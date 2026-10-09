// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho

// /anomalies rendered from the anomalies endpoint's real payload. The fixture
// is produced by the backend engine and kept equal to it by
// tests/test_anomalies_contract.py, so a field renamed on either side fails a
// test instead of throwing in the browser (the page did that from 2026-04-05).

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/svelte';
import { get } from 'svelte/store';
import { t } from '$lib/i18n';
import payload from './__fixtures__/anomalies.sample_update.json';
import AnomaliesPage from '../routes/anomalies/+page.svelte';

vi.mock('$app/state', () => ({
	page: { url: new URL('http://localhost/anomalies?project=p1') }
}));

vi.mock('$lib/supabase', () => ({
	supabase: {
		auth: {
			getSession: vi.fn(async () => ({ data: { session: { access_token: 'token' } } }))
		}
	}
}));

vi.mock('$lib/api', () => ({
	getProjects: vi.fn(async () => ({
		projects: [{ project_id: 'p1', name: 'Synthetic project', activity_count: 9 }]
	}))
}));

const tr = (key: string) => get(t)(key);

/** The value shown above a KPI label. */
function kpi(labelKey: string): string {
	const label = screen.getByText(tr(labelKey));
	return label.previousElementSibling?.textContent?.trim() ?? '';
}

describe('/anomalies', () => {
	beforeEach(() => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }))
		);
	});

	afterEach(() => {
		cleanup();
		vi.unstubAllGlobals();
	});

	it('renders the endpoint payload loaded from ?project=', async () => {
		render(AnomaliesPage);

		const table = await screen.findByRole('table');
		expect(fetch).toHaveBeenCalledWith(
			expect.stringContaining('/api/v1/projects/p1/anomalies'),
			expect.anything()
		);

		expect(kpi('anomalies.kpi_activities_scanned')).toBe(String(payload.activities_analyzed));
		expect(kpi('anomalies.kpi_anomalies_found')).toBe(String(payload.total));
		expect(kpi('anomalies.kpi_high_severity')).toBe(String(payload.critical_count));
		const types = new Set(payload.anomalies.map((a) => a.anomaly_type));
		expect(kpi('anomalies.kpi_anomaly_types')).toBe(String(types.size));

		const rows = within(table).getAllByRole('row').slice(1);
		expect(rows).toHaveLength(payload.anomalies.length);
		for (const a of payload.anomalies) {
			expect(within(table).getAllByText(a.task_name).length).toBeGreaterThan(0);
		}
		expect(screen.queryByText(/Something went wrong/i)).toBeNull();
	});
});
