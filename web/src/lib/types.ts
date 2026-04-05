// TypeScript interfaces matching FastAPI response schemas

export interface HealthResponse {
	status: string;
	version: string;
}

export interface ProjectSummary {
	project_id: string;
	name: string;
	activity_count: number;
	relationship_count: number;
	calendar_count: number;
	wbs_count: number;
	data_date: string | null;
}

export interface ProjectListItem {
	project_id: string;
	name: string;
	activity_count: number;
	relationship_count: number;
}

export interface ProjectListResponse {
	projects: ProjectListItem[];
}

// ── Programs (revision-grouped uploads) ─────────────────

export interface ProgramRevision {
	id: string;
	filename: string;
	data_date: string | null;
	uploaded_at: string | null;
	revision_number: number;
	activity_count: number;
}

export interface ProgramListItem {
	id: string;
	name: string;
	description: string;
	proj_short_name: string;
	latest_revision: ProgramRevision | null;
	revision_count: number;
}

export interface ProgramListResponse {
	programs: ProgramListItem[];
}

export interface ActivitySchema {
	task_id: string;
	task_code: string;
	task_name: string;
	task_type: string;
	status_code: string;
	total_float_hr_cnt: number | null;
	remain_drtn_hr_cnt: number;
	target_drtn_hr_cnt: number;
	act_start_date: string | null;
	act_end_date: string | null;
	early_start_date: string | null;
	early_end_date: string | null;
	late_start_date: string | null;
	late_end_date: string | null;
}

export interface RelationshipSchema {
	task_id: string;
	pred_task_id: string;
	pred_type: string;
	lag_hr_cnt: number;
}

export interface WBSLevelCount {
	level: number;
	count: number;
}

export interface WBSStats {
	total_elements: number;
	max_depth: number;
	by_level: WBSLevelCount[];
	avg_activities_per_wbs: number;
	min_activities_per_wbs: number;
	max_activities_per_wbs: number;
	wbs_with_no_activities: number;
}

export interface ActivityStatusSummary {
	total: number;
	complete: number;
	in_progress: number;
	not_started: number;
}

export interface RelationshipTypeSummary {
	total: number;
	fs: number;
	ff: number;
	ss: number;
	sf: number;
}

export interface ProjectDetailResponse {
	project_id: string;
	name: string;
	data_date: string | null;
	activities: ActivitySchema[];
	relationships: RelationshipSchema[];
	wbs_stats: WBSStats | null;
	activity_summary: ActivityStatusSummary | null;
	relationship_summary: RelationshipTypeSummary | null;
}

export interface MetricSchema {
	number: number;
	name: string;
	description: string;
	value: number;
	threshold: number;
	unit: string;
	passed: boolean;
	direction: string;
	details: string;
}

export interface ValidationResponse {
	overall_score: number;
	passed_count: number;
	failed_count: number;
	activity_count: number;
	metrics: MetricSchema[];
}

export interface CriticalPathActivity {
	task_id: string;
	task_code: string;
	task_name: string;
	duration: number;
	early_start: number;
	early_finish: number;
	total_float: number;
}

export interface CriticalPathResponse {
	project_duration: number;
	critical_path: CriticalPathActivity[];
	has_cycles: boolean;
}

export interface FloatBucket {
	range_label: string;
	count: number;
	percentage: number;
}

export interface FloatDistributionResponse {
	total_activities: number;
	buckets: FloatBucket[];
}

export interface MilestoneSchema {
	task_id: string;
	task_code: string;
	task_name: string;
	task_type: string;
	status_code: string;
	act_start_date: string | null;
	act_end_date: string | null;
	early_start_date: string | null;
	early_end_date: string | null;
	target_start_date: string | null;
	target_end_date: string | null;
}

export interface MilestonesResponse {
	milestones: MilestoneSchema[];
}

export interface ActivityChangeSchema {
	task_id: string;
	task_name: string;
	change_type: string;
	old_value: string;
	new_value: string;
	severity: string;
}

export interface RelationshipChangeSchema {
	task_id: string;
	pred_task_id: string;
	change_type: string;
	old_value: string;
	new_value: string;
}

export interface FloatChangeSchema {
	task_id: string;
	task_name: string;
	old_float: number;
	new_float: number;
	delta: number;
	direction: string;
}

export interface ManipulationFlagSchema {
	task_id: string;
	task_name: string;
	indicator: string;
	description: string;
	severity: string;
	classification: string;
	score: number;
	rationale: string;
}

export interface CodeRestructuringSchema {
	task_id: string;
	old_code: string;
	new_code: string;
	activity_name: string;
}

export interface MatchStatsSchema {
	matched_by_task_id: number;
	matched_by_task_code: number;
	total_matched: number;
	added: number;
	deleted: number;
	code_restructured: number;
}

export interface CompareResponse {
	activities_added: ActivityChangeSchema[];
	activities_deleted: ActivityChangeSchema[];
	activity_modifications: ActivityChangeSchema[];
	duration_changes: ActivityChangeSchema[];
	relationships_added: RelationshipChangeSchema[];
	relationships_deleted: RelationshipChangeSchema[];
	relationships_modified: RelationshipChangeSchema[];
	significant_float_changes: FloatChangeSchema[];
	constraint_changes: ActivityChangeSchema[];
	manipulation_flags: ManipulationFlagSchema[];
	code_restructuring: CodeRestructuringSchema[];
	match_stats: MatchStatsSchema | null;
	changed_percentage: number;
	critical_path_changed: boolean;
	activities_joined_cp: string[];
	activities_left_cp: string[];
	manipulation_classification: string;
	manipulation_score: number;
	manipulation_rationale: string;
	summary: Record<string, unknown>;
}

// ── Forensic Analysis ─────────────────────────────────

export interface WindowSchema {
	window_number: number;
	window_id: string;
	baseline_project_id: string;
	update_project_id: string;
	start_date: string | null;
	end_date: string | null;
	completion_date_start: string | null;
	completion_date_end: string | null;
	delay_days: number;
	cumulative_delay: number;
	critical_path_start: string[];
	critical_path_end: string[];
	cp_activities_joined: string[];
	cp_activities_left: string[];
	driving_activity: string;
	comparison_summary: Record<string, unknown>;
	progress_delay_days: number | null;
	revision_delay_days: number | null;
	half_step_summary: Record<string, unknown> | null;
}

export interface HalfStepResponse {
	completion_a_days: number;
	completion_half_step_days: number;
	completion_b_days: number;
	progress_effect_days: number;
	revision_effect_days: number;
	total_delay_days: number;
	progress_direction: string;
	revision_direction: string;
	invariant_holds: boolean;
	activities_updated: number;
	critical_path_a: string[];
	critical_path_half_step: string[];
	critical_path_b: string[];
	classification_summary: Record<string, number>;
	summary: Record<string, unknown>;
}

export interface TimelineSummarySchema {
	timeline_id: string;
	project_name: string;
	schedule_count: number;
	total_delay_days: number;
	window_count: number;
}

export interface TimelineDetailSchema {
	timeline_id: string;
	project_name: string;
	schedule_count: number;
	total_delay_days: number;
	contract_completion: string | null;
	current_completion: string | null;
	windows: WindowSchema[];
	summary: Record<string, unknown>;
}

export interface TimelineListResponse {
	timelines: TimelineSummarySchema[];
}

export interface DelayTrendPoint {
	window_id: string;
	window_number: number;
	data_date: string | null;
	completion_date: string | null;
	delay_days: number;
	cumulative_delay: number;
}

export interface DelayTrendResponse {
	timeline_id: string;
	contract_completion: string | null;
	points: DelayTrendPoint[];
}

// ── TIA (Time Impact Analysis) ─────────────────────────

export interface FragmentRelationship {
	activity_code: string;
	lag_hours?: number;
	rel_type?: string;
	relationship_type?: string;
}

export interface FragmentActivitySchema {
	fragment_activity_id: string;
	name: string;
	duration_hours: number;
	predecessors: FragmentRelationship[];
	successors: FragmentRelationship[];
}

export interface DelayFragmentSchema {
	fragment_id: string;
	name: string;
	description: string;
	responsible_party: string;
	activities: FragmentActivitySchema[];
}

export interface TIAResultSchema {
	fragment_id: string;
	fragment_name: string;
	responsible_party: string;
	unimpacted_completion_days: number;
	impacted_completion_days: number;
	delay_days: number;
	critical_path_affected: boolean;
	float_consumed_hours: number;
	delay_type: string;
	concurrent_with: string[];
	impacted_driving_path: string[];
}

export interface TIAAnalysisSchema {
	analysis_id: string;
	project_name: string;
	base_project_id: string;
	fragments: DelayFragmentSchema[];
	results: TIAResultSchema[];
	total_owner_delay: number;
	total_contractor_delay: number;
	total_shared_delay: number;
	net_delay: number;
	summary: Record<string, unknown>;
}

export interface TIAAnalysisSummarySchema {
	analysis_id: string;
	project_name: string;
	fragment_count: number;
	net_delay: number;
	total_owner_delay: number;
	total_contractor_delay: number;
}

export interface TIAListResponse {
	analyses: TIAAnalysisSummarySchema[];
}

// ── Contract Compliance ─────────────────────────────────

export interface ComplianceCheckSchema {
	fragment_id: string;
	fragment_name: string;
	provision_id: string;
	provision_name: string;
	provision_category: string;
	status: string;
	finding: string;
	recommendation: string;
	details: Record<string, unknown>;
}

export interface ComplianceCheckSchema {
	fragment_id: string;
	fragment_name: string;
	provision_id: string;
	provision_name: string;
	provision_category: string;
	status: string;
	finding: string;
	recommendation: string;
	details: Record<string, unknown>;
}

export interface ContractCheckResponse {
	analysis_id: string;
	checks: ComplianceCheckSchema[];
	total_checks: number;
	warnings: number;
	failures: number;
}

export interface ContractProvisionSchema {
	provision_id: string;
	name: string;
	description: string;
	category: string;
	reference: string;
	threshold_days: number;
	details: string;
}

export interface ContractProvisionsResponse {
	provisions: ContractProvisionSchema[];
}

// ── Intelligence v0.8 ─────────────────────────────────

export interface ScheduleHealthResponse {
	overall: number;
	dcma_component: number;
	float_component: number;
	logic_component: number;
	trend_component: number;
	dcma_raw: number;
	float_raw: number;
	logic_raw: number;
	trend_raw: number;
	rating: string;
	trend_arrow: string;
	details: Record<string, unknown>;
}

export interface ActivityFloatTrendSchema {
	task_code: string;
	task_name: string;
	wbs_id: string;
	old_float_days: number;
	new_float_days: number;
	delta_days: number;
	direction: string;
	is_critical_baseline: boolean;
	is_critical_update: boolean;
	progress_pct: number;
}

export interface FloatTrendResponse {
	fei: number;
	near_critical_drift: number;
	cp_stability: number;
	activity_trends: ActivityFloatTrendSchema[];
	wbs_velocity: Record<string, number>;
	thresholds: Record<string, unknown>;
	days_between_updates: number;
	total_matched: number;
	summary: Record<string, unknown>;
}

export interface AlertSchema {
	rule_id: string;
	severity: string;
	title: string;
	description: string;
	affected_activities: string[];
	projected_impact_days: number;
	confidence: number;
	alert_score: number;
}

export interface AlertsResponse {
	alerts: AlertSchema[];
	total_alerts: number;
	critical_count: number;
	warning_count: number;
	info_count: number;
	aggregate_score: number;
	summary: Record<string, unknown>;
}

export interface DashboardKPIs {
	total_projects: number;
	active_alerts: number;
	avg_health_score: number;
	projects_trending_up: number;
	projects_trending_down: number;
	most_critical_project: string | null;
	most_critical_score: number | null;
}

// ── Program Trends ───────────────────────────────────────

export interface ProgramTrends {
	revision_count: number;
	labels: string[];
	health_scores: (number | null)[];
	dcma_scores: (number | null)[];
	alert_counts: (number | null)[];
	activity_counts: (number | null)[];
	revisions: { id: string; revision_number: number; data_date: string | null; filename: string }[];
}

// ── Reports ─────────────────────────────────────────────

export interface GenerateReportResponse {
	report_id: string;
	report_type: string;
	project_id: string;
	generated_at: string;
}
