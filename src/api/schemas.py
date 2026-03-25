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
    version: str = "0.1.0-dev"


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
    changed_percentage: float = 0.0
    critical_path_changed: bool = False
    activities_joined_cp: list[str] = Field(default_factory=list)
    activities_left_cp: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
