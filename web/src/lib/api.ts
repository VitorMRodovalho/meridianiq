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
	ContractProvisionsResponse
} from './types';

const BASE = '';

async function request<T>(url: string, init?: RequestInit): Promise<T> {
	const res = await fetch(`${BASE}${url}`, init);
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
