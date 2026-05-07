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
	ProgramTrends,
	HalfStepResponse,
	DelayPredictionResponse,
	BenchmarkCompareResponse,
	BenchmarkSummaryResponse,
	ScorecardResponse,
	WhatIfResponse,
	DurationAdjustment,
	ParetoResponse,
	LevelingResponse,
	GeneratedScheduleResponse,
	VisualizationResponse
} from './types';

import { supabase } from './supabase';
import { writable } from 'svelte/store';

const BASE = import.meta.env.VITE_API_URL || '';

/** True while the backend is waking up from cold start */
export const isWarmingUp = writable(false);

// Cold-start tolerance: Fly.io idle machines wake in 5-15s. Backoff sequence
// (attempt 0 immediate, then 1.5s · 2^N) gives total tolerance:
//   3 retries → ~10.5s   (often too short — user sees "Failed to fetch")
//   5 retries → ~46.5s   (covers worst-case Fly cold start + network blip)
// Bumped 3 → 5 alongside surface-errors fix on auth-gated pages so the user
// gets fewer false-negatives during cold start.
const MAX_RETRIES = 5;
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

export async function uploadXER(file: File, isSandbox: boolean = false): Promise<ProjectSummary> {
	const form = new FormData();
	form.append('file', file);
	form.append('is_sandbox', isSandbox ? 'true' : 'false');
	return request<ProjectSummary>('/api/v1/upload', { method: 'POST', body: form });
}

export async function getProjects(): Promise<ProjectListResponse> {
	return request<ProjectListResponse>('/api/v1/projects');
}

// Re-export commonly used schema types so consumer pages don't have to
// reach into `$lib/schemas` directly.
export type { ProjectSummary };

// ── Programs (revision-grouped uploads) ─────────────────

import type { ProgramListItem, ProgramListResponse, ProgramRevision } from '$lib/types';

export type { ProgramListItem, ProgramListResponse, ProgramRevision };

export interface ProgramDetail {
	program: ProgramListItem;
	revisions: ProgramRevision[];
}

export async function getPrograms(): Promise<ProgramListResponse> {
	return request<ProgramListResponse>('/api/v1/programs');
}

export async function getProgramDetail(id: string): Promise<ProgramDetail> {
	return request<ProgramDetail>(`/api/v1/programs/${id}`);
}

export async function updateProgram(
	id: string,
	body: { name?: string; description?: string }
): Promise<{ program: ProgramListItem }> {
	return request<{ program: ProgramListItem }>(`/api/v1/programs/${id}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
}

export async function getProgramTrends(programId: string): Promise<ProgramTrends> {
	return request<ProgramTrends>(`/api/v1/programs/${programId}/trends`);
}

export interface ProgramRollup {
	program_id: string;
	revision_count: number;
	latest_revision_id: string;
	latest_revision_number: number | null;
	latest_data_date: string | null;
	latest_metrics: {
		activity_count?: number;
		relationship_count?: number;
		revision_number?: number | null;
		data_date?: string | null;
		critical_path_length_days?: number;
		critical_activities_count?: number;
		has_cycles?: boolean;
		negative_float_count?: number;
		dcma_score?: number;
		dcma_passed_count?: number;
		dcma_failed_count?: number;
		health_score?: number;
		health_rating?: string;
		health_trend_arrow?: string;
	};
	trend_direction: 'improving' | 'stable' | 'degrading';
	trend_delta: number | null;
	previous_revision_id: string | null;
	previous_revision_number: number | null;
}

export async function getProgramRollup(programId: string): Promise<ProgramRollup> {
	return request<ProgramRollup>(`/api/v1/programs/${programId}/rollup`);
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

export async function runHalfStep(
	baselineId: string,
	updateId: string
): Promise<HalfStepResponse> {
	return request<HalfStepResponse>('/api/v1/forensic/half-step', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ baseline_id: baselineId, update_id: updateId })
	});
}

// ── Delay Prediction ─────────────────────────────────

export async function getDelayPrediction(
	projectId: string,
	baselineId?: string
): Promise<DelayPredictionResponse> {
	const params = baselineId ? `?baseline_id=${baselineId}` : '';
	return request<DelayPredictionResponse>(
		`/api/v1/projects/${projectId}/delay-prediction${params}`
	);
}

// ── Benchmarks ───────────────────────────────────────────

export async function compareBenchmarks(
	projectId: string,
	filterSize: boolean = true
): Promise<BenchmarkCompareResponse> {
	return request<BenchmarkCompareResponse>(
		`/api/v1/benchmarks/compare/${projectId}?filter_size=${filterSize}`
	);
}

export async function getBenchmarkSummary(): Promise<BenchmarkSummaryResponse> {
	return request<BenchmarkSummaryResponse>('/api/v1/benchmarks/summary');
}

export async function contributeBenchmark(projectId: string): Promise<unknown> {
	return request('/api/v1/benchmarks/contribute', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(projectId)
	});
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

// ── CBS Cost Snapshots ───────────────────────────────────

export interface CostSnapshotSummary {
	snapshot_id: string;
	project_id: string;
	user_id?: string | null;
	source_name: string;
	budget_date: string;
	total_budget: number;
	total_contingency: number;
	total_escalation: number;
	program_total: number;
	cbs_element_count: number;
	wbs_budget_count: number;
	mapping_count: number;
	insights: string[];
	created_at: string;
}

export async function getCostSnapshots(
	projectId: string
): Promise<{ project_id: string; count: number; snapshots: CostSnapshotSummary[] }> {
	return request(`/api/v1/projects/${projectId}/cost/snapshots`);
}

export interface CBSElementDelta {
	cbs_code: string;
	cbs_level1: string;
	cbs_level2: string;
	scope: string;
	budget_a: number;
	budget_b: number;
	estimate_a: number;
	estimate_b: number;
	contingency_a: number;
	contingency_b: number;
	budget_delta: number;
	estimate_delta: number;
	contingency_delta: number;
	variance_pct: number;
	status: 'changed' | 'unchanged' | 'added' | 'removed';
}

export interface CostCompareResult {
	project_id: string;
	snapshot_a: string;
	snapshot_b: string;
	total_budget_a: number;
	total_budget_b: number;
	total_budget_delta: number;
	total_contingency_a: number;
	total_contingency_b: number;
	total_contingency_delta: number;
	total_escalation_a: number;
	total_escalation_b: number;
	total_escalation_delta: number;
	program_total_a: number;
	program_total_b: number;
	program_total_delta: number;
	budget_variance_pct: number;
	element_deltas: CBSElementDelta[];
	added_count: number;
	removed_count: number;
	changed_count: number;
	unchanged_count: number;
	insights: string[];
}

export async function compareCostSnapshots(
	projectId: string,
	a: string,
	b: string
): Promise<CostCompareResult> {
	const params = new URLSearchParams({ a, b });
	return request<CostCompareResult>(
		`/api/v1/projects/${projectId}/cost/compare?${params}`
	);
}

// ── EVM (Earned Value Management) ─────────────────────────

export interface EVMSCurvePoint {
	date: string;
	cumulative_pv: number;
	cumulative_ev: number;
	cumulative_ac: number;
	pv?: number;
	ev?: number;
	ac?: number;
}

/** Summary row as returned by the analyses list — flat shape, gauges + coloured badges. */
export interface EVMAnalysisSummary {
	analysis_id: string;
	project_id?: string;
	project_name?: string;
	data_date?: string;
	bac: number;
	pv: number;
	ev: number;
	ac: number;
	eac: number;
	spi: number;
	cpi: number;
	schedule_health: 'good' | 'watch' | 'bad' | string;
	cost_health: 'good' | 'watch' | 'bad' | string;
	s_curve?: EVMSCurvePoint[];
}

/** Nested metrics object on the detail response. */
export interface EVMMetrics {
	bac: number;
	pv: number;
	ev: number;
	ac: number;
	eac: number;
	sv: number;
	cv: number;
	spi: number;
	cpi: number;
	etc?: number;
	vac?: number;
	tcpi?: number;
}

/** Health verdict with traffic-light status + human-readable label. */
export interface EVMHealthBadge {
	status: 'good' | 'watch' | 'bad' | string;
	label: string;
}

/** Forecast block on the detail response. */
export interface EVMForecast {
	eac_cpi: number;
	eac_combined: number;
	eac_etc_new: number;
	etc: number;
	vac: number;
	tcpi: number;
}

/** One WBS row on the detail response. */
export interface EVMWBSBreakdown {
	wbs_id?: string;
	wbs_name: string;
	metrics: EVMMetrics;
}

/** Detail response — nested shape from /evm/analyses/{id}. */
export interface EVMAnalysis {
	analysis_id: string;
	project_id?: string;
	project_name?: string;
	data_date?: string;
	metrics: EVMMetrics;
	schedule_health: EVMHealthBadge;
	cost_health: EVMHealthBadge;
	forecast: EVMForecast;
	s_curve?: EVMSCurvePoint[];
	wbs_breakdown?: EVMWBSBreakdown[];
	activities?: Array<{
		task_id: string;
		task_code?: string;
		task_name?: string;
		pv: number;
		ev: number;
		ac: number;
	}>;
	warnings?: string[];
	variance_narrative?: string;
	[k: string]: unknown;
}

export async function getEVMAnalyses(): Promise<{ analyses: EVMAnalysisSummary[] }> {
	return request<{ analyses: EVMAnalysisSummary[] }>('/api/v1/evm/analyses');
}

export async function createEVMAnalysis(projectId: string): Promise<EVMAnalysis> {
	return request<EVMAnalysis>(`/api/v1/evm/analyze/${projectId}`, { method: 'POST' });
}

export async function getEVMAnalysis(id: string): Promise<EVMAnalysis> {
	return request<EVMAnalysis>(`/api/v1/evm/analyses/${id}`);
}

// ── Demo ────────────────────────────────────────────────

export interface DemoDCMAMetric {
	number: number;
	name: string;
	value: number;
	threshold: number;
	unit: string;
	passed: boolean;
	direction: string;
}

export interface DemoCriticalPathActivity {
	task_code: string;
	task_name: string;
	total_float: number;
}

export interface DemoProjectResponse {
	project: {
		name: string;
		activity_count: number;
		relationship_count: number;
		calendar_count: number;
		wbs_count: number;
	};
	validation: {
		overall_score: number;
		passed_count: number;
		failed_count: number;
		metrics: DemoDCMAMetric[];
	};
	critical_path: {
		length: number;
		activities: DemoCriticalPathActivity[];
	};
}

// ── Risk (Monte Carlo QSRA) ────────────────────────────────

export interface RiskPValue {
	percentile: number;
	duration_days: number;
	delta_days: number;
}

export interface RiskHistogramBin {
	bin_start: number;
	bin_end: number;
	count: number;
	frequency: number;
}

export interface RiskCriticalityEntry {
	activity_id: string;
	activity_name: string;
	criticality_pct: number;
}

export interface RiskSensitivityEntry {
	activity_id: string;
	activity_name: string;
	correlation: number;
}

export interface RiskSCurvePoint {
	duration_days: number;
	cumulative_probability: number;
}

export interface RiskSimulationSummary {
	simulation_id: string;
	project_name: string;
	project_id: string;
	iterations: number;
	deterministic_days: number;
	mean_days: number;
	p50_days: number;
	p80_days: number;
}

export interface RiskSimulationResult {
	simulation_id: string;
	project_name: string;
	project_id: string;
	iterations: number;
	deterministic_days: number;
	mean_days: number;
	std_days: number;
	p_values: RiskPValue[];
	histogram: RiskHistogramBin[];
	criticality: RiskCriticalityEntry[];
	sensitivity: RiskSensitivityEntry[];
	s_curve: RiskSCurvePoint[];
}

export interface RiskSimulationRunConfig {
	config: {
		iterations: number;
		default_distribution: string;
		default_uncertainty: number;
		confidence_levels: number[];
		seed?: number;
	};
	duration_risks: unknown[];
	risk_events: unknown[];
}

export async function getRiskSimulations(): Promise<{ simulations: RiskSimulationSummary[] }> {
	return request<{ simulations: RiskSimulationSummary[] }>('/api/v1/risk/simulations');
}

export async function createRiskSimulation(
	projectId: string,
	config: RiskSimulationRunConfig,
	jobId?: string
): Promise<RiskSimulationResult> {
	const suffix = jobId ? `?job_id=${encodeURIComponent(jobId)}` : '';
	return request<RiskSimulationResult>(`/api/v1/risk/simulate/${projectId}${suffix}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(config)
	});
}

/**
 * ADR-0019 §"W1 — D4". Look up a completed risk simulation by its
 * progress channel job_id. Returns `simulation_id: null` while the
 * simulation is still running OR was never bound — the
 * `useWebSocketProgress` recovery poller polls until a non-null id
 * appears or the recovery window times out.
 */
export async function getRiskSimulationByJob(
	jobId: string
): Promise<{ simulation_id: string | null }> {
	return request<{ simulation_id: string | null }>(
		`/api/v1/risk/simulations/by-job/${encodeURIComponent(jobId)}`
	);
}

// ── Progress jobs (ADR-0013 server-generated job_id + ownership) ───────

export interface ProgressJobResponse {
	job_id: string;
	ws_url: string;
}

export async function startProgressJob(): Promise<ProgressJobResponse> {
	return request<ProgressJobResponse>('/api/v1/jobs/progress/start', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' }
	});
}

export async function getRiskSimulation(id: string): Promise<RiskSimulationResult> {
	return request<RiskSimulationResult>(`/api/v1/risk/simulations/${id}`);
}

export interface RegisterEntryMatched {
	activity: string;
	sensitivity: number | null;
	criticality_pct: number | null;
}

export interface LinkedRegisterEntry {
	risk_id: string;
	name: string;
	description?: string;
	category?: string;
	probability: number;
	impact_days: number;
	impact_cost?: number;
	status: string;
	responsible_party?: string;
	mitigation?: string;
	affected_activities: string[];
	matched_activities: RegisterEntryMatched[];
}

export interface SimulationRegisterLinkage {
	simulation_id: string;
	project_id: string;
	driver_activities: string[];
	entries: LinkedRegisterEntry[];
	total: number;
}

export async function getSimulationRegisterEntries(
	simulationId: string,
	topN: number = 15
): Promise<SimulationRegisterLinkage> {
	return request<SimulationRegisterLinkage>(
		`/api/v1/risk/simulations/${simulationId}/register-entries?top_n=${topN}`
	);
}

export async function getProjectRiskRegister(
	projectId: string
): Promise<{ project_id: string; entries: any[]; summary: any }> {
	return request(`/api/v1/projects/${projectId}/risk-register`);
}

export async function addRiskRegisterEntry(
	projectId: string,
	entry: Record<string, unknown>
): Promise<{ project_id: string; entry: Record<string, unknown> }> {
	return request(`/api/v1/projects/${projectId}/risk-register`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(entry)
	});
}

export async function deleteRiskRegisterEntry(
	projectId: string,
	riskId: string
): Promise<{ deleted: boolean }> {
	return request(`/api/v1/projects/${projectId}/risk-register/${riskId}`, {
		method: 'DELETE'
	});
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

export interface Organization {
	id: string;
	name: string;
	slug: string;
	org_type: string;
	description?: string;
	created_at?: string;
}

export interface OrganizationWithRole {
	id: string;
	name: string;
	slug: string;
	org_type: string;
	role: string;
}

export interface UserProfileSummary {
	id?: string;
	email?: string;
	full_name?: string;
	avatar_url?: string;
}

export interface OrgMember {
	user_id: string;
	role: string;
	accepted_at: string | null;
	user_profiles?: UserProfileSummary | null;
}

export interface AuditEntry {
	id?: string;
	created_at: string;
	action: string;
	entity_type: string;
	entity_id?: string | null;
	details?: Record<string, unknown>;
	ip_address?: string | null;
	user_agent?: string | null;
	user_profiles?: UserProfileSummary | null;
}

export interface ProjectShare {
	project_id: string;
	shared_with_org: string;
	permission: string;
	shared_by?: string;
	organizations?: { id: string; name: string; slug: string; org_type: string } | null;
}

export async function getOrganizations(): Promise<{ organizations: OrganizationWithRole[] }> {
	return request<{ organizations: OrganizationWithRole[] }>('/api/v1/organizations');
}

export async function createOrganization(
	name: string,
	orgType: string = 'general'
): Promise<{ organization: Organization }> {
	return request<{ organization: Organization }>('/api/v1/organizations', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ name, org_type: orgType })
	});
}

export async function getOrganization(
	orgId: string
): Promise<{ organization: Organization; members: OrgMember[] }> {
	return request<{ organization: Organization; members: OrgMember[] }>(
		`/api/v1/organizations/${orgId}`
	);
}

export async function inviteMember(
	orgId: string,
	email: string,
	role: string = 'member'
): Promise<{ status: string; email: string; role: string }> {
	return request<{ status: string; email: string; role: string }>(
		`/api/v1/organizations/${orgId}/invite`,
		{
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ email, role })
		}
	);
}

export async function removeMember(
	orgId: string,
	userId: string
): Promise<{ status: string }> {
	return request<{ status: string }>(`/api/v1/organizations/${orgId}/members/${userId}`, {
		method: 'DELETE'
	});
}

export async function shareProject(
	projectId: string,
	sharedWithOrgId: string,
	permission: string = 'viewer'
): Promise<{ status: string; permission: string }> {
	return request<{ status: string; permission: string }>('/api/v1/shares/project', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			project_id: projectId,
			shared_with_org_id: sharedWithOrgId,
			permission
		})
	});
}

export async function getProjectShares(
	projectId: string
): Promise<{ shares: ProjectShare[] }> {
	return request<{ shares: ProjectShare[] }>(`/api/v1/shares/project/${projectId}`);
}

export async function getAuditLog(
	orgId: string,
	limit: number = 50
): Promise<{ entries: AuditEntry[] }> {
	return request<{ entries: AuditEntry[] }>(
		`/api/v1/organizations/${orgId}/audit?limit=${limit}`
	);
}

// ── IPS Reconciliation ──────────────────────────────────

export interface ReconciliationIssue {
	severity: string;
	category: string;
	master_activity: string;
	sub_activity: string;
	sub_schedule: string;
	description: string;
	master_value: string;
	sub_value: string;
	delta: string;
}

export interface SubScheduleResult {
	sub_name: string;
	sub_activity_count: number;
	matched_milestones: number;
	unmatched_milestones: number;
	date_issues: number;
	logic_issues: number;
	issues: ReconciliationIssue[];
	alignment_score: number;
}

export interface IPSReconciliationResult {
	master_name: string;
	master_activity_count: number;
	sub_count: number;
	sub_results: SubScheduleResult[];
	total_issues: number;
	critical_issues: number;
	warning_issues: number;
	overall_alignment_score: number;
	reconciliation_status: string;
}

export async function reconcileIPS(
	masterProjectId: string,
	subProjectIds: string[]
): Promise<IPSReconciliationResult> {
	return request<IPSReconciliationResult>('/api/v1/ips/reconcile', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			master_project_id: masterProjectId,
			sub_project_ids: subProjectIds
		})
	});
}

// ── Recovery Validation ─────────────────────────────────

export interface RecoveryIssue {
	severity: string;
	category: string;
	task_code: string;
	task_name: string;
	description: string;
	impacted_value: string;
	recovery_value: string;
}

export interface RecoveryValidationResult {
	impacted_name: string;
	recovery_name: string;
	impacted_activity_count: number;
	recovery_activity_count: number;
	issues: RecoveryIssue[];
	critical_count: number;
	warning_count: number;
	total_duration_reduction_pct: number;
	activities_compressed: number;
	activities_added: number;
	activities_removed: number;
	zero_float_activities: number;
	validation_score: number;
	verdict: string;
}

export async function validateRecovery(
	impactedProjectId: string,
	recoveryProjectId: string
): Promise<RecoveryValidationResult> {
	return request<RecoveryValidationResult>('/api/v1/recovery/validate', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			impacted_project_id: impactedProjectId,
			recovery_project_id: recoveryProjectId
		})
	});
}

// ── Value Milestones ────────────────────────────────────

export interface ValueMilestone {
	id: string;
	project_id: string;
	org_id?: string | null;
	task_code: string;
	task_name: string;
	milestone_type: string;
	commercial_value: number;
	currency: string;
	payment_trigger: string;
	contract_ref: string;
	notes: string;
	baseline_date: string | null;
	forecast_date: string | null;
	actual_date: string | null;
	status: string | null;
	created_by?: string;
	created_at?: string;
	updated_at?: string;
}

export type ValueMilestoneCreate = Partial<Omit<ValueMilestone, 'id' | 'created_at' | 'updated_at'>> & {
	task_code: string;
	project_id: string;
};

export type ValueMilestoneUpdate = Partial<
	Pick<
		ValueMilestone,
		| 'commercial_value'
		| 'currency'
		| 'payment_trigger'
		| 'contract_ref'
		| 'notes'
		| 'baseline_date'
		| 'forecast_date'
		| 'actual_date'
		| 'status'
		| 'milestone_type'
	>
>;

export async function getValueMilestones(
	projectId: string
): Promise<{ milestones: ValueMilestone[] }> {
	return request<{ milestones: ValueMilestone[] }>(
		`/api/v1/projects/${projectId}/value-milestones`
	);
}

export async function createValueMilestone(
	projectId: string,
	data: ValueMilestoneCreate
): Promise<{ milestone: ValueMilestone }> {
	return request<{ milestone: ValueMilestone }>(
		`/api/v1/projects/${projectId}/value-milestones`,
		{
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(data)
		}
	);
}

export async function updateValueMilestone(
	milestoneId: string,
	data: ValueMilestoneUpdate
): Promise<{ milestone: ValueMilestone }> {
	return request<{ milestone: ValueMilestone }>(`/api/v1/value-milestones/${milestoneId}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
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

export async function exportJSON(projectId: string): Promise<Blob> {
	const { data: { session: currentSession } } = await supabase.auth.getSession();
	const token = currentSession?.access_token;
	const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

	const res = await fetch(`${BASE}/api/v1/projects/${projectId}/export/json`, { headers });
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `Export failed: ${res.status}`);
	}
	return res.blob();
}

export async function exportCSV(projectId: string, dataset: string = 'activities'): Promise<Blob> {
	const { data: { session: currentSession } } = await supabase.auth.getSession();
	const token = currentSession?.access_token;
	const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

	const res = await fetch(`${BASE}/api/v1/projects/${projectId}/export/csv?dataset=${dataset}`, { headers });
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

// ── v2.2+ Intelligence APIs ───────────────────────────────

export async function getScorecard(projectId: string): Promise<ScorecardResponse> {
	return request<ScorecardResponse>(`/api/v1/projects/${projectId}/scorecard`);
}

export async function runWhatIf(
	projectId: string,
	name: string,
	adjustments: DurationAdjustment[],
	iterations: number = 1
): Promise<WhatIfResponse> {
	return request<WhatIfResponse>(`/api/v1/projects/${projectId}/what-if`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ name, adjustments, iterations }),
	});
}

export async function runPareto(
	projectId: string,
	scenarios: { name: string; adjustments: DurationAdjustment[]; cost_delta: number }[],
	baseCost: number = 0
): Promise<ParetoResponse> {
	return request<ParetoResponse>(`/api/v1/projects/${projectId}/pareto`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ scenarios, base_cost: baseCost }),
	});
}

export async function runResourceLeveling(
	projectId: string,
	resourceLimits: { rsrc_id: string; max_units: number }[],
	priorityRule: string = 'late_start'
): Promise<LevelingResponse> {
	return request<LevelingResponse>(`/api/v1/projects/${projectId}/resource-leveling`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ resource_limits: resourceLimits, priority_rule: priorityRule }),
	});
}

export async function generateSchedule(
	projectType: string = 'commercial',
	sizeCategory: string = 'medium',
	projectName: string = 'Generated Project',
	targetDurationDays: number = 0
): Promise<GeneratedScheduleResponse> {
	return request<GeneratedScheduleResponse>(`/api/v1/schedule/generate`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			project_type: projectType,
			project_name: projectName,
			target_duration_days: targetDurationDays,
			size_category: sizeCategory,
		}),
	});
}

export async function getVisualization(projectId: string): Promise<VisualizationResponse> {
	return request<VisualizationResponse>(`/api/v1/projects/${projectId}/visualization`);
}

// ── Lifecycle phase (W3 of Cycle 1 v4.0 — ADR-0016) ──────

import type {
	LifecyclePhaseSummary,
	LifecycleOverrideRequest,
	LifecycleOverrideSchema,
	LifecycleOverrideListResponse,
	PendingStatusesResponse,
} from './types';

export type {
	LifecyclePhaseSummary,
	LifecycleOverrideRequest,
	LifecycleOverrideSchema,
	LifecycleOverrideListResponse,
	PendingStatusesResponse,
};

export async function getLifecycleSummary(projectId: string): Promise<LifecyclePhaseSummary> {
	return request<LifecyclePhaseSummary>(`/api/v1/projects/${projectId}/lifecycle`);
}

export async function postLifecycleOverride(
	projectId: string,
	body: LifecycleOverrideRequest
): Promise<LifecycleOverrideSchema> {
	return request<LifecycleOverrideSchema>(`/api/v1/projects/${projectId}/lifecycle/override`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	});
}

export async function deleteLifecycleOverride(projectId: string): Promise<void> {
	// 204 No Content — request<T>() expects JSON, so we hit fetch directly.
	const { data: { session } } = await supabase.auth.getSession();
	const token = session?.access_token;
	const headers: Record<string, string> = token
		? { Authorization: `Bearer ${token}` }
		: {};
	const res = await fetch(`${BASE}/api/v1/projects/${projectId}/lifecycle/override`, {
		method: 'DELETE',
		headers,
	});
	if (!res.ok) {
		const text = await res.text();
		throw new Error(text || `Revert failed: ${res.status}`);
	}
}

export async function getLifecycleOverrides(
	projectId: string,
	limit: number = 50
): Promise<LifecycleOverrideListResponse> {
	return request<LifecycleOverrideListResponse>(
		`/api/v1/projects/${projectId}/lifecycle/overrides?limit=${limit}`
	);
}

export async function getPendingStatuses(): Promise<PendingStatusesResponse> {
	return request<PendingStatusesResponse>(`/api/v1/projects/pending-statuses`);
}

// ── Cycle 4 W2 — revision detection (ADR-0022 + Amendment 2) ───

/**
 * Run the v1 heuristic to find a candidate parent revision for a project.
 *
 * Returns ``candidate_project_id: null`` when no sibling matches.
 * UI MUST NOT render ``confidence`` as a high-trust signal — see ADR-0022
 * Amendment 2 §"Calibration caveat".
 */
export async function detectRevisionOf(
	projectId: string
): Promise<import('./types').DetectRevisionOfResponse> {
	return request<import('./types').DetectRevisionOfResponse>(
		`/api/v1/projects/${projectId}/detect-revision-of`,
		{ method: 'POST' }
	);
}

/**
 * Append-only INSERT of a ``revision_history`` row anchoring the project as
 * a new revision in the parent's program. Server recomputes ``content_hash``
 * from the stored XER bytes — client does not need to send it.
 *
 * Throws on 4xx / 5xx with the server-provided detail message.
 */
export async function confirmRevisionOf(
	projectId: string,
	parentProjectId: string
): Promise<import('./types').ConfirmRevisionOfResponse> {
	return request<import('./types').ConfirmRevisionOfResponse>(
		`/api/v1/projects/${projectId}/confirm-revision-of`,
		{
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ parent_project_id: parentProjectId })
		}
	);
}

/**
 * Soft-tombstone a revision_history row + write paired audit_log entry.
 *
 * Idempotent — re-tombstone returns the existing tombstoned_at without
 * a new audit row.
 */
export async function tombstoneRevision(
	revisionId: string,
	reason: string
): Promise<import('./types').TombstoneRevisionResponse> {
	return request<import('./types').TombstoneRevisionResponse>(
		`/api/v1/revisions/${revisionId}/tombstone`,
		{
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ reason })
		}
	);
}
