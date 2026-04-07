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
    version: str = "0.8.0-dev"


# ── Upload ───────────────────────────────────────────────


class ScheduleMetadataSchema(BaseModel):
    """Intelligent metadata extracted from filename and XER data."""

    update_number: Optional[int] = None
    revision_number: Optional[int] = None
    is_draft: bool = False
    is_final: bool = False
    is_baseline: bool = False
    schedule_type: str = "unknown"
    schedule_prefix: str = ""
    has_baseline_dates: bool = False
    baseline_coverage_pct: float = 0.0
    retained_logic: bool = False
    progress_override: bool = False
    multiple_float_paths: bool = False
    tags: list[str] = Field(default_factory=list)


class ProjectSummary(BaseModel):
    """Summary returned after uploading an XER file."""

    project_id: str
    name: str = ""
    activity_count: int = 0
    relationship_count: int = 0
    calendar_count: int = 0
    wbs_count: int = 0
    data_date: Optional[str] = None
    metadata: Optional[ScheduleMetadataSchema] = None


# ── Project list ─────────────────────────────────────────


class ProjectListItem(BaseModel):
    """A single project in the list response."""

    project_id: str
    name: str = ""
    activity_count: int = 0
    relationship_count: int = 0
    data_date: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


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


class ActivityStatusSummary(BaseModel):
    """Activity status breakdown counts."""

    total: int = 0
    complete: int = 0
    in_progress: int = 0
    not_started: int = 0


class RelationshipTypeSummary(BaseModel):
    """Relationship type breakdown counts."""

    total: int = 0
    fs: int = 0
    ff: int = 0
    ss: int = 0
    sf: int = 0


class ProjectDetailResponse(BaseModel):
    """Response for GET /api/v1/projects/{project_id}."""

    project_id: str
    name: str = ""
    data_date: Optional[str] = None
    activities: list[ActivitySchema] = Field(default_factory=list)
    relationships: list[RelationshipSchema] = Field(default_factory=list)
    wbs_stats: Optional[WBSStats] = None
    activity_summary: Optional[ActivityStatusSummary] = None
    relationship_summary: Optional[RelationshipTypeSummary] = None


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
    direction: str = "max"
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
    """A manipulation indicator with classification scoring."""

    task_id: str
    task_name: str
    indicator: str
    description: str
    severity: str = "critical"
    classification: str = "suspicious"
    score: int = 0
    rationale: str = ""


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
    manipulation_classification: str = "normal"
    manipulation_score: int = 0
    manipulation_rationale: str = ""
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
    # MIP 3.4 bifurcated fields (populated when bifurcated=True)
    progress_delay_days: Optional[float] = None
    revision_delay_days: Optional[float] = None
    half_step_summary: Optional[dict[str, Any]] = None


class HalfStepRequest(BaseModel):
    """Request body for POST /api/v1/forensic/half-step."""

    baseline_id: str
    update_id: str


class HalfStepResponse(BaseModel):
    """Response for POST /api/v1/forensic/half-step."""

    completion_a_days: float = 0.0
    completion_half_step_days: float = 0.0
    completion_b_days: float = 0.0
    progress_effect_days: float = 0.0
    revision_effect_days: float = 0.0
    total_delay_days: float = 0.0
    progress_direction: str = ""
    revision_direction: str = ""
    invariant_holds: bool = False
    activities_updated: int = 0
    critical_path_a: list[str] = Field(default_factory=list)
    critical_path_half_step: list[str] = Field(default_factory=list)
    critical_path_b: list[str] = Field(default_factory=list)
    classification_summary: dict[str, int] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


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
    schedule_health: HealthClassificationSchema = Field(default_factory=HealthClassificationSchema)
    cost_health: HealthClassificationSchema = Field(default_factory=HealthClassificationSchema)
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


# ── Risk (Monte Carlo QSRA) ─────────────────────────────


class DurationRiskSchema(BaseModel):
    """Duration risk specification for a single activity."""

    activity_id: str
    distribution: str = "pert"
    min_duration: float = 0.0
    most_likely: float = 0.0
    max_duration: float = 0.0


class RiskEventSchema(BaseModel):
    """A discrete risk event that may affect one or more activities."""

    risk_id: str
    name: str = ""
    probability: float = 0.0
    impact_hours: float = 0.0
    affected_activities: list[str] = Field(default_factory=list)


class SimulationConfigSchema(BaseModel):
    """Configuration for a Monte Carlo simulation run."""

    iterations: int = 1000
    default_distribution: str = "pert"
    default_uncertainty: float = 0.2
    seed: Optional[int] = None
    confidence_levels: list[int] = Field(default_factory=lambda: [10, 25, 50, 75, 80, 90])


class RunSimulationRequest(BaseModel):
    """Request body for POST /api/v1/risk/simulate/{project_id}."""

    config: Optional[SimulationConfigSchema] = None
    duration_risks: list[DurationRiskSchema] = Field(default_factory=list)
    risk_events: list[RiskEventSchema] = Field(default_factory=list)


class PValueSchema(BaseModel):
    """A P-value (percentile) result."""

    percentile: int = 0
    duration_days: float = 0.0
    delta_days: float = 0.0


class HistogramBinSchema(BaseModel):
    """A single bin of the completion-duration histogram."""

    bin_start: float = 0.0
    bin_end: float = 0.0
    count: int = 0
    frequency: float = 0.0


class CriticalityEntrySchema(BaseModel):
    """Criticality index for a single activity."""

    activity_id: str = ""
    activity_name: str = ""
    criticality_pct: float = 0.0


class SensitivityEntrySchema(BaseModel):
    """Sensitivity (Spearman correlation) for a single activity."""

    activity_id: str = ""
    activity_name: str = ""
    correlation: float = 0.0


class RiskSCurvePointSchema(BaseModel):
    """A single point on the cumulative probability S-curve."""

    duration_days: float = 0.0
    cumulative_probability: float = 0.0


class SimulationResultSchema(BaseModel):
    """Full response for a Monte Carlo simulation."""

    simulation_id: str = ""
    project_name: str = ""
    project_id: str = ""
    iterations: int = 0
    deterministic_days: float = 0.0
    mean_days: float = 0.0
    std_days: float = 0.0
    p_values: list[PValueSchema] = Field(default_factory=list)
    histogram: list[HistogramBinSchema] = Field(default_factory=list)
    criticality: list[CriticalityEntrySchema] = Field(default_factory=list)
    sensitivity: list[SensitivityEntrySchema] = Field(default_factory=list)
    s_curve: list[RiskSCurvePointSchema] = Field(default_factory=list)


class SimulationSummarySchema(BaseModel):
    """Summary of a simulation (used in list responses)."""

    simulation_id: str = ""
    project_name: str = ""
    project_id: str = ""
    iterations: int = 0
    deterministic_days: float = 0.0
    mean_days: float = 0.0
    p50_days: float = 0.0
    p80_days: float = 0.0


class SimulationListResponse(BaseModel):
    """Response for GET /api/v1/risk/simulations."""

    simulations: list[SimulationSummarySchema] = Field(default_factory=list)


class HistogramResponse(BaseModel):
    """Response for GET /api/v1/risk/simulations/{id}/histogram."""

    simulation_id: str = ""
    deterministic_days: float = 0.0
    bins: list[HistogramBinSchema] = Field(default_factory=list)
    p_values: list[PValueSchema] = Field(default_factory=list)


class TornadoResponse(BaseModel):
    """Response for GET /api/v1/risk/simulations/{id}/tornado."""

    simulation_id: str = ""
    entries: list[SensitivityEntrySchema] = Field(default_factory=list)


class CriticalityResponse(BaseModel):
    """Response for GET /api/v1/risk/simulations/{id}/criticality."""

    simulation_id: str = ""
    entries: list[CriticalityEntrySchema] = Field(default_factory=list)


class RiskSCurveResponse(BaseModel):
    """Response for GET /api/v1/risk/simulations/{id}/s-curve."""

    simulation_id: str = ""
    deterministic_days: float = 0.0
    points: list[RiskSCurvePointSchema] = Field(default_factory=list)
    p_values: list[PValueSchema] = Field(default_factory=list)


# ── Intelligence (v0.8) ─────────────────────────────────


class ActivityFloatTrendSchema(BaseModel):
    """Per-activity float trend data."""

    task_code: str
    task_name: str = ""
    wbs_id: str = ""
    old_float_days: float = 0.0
    new_float_days: float = 0.0
    delta_days: float = 0.0
    direction: str = "stable"
    is_critical_baseline: bool = False
    is_critical_update: bool = False
    progress_pct: float = 0.0


class FloatTrendThresholdSchema(BaseModel):
    """Threshold status for a float trend metric."""

    value: float = 0.0
    status: str = "green"
    unit: str = ""
    percentage: Optional[float] = None


class FloatTrendResponse(BaseModel):
    """Response for GET /api/v1/projects/{id}/float-trends."""

    fei: float = 0.0
    near_critical_drift: int = 0
    cp_stability: float = 100.0
    activity_trends: list[ActivityFloatTrendSchema] = Field(default_factory=list)
    wbs_velocity: dict[str, float] = Field(default_factory=dict)
    thresholds: dict[str, Any] = Field(default_factory=dict)
    days_between_updates: float = 0.0
    total_matched: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)


class FloatTrendRequest(BaseModel):
    """Request body for POST /api/v1/float-trends/analyze."""

    baseline_id: str
    update_id: str


class AlertSchema(BaseModel):
    """A single early warning alert."""

    rule_id: str
    severity: str
    title: str
    description: str
    affected_activities: list[str] = Field(default_factory=list)
    projected_impact_days: float = 0.0
    confidence: float = 0.5
    alert_score: float = 0.0


class AlertsResponse(BaseModel):
    """Response for GET /api/v1/projects/{id}/alerts."""

    alerts: list[AlertSchema] = Field(default_factory=list)
    total_alerts: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    aggregate_score: float = 0.0
    summary: dict[str, Any] = Field(default_factory=dict)


class AlertsRequest(BaseModel):
    """Request body for POST /api/v1/alerts/analyze."""

    baseline_id: str
    update_id: str


class ScheduleHealthResponse(BaseModel):
    """Response for GET /api/v1/projects/{id}/health."""

    overall: float = 0.0
    dcma_component: float = 0.0
    float_component: float = 0.0
    logic_component: float = 0.0
    trend_component: float = 0.0
    dcma_raw: float = 0.0
    float_raw: float = 0.0
    logic_raw: float = 0.0
    trend_raw: float = 0.0
    rating: str = "poor"
    trend_arrow: str = "→"
    details: dict[str, Any] = Field(default_factory=dict)


class HealthRequest(BaseModel):
    """Request body for POST /api/v1/health/analyze."""

    project_id: str
    baseline_id: Optional[str] = None


# ── Delay Prediction ─────────────────────────────────────


class RiskFactorSchema(BaseModel):
    """An explainable risk factor."""

    name: str = ""
    contribution: float = 0.0
    description: str = ""
    value: str = ""


class ActivityRiskSchema(BaseModel):
    """Risk assessment for a single activity."""

    task_id: str = ""
    task_code: str = ""
    task_name: str = ""
    risk_score: float = 0.0
    risk_level: str = "low"
    predicted_delay_days: float = 0.0
    confidence: float = 0.0
    top_risk_factors: list[RiskFactorSchema] = Field(default_factory=list)
    is_critical_path: bool = False
    wbs_id: str = ""
    float_risk: float = 0.0
    progress_risk: float = 0.0
    logic_risk: float = 0.0
    duration_risk: float = 0.0
    network_risk: float = 0.0
    trend_risk: float = 0.0


class DelayPredictionResponse(BaseModel):
    """Response for GET /api/v1/projects/{id}/delay-prediction."""

    activity_risks: list[ActivityRiskSchema] = Field(default_factory=list)
    project_risk_score: float = 0.0
    project_risk_level: str = "low"
    predicted_completion_delay: float = 0.0
    high_risk_count: int = 0
    critical_risk_count: int = 0
    risk_distribution: dict[str, int] = Field(default_factory=dict)
    methodology: str = ""
    features_used: int = 0
    has_baseline: bool = False
    summary: dict[str, Any] = Field(default_factory=dict)


# ── What-If Simulator ─────────────────────────────────


class DurationAdjustmentSchema(BaseModel):
    """A duration adjustment for a what-if scenario."""

    target: str = ""  # task_code, "WBS:xxx", or "*"
    pct_change: float = 0.0
    min_pct: float | None = None
    max_pct: float | None = None


class WhatIfRequest(BaseModel):
    """Request body for POST /api/v1/projects/{id}/what-if."""

    name: str = "Scenario"
    adjustments: list[DurationAdjustmentSchema] = Field(default_factory=list)
    iterations: int = 1


class ActivityImpactSchema(BaseModel):
    """Per-activity impact of a what-if scenario."""

    task_id: str = ""
    task_code: str = ""
    task_name: str = ""
    original_duration_days: float = 0.0
    adjusted_duration_days: float = 0.0
    delta_days: float = 0.0
    original_total_float: float = 0.0
    adjusted_total_float: float = 0.0
    was_critical: bool = False
    is_critical: bool = False


# ── Schedule Scorecard ─────────────────────────────────


# ── Resource Leveling ──────────────────────────────────


class ResourceLimitSchema(BaseModel):
    """Resource capacity limit."""

    rsrc_id: str = ""
    max_units: float = 1.0
    cost_per_unit_day: float = 0.0


class LevelingRequest(BaseModel):
    """Request for POST /api/v1/projects/{id}/resource-leveling."""

    resource_limits: list[ResourceLimitSchema] = Field(default_factory=list)
    priority_rule: str = "late_start"
    max_project_extension_pct: float | None = None


class ActivityShiftSchema(BaseModel):
    """How an activity was shifted during leveling."""

    task_id: str = ""
    task_code: str = ""
    task_name: str = ""
    original_start: float = 0.0
    leveled_start: float = 0.0
    shift_days: float = 0.0
    duration_days: float = 0.0
    resources: dict[str, float] = Field(default_factory=dict)


class ResourceProfileSchema(BaseModel):
    """Resource usage profile over time."""

    rsrc_id: str = ""
    rsrc_name: str = ""
    max_units: float = 0.0
    peak_demand: float = 0.0
    demand_by_day: list[float] = Field(default_factory=list)


class LevelingResponse(BaseModel):
    """Response for POST /api/v1/projects/{id}/resource-leveling."""

    original_duration_days: float = 0.0
    leveled_duration_days: float = 0.0
    extension_days: float = 0.0
    extension_pct: float = 0.0
    activity_shifts: list[ActivityShiftSchema] = Field(default_factory=list)
    resource_profiles: list[ResourceProfileSchema] = Field(default_factory=list)
    overloaded_periods: int = 0
    leveling_iterations: int = 0
    priority_rule: str = ""
    methodology: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)


# ── Duration Prediction ────────────────────────────────


class DurationPredictionResponse(BaseModel):
    """Response for GET /api/v1/projects/{id}/duration-prediction."""

    predicted_duration_days: float = 0.0
    confidence_low: float = 0.0
    confidence_high: float = 0.0
    actual_duration_days: float = 0.0
    delta_days: float = 0.0
    model_r_squared: float = 0.0
    training_samples: int = 0
    feature_importances: dict[str, float] = Field(default_factory=dict)
    methodology: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)


class ScorecardDimensionSchema(BaseModel):
    """A single dimension of the schedule scorecard."""

    name: str = ""
    score: float = 0.0
    grade: str = "F"
    description: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class ScorecardResponse(BaseModel):
    """Response for GET /api/v1/projects/{id}/scorecard."""

    overall_score: float = 0.0
    overall_grade: str = "F"
    dimensions: list[ScorecardDimensionSchema] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    methodology: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)


# ── Time-Cost Pareto ───────────────────────────────────


class CostScenarioSchema(BaseModel):
    """A what-if scenario with cost impact."""

    name: str = ""
    adjustments: list[DurationAdjustmentSchema] = Field(default_factory=list)
    cost_delta: float = 0.0


class ParetoRequest(BaseModel):
    """Request for POST /api/v1/projects/{id}/pareto."""

    scenarios: list[CostScenarioSchema] = Field(default_factory=list)
    base_cost: float = 0.0


class ParetoPointSchema(BaseModel):
    """A point on the time-cost plane."""

    scenario_name: str = ""
    duration_days: float = 0.0
    total_cost: float = 0.0
    is_pareto_optimal: bool = False
    delta_days: float = 0.0
    delta_cost: float = 0.0


class ParetoResponse(BaseModel):
    """Response for POST /api/v1/projects/{id}/pareto."""

    base_duration_days: float = 0.0
    base_cost: float = 0.0
    all_points: list[ParetoPointSchema] = Field(default_factory=list)
    frontier: list[ParetoPointSchema] = Field(default_factory=list)
    scenarios_evaluated: int = 0
    frontier_size: int = 0
    methodology: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)


class WhatIfResponse(BaseModel):
    """Response for POST /api/v1/projects/{id}/what-if."""

    scenario_name: str = ""
    base_duration_days: float = 0.0
    adjusted_duration_days: float = 0.0
    delta_days: float = 0.0
    delta_pct: float = 0.0
    critical_path_changed: bool = False
    new_critical_path: list[str] = Field(default_factory=list)
    activity_impacts: list[ActivityImpactSchema] = Field(default_factory=list)
    iterations: int = 1
    distribution: list[float] = Field(default_factory=list)
    p_values: dict[int, float] = Field(default_factory=dict)
    std_days: float = 0.0
    methodology: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)


# ── Benchmarks ─────────────────────────────────────────


class PercentileRankingSchema(BaseModel):
    """Percentile ranking for a single metric."""

    metric_name: str = ""
    value: float = 0.0
    percentile: float = 0.0
    benchmark_mean: float = 0.0
    benchmark_median: float = 0.0
    benchmark_count: int = 0
    interpretation: str = "average"


class BenchmarkCompareResponse(BaseModel):
    """Response for GET /api/v1/benchmarks/compare/{project_id}."""

    rankings: list[PercentileRankingSchema] = Field(default_factory=list)
    overall_percentile: float = 0.0
    benchmark_count: int = 0
    size_category: str = ""
    project_dcma_score: float = 0.0
    project_activity_count: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)


class BenchmarkSummaryResponse(BaseModel):
    """Response for GET /api/v1/benchmarks/summary."""

    total_projects: int = 0
    size_distribution: dict[str, int] = Field(default_factory=dict)
    avg_dcma_score: float = 0.0
    avg_activity_count: float = 0.0
    avg_relationship_density: float = 0.0


class GDPRDeleteResponse(BaseModel):
    """Response for DELETE /api/v1/user/data."""

    deleted_uploads: int = 0
    deleted_projects: int = 0
    deleted_analyses: int = 0
    deleted_benchmarks: int = 0
    status: str = "complete"


class DashboardKPIs(BaseModel):
    """Response for GET /api/v1/dashboard."""

    total_projects: int = 0
    active_alerts: int = 0
    avg_health_score: float = 0.0
    projects_trending_up: int = 0
    projects_trending_down: int = 0
    most_critical_project: Optional[str] = None
    most_critical_score: Optional[float] = None


# ── Reports ─────────────────────────────────────────────


class GenerateReportRequest(BaseModel):
    """Request body for POST /api/v1/reports/generate."""

    project_id: str
    report_type: str  # 'health', 'comparison', 'forensic', 'tia', 'risk'
    baseline_id: Optional[str] = None
    options: dict[str, Any] = Field(default_factory=dict)


class GenerateReportResponse(BaseModel):
    """Response for POST /api/v1/reports/generate."""

    report_id: str
    report_type: str
    project_id: str
    generated_at: str
