# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Microsoft Project XML Parser.

Parses Microsoft Project XML exports (.xml) into the same ParsedSchedule
model used by the XER parser. This enables MeridianIQ to analyze schedules
from both Primavera P6 and Microsoft Project.

Supports Microsoft Project 2010+ XML format (MSPDI schema).

Note: This is a foundational implementation covering the core elements
(Project, Tasks, Resources, Assignments, Calendars). Advanced features
like custom fields, baselines, and extended attributes will be added
incrementally.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime

# Parse via defusedxml to reject XXE, billion-laughs, external DTDs, and
# entity-based attacks (CWE-611). Stdlib xml.etree is retained for the
# ``ET.Element`` type annotation only — defusedxml returns stdlib Elements,
# so type compatibility is preserved.
from defusedxml.ElementTree import fromstring as _safe_fromstring

from .models import (
    Calendar,
    ParsedSchedule,
    Project,
    Relationship,
    Resource,
    Task,
    TaskResource,
    WBS,
    XERHeader,
)

logger = logging.getLogger(__name__)

# Microsoft Project XML namespace
MSP_NS = "http://schemas.microsoft.com/project"


def _ns(tag: str) -> str:
    """Add MSP namespace to a tag name."""
    return f"{{{MSP_NS}}}{tag}"


def _text(element: ET.Element | None, tag: str, default: str = "") -> str:
    """Extract text from a child element."""
    if element is None:
        return default
    child = element.find(_ns(tag))
    if child is not None and child.text:
        return child.text.strip()
    # Try without namespace (some exports omit it)
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return default


def _float(element: ET.Element | None, tag: str, default: float = 0.0) -> float:
    """Extract float from a child element."""
    val = _text(element, tag)
    if val:
        try:
            return float(val)
        except ValueError:
            pass
    return default


def _parse_msp_date(date_str: str) -> datetime | None:
    """Parse an MSP date string (ISO 8601 format)."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _parse_duration_hours(dur_str: str) -> float:
    """Parse an MSP duration string like 'PT48H0M0S' into hours."""
    if not dur_str or not dur_str.startswith("PT"):
        return 0.0
    dur_str = dur_str[2:]  # Remove PT prefix
    hours = 0.0
    # Parse hours
    if "H" in dur_str:
        h_part, dur_str = dur_str.split("H", 1)
        try:
            hours += float(h_part)
        except ValueError:
            pass
    # Parse minutes
    if "M" in dur_str:
        m_part, dur_str = dur_str.split("M", 1)
        try:
            hours += float(m_part) / 60
        except ValueError:
            pass
    return hours


class MSPReader:
    """Parse Microsoft Project XML files into ParsedSchedule.

    Usage:
        reader = MSPReader()
        schedule = reader.parse(xml_content)
    """

    def parse(self, xml_content: str) -> ParsedSchedule:
        """Parse an MSP XML string into a ParsedSchedule.

        Args:
            xml_content: The full XML file content as a string.

        Returns:
            A ParsedSchedule populated with project data.
        """
        # forbid_dtd=True is stricter than defusedxml's default (which accepts
        # bare DTD declarations without fetching external resources). MSP
        # exports do not use DTD — rejecting it is pure defense in depth
        # against future entity-based attack constructs.
        root = _safe_fromstring(xml_content, forbid_dtd=True)

        schedule = ParsedSchedule(
            header=XERHeader(version="MSP-XML", encoding="utf-8"),
            parser_version="1.0.0-dev",
        )

        # Parse project metadata
        self._parse_project(root, schedule)

        # Parse calendars
        self._parse_calendars(root, schedule)

        # Parse tasks (activities) and WBS
        self._parse_tasks(root, schedule)

        # Parse resources
        self._parse_resources(root, schedule)

        # Parse assignments
        self._parse_assignments(root, schedule)

        # Build predecessor relationships from task links
        self._parse_links(root, schedule)

        return schedule

    def _parse_project(self, root: ET.Element, schedule: ParsedSchedule) -> None:
        """Extract project metadata."""
        name = _text(root, "Name", "Untitled Project")
        status_date = _text(root, "StatusDate") or _text(root, "CurrentDate")

        schedule.projects = [
            Project(
                proj_id="MSP-1",
                proj_short_name=name,
                last_recalc_date=_parse_msp_date(status_date),
                sum_data_date=_parse_msp_date(status_date),
            )
        ]

    def _parse_calendars(self, root: ET.Element, schedule: ParsedSchedule) -> None:
        """Extract calendar definitions."""
        cals_elem = root.find(_ns("Calendars")) or root.find("Calendars")
        if cals_elem is None:
            return

        for cal in cals_elem.findall(_ns("Calendar")) or cals_elem.findall("Calendar"):
            uid = _text(cal, "UID", "0")
            name = _text(cal, "Name", f"Calendar-{uid}")
            schedule.calendars.append(
                Calendar(
                    clndr_id=uid,
                    clndr_name=name,
                    day_hr_cnt=8.0,
                    week_hr_cnt=40.0,
                    clndr_type="CA_Base",
                    default_flag="Y" if _text(cal, "IsBaseCalendar") == "true" else "N",
                )
            )

    def _parse_tasks(self, root: ET.Element, schedule: ParsedSchedule) -> None:
        """Extract tasks — distinguish between summary tasks (WBS) and leaf tasks (activities)."""
        tasks_elem = root.find(_ns("Tasks")) or root.find("Tasks")
        if tasks_elem is None:
            return

        uid_to_outline: dict[str, int] = {}

        for task in tasks_elem.findall(_ns("Task")) or tasks_elem.findall("Task"):
            uid = _text(task, "UID", "0")
            name = _text(task, "Name", "")
            outline_level = int(_text(task, "OutlineLevel", "0"))
            is_summary = _text(task, "Summary") == "1"
            wbs_code = _text(task, "WBS", uid)

            uid_to_outline[uid] = outline_level

            start = _parse_msp_date(_text(task, "Start"))
            finish = _parse_msp_date(_text(task, "Finish"))
            actual_start = _parse_msp_date(_text(task, "ActualStart"))
            actual_finish = _parse_msp_date(_text(task, "ActualFinish"))
            duration = _parse_duration_hours(_text(task, "Duration"))
            remaining = _parse_duration_hours(_text(task, "RemainingDuration"))
            pct_complete = _float(task, "PercentComplete")
            total_slack = _parse_duration_hours(_text(task, "TotalSlack"))

            # Determine status
            if pct_complete >= 100:
                status = "TK_Complete"
            elif pct_complete > 0:
                status = "TK_Active"
            else:
                status = "TK_NotStart"

            # Determine task type
            is_milestone = _text(task, "Milestone") == "1"
            if is_milestone:
                task_type = "TT_Mile"
            elif is_summary:
                task_type = "TT_LOE"
            else:
                task_type = "TT_Task"

            if is_summary:
                # Summary tasks become WBS elements
                schedule.wbs_nodes.append(
                    WBS(
                        wbs_id=uid,
                        parent_wbs_id="",  # Will be resolved by outline level
                        wbs_short_name=wbs_code,
                        wbs_name=name,
                        seq_num=0,
                        proj_node_flag="Y" if outline_level == 0 else "N",
                    )
                )
            else:
                # Leaf tasks become activities
                schedule.activities.append(
                    Task(
                        task_id=uid,
                        task_code=wbs_code,
                        task_name=name,
                        task_type=task_type,
                        status_code=status,
                        wbs_id="",
                        clndr_id="1",
                        total_float_hr_cnt=total_slack,
                        remain_drtn_hr_cnt=remaining,
                        target_drtn_hr_cnt=duration,
                        act_start_date=actual_start,
                        act_end_date=actual_finish,
                        early_start_date=start,
                        early_end_date=finish,
                        phys_complete_pct=pct_complete,
                    )
                )

    def _parse_resources(self, root: ET.Element, schedule: ParsedSchedule) -> None:
        """Extract resource definitions."""
        res_elem = root.find(_ns("Resources")) or root.find("Resources")
        if res_elem is None:
            return

        for res in res_elem.findall(_ns("Resource")) or res_elem.findall("Resource"):
            uid = _text(res, "UID", "0")
            if uid == "0":
                continue  # Skip the default "Unassigned" resource
            name = _text(res, "Name", f"Resource-{uid}")
            rtype = _text(res, "Type", "1")
            type_map = {"0": "RT_Material", "1": "RT_Labor", "2": "RT_Cost"}

            schedule.resources.append(
                Resource(
                    rsrc_id=uid,
                    rsrc_name=name,
                    rsrc_type=type_map.get(rtype, "RT_Labor"),
                )
            )

    def _parse_assignments(self, root: ET.Element, schedule: ParsedSchedule) -> None:
        """Extract resource assignments."""
        assign_elem = root.find(_ns("Assignments")) or root.find("Assignments")
        if assign_elem is None:
            return

        for assign in assign_elem.findall(_ns("Assignment")) or assign_elem.findall("Assignment"):
            task_uid = _text(assign, "TaskUID")
            rsrc_uid = _text(assign, "ResourceUID")
            if not task_uid or not rsrc_uid or rsrc_uid == "0":
                continue

            cost = _float(assign, "Cost")
            actual_cost = _float(assign, "ActualCost")
            remaining_cost = _float(assign, "RemainingCost")

            schedule.task_resources.append(
                TaskResource(
                    task_id=task_uid,
                    rsrc_id=rsrc_uid,
                    target_cost=cost,
                    act_reg_cost=actual_cost,
                    remain_cost=remaining_cost,
                )
            )

    def _parse_links(self, root: ET.Element, schedule: ParsedSchedule) -> None:
        """Extract predecessor links from task definitions."""
        tasks_elem = root.find(_ns("Tasks")) or root.find("Tasks")
        if tasks_elem is None:
            return

        link_type_map = {"0": "PR_FF", "1": "PR_FS", "2": "PR_SF", "3": "PR_SS"}

        for task in tasks_elem.findall(_ns("Task")) or tasks_elem.findall("Task"):
            task_uid = _text(task, "UID")
            if not task_uid:
                continue

            for link in task.findall(_ns("PredecessorLink")) or task.findall("PredecessorLink"):
                pred_uid = _text(link, "PredecessorUID")
                link_type = _text(link, "Type", "1")
                lag = _parse_duration_hours(_text(link, "LinkLag"))

                if pred_uid:
                    schedule.relationships.append(
                        Relationship(
                            task_pred_id=f"{pred_uid}-{task_uid}",
                            task_id=task_uid,
                            pred_task_id=pred_uid,
                            pred_type=link_type_map.get(link_type, "PR_FS"),
                            lag_hr_cnt=lag,
                        )
                    )
