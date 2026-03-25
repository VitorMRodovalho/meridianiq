import type {
	ProjectSummary,
	ProjectListResponse,
	ProjectDetailResponse,
	ValidationResponse,
	CriticalPathResponse,
	FloatDistributionResponse,
	MilestonesResponse,
	CompareResponse
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
