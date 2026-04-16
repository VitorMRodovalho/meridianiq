export interface WBSNode {
	wbs_id: string;
	name: string;
	short_name: string;
	depth: number;
	parent_id: string;
	activity_count: number;
	children: WBSNode[];
}

export interface ActivityView {
	task_id: string;
	task_code: string;
	task_name: string;
	wbs_id: string;
	wbs_path: string;
	indent_level: number;
	task_type: 'task' | 'milestone' | 'loe';
	status: 'complete' | 'active' | 'not_started';
	early_start: string;
	early_finish: string;
	late_start: string;
	late_finish: string;
	actual_start: string | null;
	actual_finish: string | null;
	baseline_start: string | null;
	baseline_finish: string | null;
	duration_days: number;
	remaining_days: number;
	total_float_days: number;
	free_float_days: number;
	progress_pct: number;
	is_critical: boolean;
	is_driving: boolean;
	calendar_id: string;
	constraint_type: string;
	constraint_date: string | null;
	start_variance_days: number | null;
	finish_variance_days: number | null;
	alerts: string[];
}

export interface RelationshipView {
	from_id: string;
	to_id: string;
	type: 'FS' | 'FF' | 'SS' | 'SF';
	lag_days: number;
	is_driving: boolean;
}

export interface WBSAggregate {
	start: string;
	finish: string;
	count: number;
	total_duration: number;
	min_float: number;
	weighted_progress: number;
	total_weight: number;
	critical_count: number;
	baseline_start: string | null;
	baseline_finish: string | null;
}

/** Shared flat row — single source of truth for WBSTree + GanttCanvas alignment. */
export interface FlatRow {
	type: 'wbs' | 'activity';
	activity?: ActivityView;
	wbsNode?: WBSNode;
	indent: number;
	wbsPath?: string;
}

export interface ScheduleViewData {
	project_name: string;
	data_date: string;
	project_start: string;
	project_finish: string;
	wbs_tree: WBSNode[];
	activities: ActivityView[];
	relationships: RelationshipView[];
	holidays?: string[];
	summary: {
		total_activities: number;
		critical_count: number;
		near_critical_count: number;
		complete_pct: number;
		negative_float_count: number;
		milestones_count: number;
		relationship_count: number;
		calendar_count: number;
		avg_float_days?: number;
		constraint_count?: number;
		loe_count?: number;
		complete_count?: number;
		active_count?: number;
		not_started_count?: number;
	};
}
