# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Pydantic request/response schemas for the FastAPI endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Health ───────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Response for GET /api/v1/health."""

    status: str = "ok"
    version: str = "0.4.0-dev"


# ── Upload ───────────────────────────────────────────────


class ProjectSummary(BaseModel):
    """Summary returned after uploading an XER file."""

    project_id: str
    name: str = ""
    activity_count: int = 0
    relationship_count: int = 0
    calendar_count: int = 0
    wbs_count: int = 0
    data_date: Optional[str] = None


# ── Project list ─────────────────────────────────────────


class ProjectListItem(BaseModel):
    """A single project in the list response."""

    project_id: str
    name: str = ""
    activity_count: int = 0
    relationship_count: int = 0


class ProjectListResponse(BaseModel):
    """Response for GET /api/v1/projects."""

    projects: list[ProjectListItem] = Field(default_factory=list)


# ── Detailed project ────────────────────────────────────


class ActivitySchema(BaseModel):
    """Serialisable representation of a Task/Activity."""

    task_id: str
    task_code: str = ""
    task_name: str = ""
    task_type: str = ""
    status_code: str = ""
    total_float_hr_cnt: Optional[float] = None
    remain_drtn_hr_cnt: float = 0.0
    target_drtn_hr_cnt: float = 0.0
    act_start_date: Optional[datetime] = None
    act_end_date: Optional[datetime] = None
    early_start_date: Optional[datetime] = None
    early_end_date: Optional[datetime] = None
    late_start_date: Optional[datetime] = None
    late_end_date: Optional[datetime] = None


class RelationshipSchema(BaseModel):
    """Serialisable representation of a Relationship."""

    task_id: str
    pred_task_id: str
    pred_type: str = "PR_FS"
    lag_hr_cnt: float = 0.0


class WBSLevelCount(BaseModel):
    """WBS elements at a specific hierarchy level."""

    level: int
    count: int


class WBSStats(BaseModel):
    """WBS hierarchy statistics for schedule assessment."""

    total_elements: int = 0
    max_depth: int = 0
    by_level: list[WBSLevelCount] = Field(default_factory=list)
    avg_activities_per_wbs: float = 0.0
    min_activities_per_wbs: int = 0
    max_activities_per_wbs: int = 0
    wbs_with_no_activities: int = 0


class ProjectDetailResponse(BaseModel):
    """Response for GET /api/v1/projects/{project_id}."""

    project_id: str
    name: str = ""
    data_date: Optional[str] = None
    activities: list[ActivitySchema] = Field(default_factory=list)
    relationships: list[RelationshipSchema] = Field(default_factory=list)
    wbs_stats: Optional[WBSStats] = None


# ── Validation (DCMA) ───────────────────────────────────


class MetricSchema(BaseModel):
    """A single DCMA metric result."""

    number: int
    name: str
    description: str
    value: float
    threshold: float
    unit: str = "%"
    passed: bool = True
    details: str = ""


class ValidationResponse(BaseModel):
    """Response for GET /api/v1/projects/{project_id}/validation."""

    overall_score: float = 0.0
    passed_count: int = 0
    failed_count: int = 0
    activity_count: int = 0
    metrics: list[MetricSchema] = Field(default_factory=list)


# ── Critical path ───────────────────────────────────────


class CriticalPathActivity(BaseModel):
    """An activity on the critical path."""

    task_id: str
    task_code: str = ""
    task_name: str = ""
    duration: float = 0.0
    early_start: float = 0.0
    early_finish: float = 0.0
    total_float: float = 0.0


class CriticalPathResponse(BaseModel):
    """Response for GET /api/v1/projects/{project_id}/critical-path."""

    project_duration: float = 0.0
    critical_path: list[CriticalPathActivity] = Field(default_factory=list)
    has_cycles: bool = False


# ── Float distribution ──────────────────────────────────


class FloatBucket(BaseModel):
    """A bucket of activities grouped by total float range."""

    range_label: str
    count: int
    percentage: float


class FloatDistributionResponse(BaseModel):
    """Response for GET /api/v1/projects/{project_id}/float-distribution."""

    total_activities: int = 0
    buckets: list[FloatBucket] = Field(default_factory=list)


# ── Milestones ──────────────────────────────────────────


class MilestoneSchema(BaseModel):
    """A milestone activity with its dates."""

    task_id: str
    task_code: str = ""
    task_name: str = ""
    task_type: str = ""
    status_code: str = ""
    act_start_date: Optional[datetime] = None
    act_end_date: Optional[datetime] = None
    early_start_date: Optional[datetime] = None
    early_end_date: Optional[datetime] = None
    target_start_date: Optional[datetime] = None
    target_end_date: Optional[datetime] = None


class MilestonesResponse(BaseModel):
    """Response for GET /api/v1/projects/{project_id}/milestones."""

    milestones: list[MilestoneSchema] = Field(default_factory=list)


# ── Comparison ──────────────────────────────────────────


class CompareRequest(BaseModel):
    """Request body for POST /api/v1/compare."""

    baseline_id: str
    update_id: str


class ActivityChangeSchema(BaseModel):
    """A single activity change."""

    task_id: str
    task_name: str
    change_type: str
    old_value: str = ""
    new_value: str = ""
    severity: str = "info"


class RelationshipChangeSchema(BaseModel):
    """A single relationship change."""

    task_id: str
    pred_task_id: str
    change_type: str
    old_value: str = ""
    new_value: str = ""


class FloatChangeSchema(BaseModel):
    """A significant float change."""

    task_id: str
    task_name: str
    old_float: float
    new_float: float
    delta: float
    direction: str


class ManipulationFlagSchema(BaseModel):
    """A manipulation indicator."""

    task_id: str
    task_name: str
    indicator: str
    description: str
    severity: str = "critical"


class CodeRestructuringSchema(BaseModel):
    """A detected activity code change between versions."""

    task_id: str
    old_code: str
    new_code: str
    activity_name: str


class MatchStatsSchema(BaseModel):
    """Statistics about how activities were matched."""

    matched_by_task_id: int = 0
    matched_by_task_code: int = 0
    total_matched: int = 0
    added: int = 0
    deleted: int = 0
    code_restructured: int = 0


class CompareResponse(BaseModel):
    """Response for POST /api/v1/compare."""

    activities_added: list[ActivityChangeSchema] = Field(default_factory=list)
    activities_deleted: list[ActivityChangeSchema] = Field(default_factory=list)
    activity_modifications: list[ActivityChangeSchema] = Field(default_factory=list)
    duration_changes: list[ActivityChangeSchema] = Field(default_factory=list)
    relationships_added: list[RelationshipChangeSchema] = Field(default_factory=list)
    relationships_deleted: list[RelationshipChangeSchema] = Field(default_factory=list)
    relationships_modified: list[RelationshipChangeSchema] = Field(default_factory=list)
    significant_float_changes: list[FloatChangeSchema] = Field(default_factory=list)
    constraint_changes: list[ActivityChangeSchema] = Field(default_factory=list)
    manipulation_flags: list[ManipulationFlagSchema] = Field(default_factory=list)
    code_restructuring: list[CodeRestructuringSchema] = Field(default_factory=list)
    match_stats: Optional[MatchStatsSchema] = None
    changed_percentage: float = 0.0
    critical_path_changed: bool = False
    activities_joined_cp: list[str] = Field(default_factory=list)
    activities_left_cp: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


# ── Forensic Analysis ─────────────────────────────────


class CreateTimelineRequest(BaseModel):
    """Request body for POST /api/v1/forensic/create-timeline."""

    project_ids: list[str] = Field(
        ..., min_length=2, description="At least 2 project IDs sorted by data date"
    )


class WindowSchema(BaseModel):
    """A single analysis window in the forensic timeline."""

    window_number: int
    window_id: str
    baseline_project_id: str = ""
    update_project_id: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    completion_date_start: Optional[str] = None
    completion_date_end: Optional[str] = None
    delay_days: float = 0.0
    cumulative_delay: float = 0.0
    critical_path_start: list[str] = Field(default_factory=list)
    critical_path_end: list[str] = Field(default_factory=list)
    cp_activities_joined: list[str] = Field(default_factory=list)
    cp_activities_left: list[str] = Field(default_factory=list)
    driving_activity: str = ""
    comparison_summary: dict[str, Any] = Field(default_factory=dict)


class TimelineSummarySchema(BaseModel):
    """Summary of a forensic timeline (used in list responses)."""

    timeline_id: str
    project_name: str = ""
    schedule_count: int = 0
    total_delay_days: float = 0.0
    window_count: int = 0


class TimelineDetailSchema(BaseModel):
    """Full forensic timeline with all window results."""

    timeline_id: str
    project_name: str = ""
    schedule_count: int = 0
    total_delay_days: float = 0.0
    contract_completion: Optional[str] = None
    current_completion: Optional[str] = None
    windows: list[WindowSchema] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class TimelineListResponse(BaseModel):
    """Response for GET /api/v1/forensic/timelines."""

    timelines: list[TimelineSummarySchema] = Field(default_factory=list)


class DelayTrendPoint(BaseModel):
    """A single point on the delay trend chart."""

    window_id: str
    window_number: int
    data_date: Optional[str] = None
    completion_date: Optional[str] = None
    delay_days: float = 0.0
    cumulative_delay: float = 0.0


class DelayTrendResponse(BaseModel):
    """Response for GET /api/v1/forensic/timelines/{id}/delay-trend."""

    timeline_id: str
    contract_completion: Optional[str] = None
    points: list[DelayTrendPoint] = Field(default_factory=list)


# ── TIA (Time Impact Analysis) ──────────────────────────


class FragmentActivitySchema(BaseModel):
    """A single activity within a delay fragment."""

    fragment_activity_id: str
    name: str
    duration_hours: float = 0.0
    predecessors: list[dict[str, Any]] = Field(default_factory=list)
    successors: list[dict[str, Any]] = Field(default_factory=list)


class DelayFragmentSchema(BaseModel):
    """A delay fragment definition for TIA."""

    fragment_id: str
    name: str
    description: str = ""
    responsible_party: str = "contractor"
    activities: list[FragmentActivitySchema] = Field(default_factory=list)


class TIAAnalyzeRequest(BaseModel):
    """Request body for POST /api/v1/tia/analyze."""

    project_id: str
    fragments: list[DelayFragmentSchema] = Field(
        ..., min_length=1, description="At least 1 delay fragment"
    )


class TIAResultSchema(BaseModel):
    """Result of analyzing a single delay fragment."""

    fragment_id: str
    fragment_name: str
    responsible_party: str = ""
    unimpacted_completion_days: float = 0.0
    impacted_completion_days: float = 0.0
    delay_days: float = 0.0
    critical_path_affected: bool = False
    float_consumed_hours: float = 0.0
    delay_type: str = ""
    concurrent_with: list[str] = Field(default_factory=list)
    impacted_driving_path: list[str] = Field(default_factory=list)


class TIAAnalysisSchema(BaseModel):
    """Full TIA analysis response."""

    analysis_id: str
    project_name: str = ""
    base_project_id: str = ""
    fragments: list[DelayFragmentSchema] = Field(default_factory=list)
    results: list[TIAResultSchema] = Field(default_factory=list)
    total_owner_delay: float = 0.0
    total_contractor_delay: float = 0.0
    total_shared_delay: float = 0.0
    net_delay: float = 0.0
    summary: dict[str, Any] = Field(default_factory=dict)


class TIAAnalysisSummarySchema(BaseModel):
    """Summary of a TIA analysis (used in list responses)."""

    analysis_id: str
    project_name: str = ""
    fragment_count: int = 0
    net_delay: float = 0.0
    total_owner_delay: float = 0.0
    total_contractor_delay: float = 0.0


class TIAListResponse(BaseModel):
    """Response for GET /api/v1/tia/analyses."""

    analyses: list[TIAAnalysisSummarySchema] = Field(default_factory=list)


class TIASummaryResponse(BaseModel):
    """Response for GET /api/v1/tia/analyses/{id}/summary."""

    analysis_id: str
    total_owner_delay: float = 0.0
    total_contractor_delay: float = 0.0
    total_shared_delay: float = 0.0
    net_delay: float = 0.0
    summary: dict[str, Any] = Field(default_factory=dict)


# ── Contract Compliance ──────────────────────────────────


class ContractCheckRequest(BaseModel):
    """Request body for POST /api/v1/contract/check."""

    analysis_id: str


class ContractProvisionSchema(BaseModel):
    """A contract provision."""

    provision_id: str
    name: str
    description: str
    category: str = ""
    reference: str = ""
    threshold_days: float = 0.0
    details: str = ""


class ComplianceCheckSchema(BaseModel):
    """A single compliance check result."""

    fragment_id: str
    fragment_name: str
    provision_id: str
    provision_name: str
    provision_category: str = ""
    status: str = "info"
    finding: str = ""
    recommendation: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class ContractCheckResponse(BaseModel):
    """Response for POST /api/v1/contract/check."""

    analysis_id: str
    checks: list[ComplianceCheckSchema] = Field(default_factory=list)
    total_checks: int = 0
    warnings: int = 0
    failures: int = 0


class ContractProvisionsResponse(BaseModel):
    """Response for GET /api/v1/contract/provisions."""

    provisions: list[ContractProvisionSchema] = Field(default_factory=list)


# ── EVM (Earned Value Management) ─────────────────────


class EVMAnalyzeRequest(BaseModel):
    """Request body for POST /api/v1/evm/analyze/{project_id}."""

    pass


class EVMMetricsSchema(BaseModel):
    """EVM metric values for a scope element."""

    scope_name: str = ""
    scope_id: str = ""
    bac: float = 0.0
    pv: float = 0.0
    ev: float = 0.0
    ac: float = 0.0
    sv: float = 0.0
    cv: float = 0.0
    spi: float = 0.0
    cpi: float = 0.0
    eac_cpi: float = 0.0
    eac_combined: float = 0.0
    etc: float = 0.0
    vac: float = 0.0
    tcpi: float = 0.0
    percent_complete_ev: float = 0.0
    percent_spent: float = 0.0


class SCurvePointSchema(BaseModel):
    """A single data point on the S-curve chart."""

    date: str
    cumulative_pv: float = 0.0
    cumulative_ev: float = 0.0
    cumulative_ac: float = 0.0


class HealthClassificationSchema(BaseModel):
    """Health classification for a performance index."""

    index_name: str
    value: float = 0.0
    status: str = "critical"
    label: str = ""


class WBSMetricsSchema(BaseModel):
    """EVM metrics for a single WBS element."""

    wbs_id: str
    wbs_name: str = ""
    metrics: EVMMetricsSchema = Field(default_factory=EVMMetricsSchema)
    activity_count: int = 0


class EVMAnalysisSchema(BaseModel):
    """Full EVM analysis response."""

    analysis_id: str
    project_name: str = ""
    project_id: str = ""
    data_date: Optional[str] = None
    metrics: EVMMetricsSchema = Field(default_factory=EVMMetricsSchema)
    wbs_breakdown: list[WBSMetricsSchema] = Field(default_factory=list)
    s_curve: list[SCurvePointSchema] = Field(default_factory=list)
    schedule_health: HealthClassificationSchema = Field(
        default_factory=HealthClassificationSchema
    )
    cost_health: HealthClassificationSchema = Field(
        default_factory=HealthClassificationSchema
    )
    forecast: dict[str, float] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


class EVMAnalysisSummarySchema(BaseModel):
    """Summary of an EVM analysis (used in list responses)."""

    analysis_id: str
    project_name: str = ""
    project_id: str = ""
    bac: float = 0.0
    spi: float = 0.0
    cpi: float = 0.0
    schedule_health: str = ""
    cost_health: str = ""


class EVMListResponse(BaseModel):
    """Response for GET /api/v1/evm/analyses."""

    analyses: list[EVMAnalysisSummarySchema] = Field(default_factory=list)


class SCurveResponse(BaseModel):
    """Response for GET /api/v1/evm/analyses/{id}/s-curve."""

    analysis_id: str
    points: list[SCurvePointSchema] = Field(default_factory=list)


class WBSDrillResponse(BaseModel):
    """Response for GET /api/v1/evm/analyses/{id}/wbs-drill."""

    analysis_id: str
    wbs_breakdown: list[WBSMetricsSchema] = Field(default_factory=list)


class ForecastResponse(BaseModel):
    """Response for GET /api/v1/evm/analyses/{id}/forecast."""

    analysis_id: str
    bac: float = 0.0
    eac_cpi: float = 0.0
    eac_combined: float = 0.0
    eac_etc_new: float = 0.0
    etc: float = 0.0
    vac: float = 0.0
    tcpi: float = 0.0
