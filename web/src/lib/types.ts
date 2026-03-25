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

export interface ProjectDetailResponse {
	project_id: string;
	name: string;
	data_date: string | null;
	activities: ActivitySchema[];
	relationships: RelationshipSchema[];
}

export interface MetricSchema {
	number: number;
	name: string;
	description: string;
	value: number;
	threshold: number;
	unit: string;
	passed: boolean;
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
	changed_percentage: number;
	critical_path_changed: boolean;
	activities_joined_cp: string[];
	activities_left_cp: string[];
	summary: Record<string, unknown>;
}
