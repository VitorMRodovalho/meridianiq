import type {
	ProjectSummary,
	ProjectListResponse,
	ProjectDetailResponse,
	ValidationResponse,
	CriticalPathResponse,
	FloatDistributionResponse,
	MilestonesResponse,
	CompareResponse,
	TimelineDetailSchema,
	TimelineListResponse,
	DelayTrendResponse,
	TIAAnalysisSchema,
	TIAListResponse,
	DelayFragmentSchema,
	ContractCheckResponse,
	ContractProvisionsResponse,
	ScheduleHealthResponse,
	FloatTrendResponse,
	AlertsResponse,
	DashboardKPIs,
	ProgramTrends
} from './types';

import { supabase } from './supabase';
import { writable } from 'svelte/store';

const BASE = import.meta.env.VITE_API_URL || '';

/** True while the backend is waking up from cold start */
export const isWarmingUp = writable(false);

const MAX_RETRIES = 3;
const INITIAL_DELAY_MS = 1500;

async function sleep(ms: number): Promise<void> {
	return new Promise((r) => setTimeout(r, ms));
}

function isColdStartError(res: Response | null, err: unknown): boolean {
	// Fly.io returns 502 during cold start; browser sees as network/CORS error
	if (res && (res.status === 502 || res.status === 503)) return true;
	if (err instanceof TypeError && String(err.message).includes('fetch')) return true;
	return false;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
	// Get session directly from Supabase (reads localStorage, no store timing dependency)
	const { data: { session: currentSession } } = await supabase.auth.getSession();
	const token = currentSession?.access_token;
	const authHeaders: Record<string, string> = token
		? { Authorization: `Bearer ${token}` }
		: {};

	const mergedInit: RequestInit = {
		...init,
		headers: {
			...authHeaders,
			...(init?.headers as Record<string, string> | undefined)
		}
	};

	let lastError: unknown;
	for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
		let res: Response | null = null;
		try {
			res = await fetch(`${BASE}${url}`, mergedInit);
			if (res.ok) {
				isWarmingUp.set(false);
				return res.json();
			}
			if (!isColdStartError(res, null) || attempt === MAX_RETRIES) {
				const text = await res.text();
				throw new Error(text || `Request failed: ${res.status}`);
			}
		} catch (err) {
			if (!isColdStartError(res, err) || attempt === MAX_RETRIES) {
				throw err;
			}
			lastError = err;
		}
		// Cold start detected — retry with backoff
		isWarmingUp.set(true);
		await sleep(INITIAL_DELAY_MS * Math.pow(2, attempt));
	}
	throw lastError;
}

/**
 * Ping the backend health endpoint to wake it from cold start.
 * Returns true if backend is reachable, false otherwise.
 */
export async function warmUp(): Promise<boolean> {
	try {
		isWarmingUp.set(true);
		const res = await fetch(`${BASE}/health`);
		isWarmingUp.set(false);
		return res.ok;
	} catch {
		// Try once more after a delay
		await sleep(2000);
		try {
			const res = await fetch(`${BASE}/health`);
			isWarmingUp.set(false);
			return res.ok;
		} catch {
			isWarmingUp.set(false);
			return false;
		}
	}
}

export async function uploadXER(file: File): Promise<ProjectSummary> {
	const form = new FormData();
	form.append('file', file);
	return request<ProjectSummary>('/api/v1/upload', { method: 'POST', body: form });
}

export async function getProjects(): Promise<ProjectListResponse> {
	return request<ProjectListResponse>('/api/v1/projects');
}

// ── Programs (revision-grouped uploads) ─────────────────
export async function getPrograms(): Promise<{ programs: any[] }> {
	return request<{ programs: any[] }>('/api/v1/programs');
}

export async function getProgramDetail(id: string): Promise<{ program: any; revisions: any[] }> {
	return request<{ program: any; revisions: any[] }>(`/api/v1/programs/${id}`);
}

export async function updateProgram(id: string, body: { name?: string; description?: string }): Promise<{ program: any }> {
	return request<{ program: any }>(`/api/v1/programs/${id}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
}

export async function getProgramTrends(programId: string): Promise<ProgramTrends> {
	return request<ProgramTrends>(`/api/v1/programs/${programId}/trends`);
}

export async function getProject(id: string): Promise<ProjectDetailResponse> {
	return request<ProjectDetailResponse>(`/api/v1/projects/${id}`);
}

export async function getValidation(id: string): Promise<ValidationResponse> {
	return request<ValidationResponse>(`/api/v1/projects/${id}/validation`);
}

export async function getCriticalPath(id: string): Promise<CriticalPathResponse> {
	return request<CriticalPathResponse>(`/api/v1/projects/${id}/critical-path`);
}

export async function getFloatDistribution(id: string): Promise<FloatDistributionResponse> {
	return request<FloatDistributionResponse>(`/api/v1/projects/${id}/float-distribution`);
}

export async function getMilestones(id: string): Promise<MilestonesResponse> {
	return request<MilestonesResponse>(`/api/v1/projects/${id}/milestones`);
}

export async function compareSchedules(
	baselineId: string,
	updateId: string
): Promise<CompareResponse> {
	return request<CompareResponse>('/api/v1/compare', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ baseline_id: baselineId, update_id: updateId })
	});
}

// ── Forensic Analysis ─────────────────────────────────

export async function createTimeline(
	projectIds: string[]
): Promise<TimelineDetailSchema> {
	return request<TimelineDetailSchema>('/api/v1/forensic/create-timeline', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ project_ids: projectIds })
	});
}

export async function getTimelines(): Promise<TimelineListResponse> {
	return request<TimelineListResponse>('/api/v1/forensic/timelines');
}

export async function getTimeline(id: string): Promise<TimelineDetailSchema> {
	return request<TimelineDetailSchema>(`/api/v1/forensic/timelines/${id}`);
}

export async function getDelayTrend(id: string): Promise<DelayTrendResponse> {
	return request<DelayTrendResponse>(`/api/v1/forensic/timelines/${id}/delay-trend`);
}

// ── TIA (Time Impact Analysis) ─────────────────────────

export async function createTIAAnalysis(
	projectId: string,
	fragments: DelayFragmentSchema[]
): Promise<TIAAnalysisSchema> {
	return request<TIAAnalysisSchema>('/api/v1/tia/analyze', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ project_id: projectId, fragments })
	});
}

export async function getTIAAnalyses(): Promise<TIAListResponse> {
	return request<TIAListResponse>('/api/v1/tia/analyses');
}

export async function getTIAAnalysis(id: string): Promise<TIAAnalysisSchema> {
	return request<TIAAnalysisSchema>(`/api/v1/tia/analyses/${id}`);
}

export async function getTIASummary(id: string): Promise<TIAAnalysisSchema> {
	return request<TIAAnalysisSchema>(`/api/v1/tia/analyses/${id}/summary`);
}

// ── Contract Compliance ─────────────────────────────────

export async function contractCheck(analysisId: string): Promise<ContractCheckResponse> {
	return request<ContractCheckResponse>('/api/v1/contract/check', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ analysis_id: analysisId })
	});
}

export async function getContractProvisions(): Promise<ContractProvisionsResponse> {
	return request<ContractProvisionsResponse>('/api/v1/contract/provisions');
}

// ── Intelligence v0.8 ─────────────────────────────────

export async function getProjectHealth(
	id: string,
	baselineId?: string
): Promise<ScheduleHealthResponse> {
	const params = baselineId ? `?baseline_id=${baselineId}` : '';
	return request<ScheduleHealthResponse>(`/api/v1/projects/${id}/health${params}`);
}

export async function getFloatTrends(
	id: string,
	baselineId: string
): Promise<FloatTrendResponse> {
	return request<FloatTrendResponse>(
		`/api/v1/projects/${id}/float-trends?baseline_id=${baselineId}`
	);
}

export async function getProjectAlerts(
	id: string,
	baselineId: string
): Promise<AlertsResponse> {
	return request<AlertsResponse>(
		`/api/v1/projects/${id}/alerts?baseline_id=${baselineId}`
	);
}

export async function getDashboard(): Promise<DashboardKPIs> {
	return request<DashboardKPIs>('/api/v1/dashboard');
}

// ── PDF Reports ─────────────────────────────────────────

export async function generateReport(
	projectId: string,
	reportType: string,
	baselineId?: string
): Promise<{ report_id: string; report_type: string; project_id: string; generated_at: string }> {
	return request('/api/v1/reports/generate', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			project_id: projectId,
			report_type: reportType,
			baseline_id: baselineId || null,
			options: {}
		})
	});
}

// ── EVM (Earned Value Management) ─────────────────────────
export async function getEVMAnalyses(): Promise<{ analyses: any[] }> {
	return request<{ analyses: any[] }>('/api/v1/evm/analyses');
}

export async function createEVMAnalysis(projectId: string): Promise<any> {
	return request<any>(`/api/v1/evm/analyze/${projectId}`, { method: 'POST' });
}

export async function getEVMAnalysis(id: string): Promise<any> {
	return request<any>(`/api/v1/evm/analyses/${id}`);
}

// ── Risk (Monte Carlo QSRA) ────────────────────────────────
export async function getRiskSimulations(): Promise<{ simulations: any[] }> {
	return request<{ simulations: any[] }>('/api/v1/risk/simulations');
}

export async function createRiskSimulation(projectId: string, config: any): Promise<any> {
	return request<any>(`/api/v1/risk/simulate/${projectId}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(config)
	});
}

export async function getRiskSimulation(id: string): Promise<any> {
	return request<any>(`/api/v1/risk/simulations/${id}`);
}

// ── P3: Report Availability ──────────────────────────────

export interface ReportAvailabilityEntry {
	type: string;
	name: string;
	ready: boolean;
	reason: string;
}

export async function getAvailableReports(
	projectId: string
): Promise<{ project_id: string; reports: ReportAvailabilityEntry[] }> {
	return request<{ project_id: string; reports: ReportAvailabilityEntry[] }>(
		`/api/v1/projects/${projectId}/available-reports`
	);
}

// ── P4: Activity Search ──────────────────────────────────

export interface ActivitySearchEntry {
	task_code: string;
	task_name: string;
	task_type: string;
	wbs_id: string;
	status_code: string;
}

export async function searchActivities(
	projectId: string,
	q: string = '',
	limit: number = 20
): Promise<{ activities: ActivitySearchEntry[]; total: number }> {
	const params = new URLSearchParams({ limit: String(limit) });
	if (q) params.set('q', q);
	return request<{ activities: ActivitySearchEntry[]; total: number }>(
		`/api/v1/projects/${projectId}/activities?${params}`
	);
}

// ── Organizations ────────────────────────────────────────

export async function getOrganizations(): Promise<{ organizations: any[] }> {
	return request<{ organizations: any[] }>('/api/v1/organizations');
}

export async function createOrganization(name: string, orgType: string = 'general'): Promise<{ organization: any }> {
	return request<{ organization: any }>('/api/v1/organizations', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ name, org_type: orgType }),
	});
}

export async function getOrganization(orgId: string): Promise<{ organization: any; members: any[] }> {
	return request<{ organization: any; members: any[] }>(`/api/v1/organizations/${orgId}`);
}

export async function inviteMember(orgId: string, email: string, role: string = 'member'): Promise<any> {
	return request<any>(`/api/v1/organizations/${orgId}/invite`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ email, role }),
	});
}

export async function removeMember(orgId: string, userId: string): Promise<any> {
	return request<any>(`/api/v1/organizations/${orgId}/members/${userId}`, { method: 'DELETE' });
}

export async function shareProject(projectId: string, sharedWithOrgId: string, permission: string = 'viewer'): Promise<any> {
	return request<any>('/api/v1/shares/project', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ project_id: projectId, shared_with_org_id: sharedWithOrgId, permission }),
	});
}

export async function getProjectShares(projectId: string): Promise<{ shares: any[] }> {
	return request<{ shares: any[] }>(`/api/v1/shares/project/${projectId}`);
}

export async function getAuditLog(orgId: string, limit: number = 50): Promise<{ entries: any[] }> {
	return request<{ entries: any[] }>(`/api/v1/organizations/${orgId}/audit?limit=${limit}`);
}

// ── IPS Reconciliation ──────────────────────────────────

export async function reconcileIPS(masterProjectId: string, subProjectIds: string[]): Promise<any> {
	return request<any>('/api/v1/ips/reconcile', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ master_project_id: masterProjectId, sub_project_ids: subProjectIds }),
	});
}

// ── Recovery Validation ─────────────────────────────────

export async function validateRecovery(impactedProjectId: string, recoveryProjectId: string): Promise<any> {
	return request<any>('/api/v1/recovery/validate', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ impacted_project_id: impactedProjectId, recovery_project_id: recoveryProjectId }),
	});
}

// ── Value Milestones ────────────────────────────────────

export async function getValueMilestones(projectId: string): Promise<{ milestones: any[] }> {
	return request<{ milestones: any[] }>(`/api/v1/projects/${projectId}/value-milestones`);
}

export async function createValueMilestone(projectId: string, data: Record<string, unknown>): Promise<{ milestone: any }> {
	return request<{ milestone: any }>(`/api/v1/projects/${projectId}/value-milestones`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
	});
}

export async function updateValueMilestone(milestoneId: string, data: Record<string, unknown>): Promise<{ milestone: any }> {
	return request<{ milestone: any }>(`/api/v1/value-milestones/${milestoneId}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
	});
}

export async function exportExcel(projectId: string): Promise<Blob> {
	const { data: { session: currentSession } } = await supabase.auth.getSession();
	const token = currentSession?.access_token;
	const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

	const res = await fetch(`${BASE}/api/v1/projects/${projectId}/export/excel`, { headers });
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `Export failed: ${res.status}`);
	}
	return res.blob();
}

export async function downloadReport(reportId: string): Promise<Blob> {
	const { data: { session: currentSession } } = await supabase.auth.getSession();
	const token = currentSession?.access_token;
	const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

	const res = await fetch(`${BASE}/api/v1/reports/${reportId}/download`, { headers });
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `Download failed: ${res.status}`);
	}
	return res.blob();
}
