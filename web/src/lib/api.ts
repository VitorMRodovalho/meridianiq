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

const BASE = import.meta.env.VITE_API_URL || '';

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

	const res = await fetch(`${BASE}${url}`, mergedInit);
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `Request failed: ${res.status}`);
	}
	return res.json();
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
