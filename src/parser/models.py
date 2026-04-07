# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Pydantic models for Oracle P6 XER file tables."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class XERHeader(BaseModel):
    """ERMHDR -- XER file export metadata."""

    version: str = ""
    date_format: str = ""
    currency_name: str = ""
    file_name: str = ""
    user_name: str = ""
    export_date: str = ""


class Project(BaseModel):
    """PROJECT table -- project-level metadata."""

    proj_id: str
    proj_short_name: str = ""
    last_recalc_date: Optional[datetime] = None
    plan_start_date: Optional[datetime] = None
    plan_end_date: Optional[datetime] = None
    scd_end_date: Optional[datetime] = None
    sum_data_date: Optional[datetime] = None
    last_tasksum_date: Optional[datetime] = None
    fcst_start_date: Optional[datetime] = None


class Calendar(BaseModel):
    """CALENDAR table."""

    clndr_id: str
    clndr_name: str = ""
    day_hr_cnt: float = 8.0
    week_hr_cnt: float = 40.0
    clndr_type: str = ""
    default_flag: str = "N"
    clndr_data: str = ""


class WBS(BaseModel):
    """PROJWBS table -- Work Breakdown Structure."""

    wbs_id: str
    proj_id: str = ""
    parent_wbs_id: str = ""
    wbs_short_name: str = ""
    wbs_name: str = ""
    seq_num: int = 0
    proj_node_flag: str = "N"


class Task(BaseModel):
    """TASK table -- activities/tasks."""

    task_id: str
    proj_id: str = ""
    wbs_id: str = ""
    clndr_id: str = ""
    task_code: str = ""
    task_name: str = ""
    task_type: str = ""
    status_code: str = ""
    total_float_hr_cnt: Optional[float] = None
    free_float_hr_cnt: Optional[float] = None
    remain_drtn_hr_cnt: float = 0.0
    target_drtn_hr_cnt: float = 0.0
    act_start_date: Optional[datetime] = None
    act_end_date: Optional[datetime] = None
    early_start_date: Optional[datetime] = None
    early_end_date: Optional[datetime] = None
    late_start_date: Optional[datetime] = None
    late_end_date: Optional[datetime] = None
    target_start_date: Optional[datetime] = None
    target_end_date: Optional[datetime] = None
    restart_date: Optional[datetime] = None
    reend_date: Optional[datetime] = None
    phys_complete_pct: float = 0.0
    complete_pct_type: str = ""
    duration_type: str = ""
    cstr_date: Optional[datetime] = None
    cstr_type: str = ""
    cstr_date2: Optional[datetime] = None
    cstr_type2: str = ""
    float_path: Optional[int] = None
    float_path_order: Optional[int] = None
    driving_path_flag: str = ""
    priority_type: str = ""
    act_work_qty: float = 0.0
    remain_work_qty: float = 0.0
    target_work_qty: float = 0.0
    act_equip_qty: float = 0.0
    remain_equip_qty: float = 0.0
    target_equip_qty: float = 0.0
    # Computed field for multi-project support
    task_id_key: str = ""


class Relationship(BaseModel):
    """TASKPRED table -- predecessor relationships."""

    task_pred_id: str = ""
    task_id: str
    pred_task_id: str
    proj_id: str = ""
    pred_proj_id: str = ""
    pred_type: str = "PR_FS"
    lag_hr_cnt: float = 0.0


class Resource(BaseModel):
    """RSRC table."""

    rsrc_id: str
    rsrc_name: str = ""
    rsrc_type: str = ""


class TaskResource(BaseModel):
    """TASKRSRC table."""

    taskrsrc_id: str = ""
    task_id: str
    rsrc_id: str = ""
    proj_id: str = ""
    target_qty: float = 0.0
    act_reg_qty: float = 0.0
    remain_qty: float = 0.0
    target_cost: float = 0.0
    act_reg_cost: float = 0.0
    remain_cost: float = 0.0


class ActivityCode(BaseModel):
    """ACTVCODE table."""

    actv_code_id: str
    actv_code_type_id: str = ""
    actv_code_name: str = ""
    short_name: str = ""


class ActivityCodeType(BaseModel):
    """ACTVTYPE table."""

    actv_code_type_id: str
    actv_code_type: str = ""
    proj_id: str = ""


class TaskActivityCode(BaseModel):
    """TASKACTV table."""

    task_id: str
    actv_code_id: str


class UDFType(BaseModel):
    """UDFTYPE table."""

    udf_type_id: str
    table_name: str = ""
    udf_type_label: str = ""


class UDFValue(BaseModel):
    """UDFVALUE table."""

    udf_type_id: str
    fk_id: str = ""
    udf_text: Optional[str] = None
    udf_number: Optional[float] = None
    udf_date: Optional[datetime] = None


class FinancialPeriod(BaseModel):
    """FINDATES table."""

    fin_dates_id: str
    fin_dates_name: str = ""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class TaskFinancial(BaseModel):
    """TASKFIN table."""

    task_id: str
    fin_dates_id: str = ""
    target_cost: float = 0.0
    act_cost: float = 0.0


class ParsedSchedule(BaseModel):
    """Complete parsed XER schedule -- the main output object."""

    header: XERHeader = Field(default_factory=XERHeader)
    projects: list[Project] = Field(default_factory=list)
    calendars: list[Calendar] = Field(default_factory=list)
    wbs_nodes: list[WBS] = Field(default_factory=list)
    activities: list[Task] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    resources: list[Resource] = Field(default_factory=list)
    task_resources: list[TaskResource] = Field(default_factory=list)
    activity_codes: list[ActivityCode] = Field(default_factory=list)
    activity_code_types: list[ActivityCodeType] = Field(default_factory=list)
    task_activity_codes: list[TaskActivityCode] = Field(default_factory=list)
    udf_types: list[UDFType] = Field(default_factory=list)
    udf_values: list[UDFValue] = Field(default_factory=list)
    financial_periods: list[FinancialPeriod] = Field(default_factory=list)
    task_financials: list[TaskFinancial] = Field(default_factory=list)
    raw_tables: dict[str, list[dict[str, str]]] = Field(default_factory=dict)
    unmapped_tables: list[str] = Field(default_factory=list)
    parser_version: str = "0.9.0"
