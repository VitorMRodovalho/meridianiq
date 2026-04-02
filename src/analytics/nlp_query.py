# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""NLP Schedule Query engine — natural language interface for schedule data.

Allows users to ask questions about a schedule in plain language.
Uses Claude API to interpret the question, extract relevant data,
and generate a human-readable answer grounded in the schedule facts.

The engine does NOT send raw schedule data to the API. Instead, it:
1. Pre-computes a structured summary of the schedule
2. Sends the summary + user question to Claude
3. Returns the answer with citations to specific activities

This approach minimizes token usage and prevents sensitive data exposure.

Standards:
    - PMI PMBOK 7 S4.6 — Measurement Performance Domain
    - DCMA 14-Point — Referenced in answers where applicable
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)


@dataclass
class NLPQueryResult:
    """Result of a natural language schedule query.

    Attributes:
        question: The original user question.
        answer: Claude's natural language answer.
        data_context: Key data points used to generate the answer.
        model: The Claude model used.
        tokens_used: Total tokens consumed.
    """

    question: str = ""
    answer: str = ""
    data_context: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    tokens_used: int = 0


def _build_schedule_summary(schedule: ParsedSchedule) -> dict[str, Any]:
    """Build a compact summary of the schedule for Claude context.

    Keeps only essential metrics to minimize token usage.
    Never sends task names or descriptions — only codes and numbers.
    """
    # Project info
    project_name = ""
    data_date = None
    if schedule.projects:
        proj = schedule.projects[0]
        project_name = proj.proj_short_name or ""
        dd = proj.last_recalc_date or proj.sum_data_date
        if dd:
            data_date = dd.isoformat()

    # Activity status counts
    complete = 0
    active = 0
    not_started = 0
    milestones = 0
    loe = 0
    total_float_sum = 0.0
    negative_float_count = 0
    critical_count = 0
    high_float_count = 0

    duration_stats: list[float] = []

    for a in schedule.activities:
        status = a.status_code.upper()
        if status == "TK_COMPLETE":
            complete += 1
        elif status == "TK_ACTIVE":
            active += 1
        else:
            not_started += 1

        task_type = a.task_type.lower()
        if "mile" in task_type:
            milestones += 1
        elif "loe" in task_type:
            loe += 1

        tf = a.total_float_hr_cnt or 0
        total_float_sum += tf
        if tf < 0:
            negative_float_count += 1
        if abs(tf) < 0.01:
            critical_count += 1
        if tf > 352:  # > 44 days * 8h
            high_float_count += 1

        dur = a.remain_drtn_hr_cnt or 0
        if dur > 0 and task_type not in ("tt_mile", "tt_loe", "tt_wbs"):
            duration_stats.append(dur / 8.0)

    n = len(schedule.activities)
    avg_float = (total_float_sum / n / 8.0) if n else 0
    avg_duration = (sum(duration_stats) / len(duration_stats)) if duration_stats else 0
    max_duration = max(duration_stats) if duration_stats else 0

    # Relationship stats
    rel_types: dict[str, int] = {}
    for r in schedule.relationships:
        rt = r.pred_type.upper()
        rel_types[rt] = rel_types.get(rt, 0) + 1

    # WBS depth
    wbs_count = len(schedule.wbs_nodes)

    return {
        "project_name": project_name,
        "data_date": data_date,
        "total_activities": n,
        "complete": complete,
        "in_progress": active,
        "not_started": not_started,
        "milestones": milestones,
        "loe_activities": loe,
        "completion_pct": round(complete / n * 100, 1) if n else 0,
        "total_relationships": len(schedule.relationships),
        "relationship_types": rel_types,
        "wbs_elements": wbs_count,
        "calendars": len(schedule.calendars),
        "critical_activities": critical_count,
        "negative_float_activities": negative_float_count,
        "high_float_activities": high_float_count,
        "avg_float_days": round(avg_float, 1),
        "avg_duration_days": round(avg_duration, 1),
        "max_duration_days": round(max_duration, 1),
        "total_task_activities": len(duration_stats),
    }


def _build_dcma_summary(schedule: ParsedSchedule) -> dict[str, Any] | None:
    """Run DCMA and return compact summary."""
    try:
        from src.analytics.dcma14 import DCMA14Analyzer

        analyzer = DCMA14Analyzer(schedule)
        result = analyzer.analyze()
        return {
            "overall_score": round(result.overall_score, 1),
            "passed": result.passed_count,
            "failed": result.failed_count,
            "failed_checks": [
                {"name": m.name, "value": round(m.value, 1), "threshold": m.threshold}
                for m in result.metrics
                if not m.passed
            ],
        }
    except Exception:
        return None


SYSTEM_PROMPT = """You are MeridianIQ, a schedule intelligence assistant specialized in
construction project scheduling and P6 XER analysis.

You answer questions about the user's schedule based on the data summary provided.
Your answers should be:
- Concise and professional (2-4 sentences for simple questions, more for complex)
- Grounded in the data — cite specific numbers from the summary
- Reference applicable standards (DCMA, AACE, PMI) when relevant
- Flag concerns proactively (e.g., high negative float, low logic density)
- Use construction scheduling terminology appropriate for the audience

Do NOT:
- Guess or fabricate data not present in the summary
- Provide generic advice unrelated to the specific schedule data
- Mention that you're an AI or that you're working from a summary

Respond in the same language the user's question is written in."""


async def query_schedule(
    schedule: ParsedSchedule,
    question: str,
    api_key: str | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> NLPQueryResult:
    """Ask a natural language question about a schedule.

    Args:
        schedule: The parsed schedule to query.
        question: User's question in natural language.
        api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
        model: Claude model to use.

    Returns:
        NLPQueryResult with the answer and context.

    Raises:
        ValueError: If no API key is available.
        RuntimeError: If the Claude API call fails.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError(
            "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
            "or pass api_key parameter."
        )

    # Build context
    summary = _build_schedule_summary(schedule)
    dcma = _build_dcma_summary(schedule)

    context = f"""Schedule Data Summary:
{json.dumps(summary, indent=2)}"""

    if dcma:
        context += f"""

DCMA 14-Point Assessment:
{json.dumps(dcma, indent=2)}"""

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"{context}\n\nQuestion: {question}",
                }
            ],
        )

        answer = response.content[0].text if response.content else ""
        tokens = (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0

        return NLPQueryResult(
            question=question,
            answer=answer,
            data_context=summary,
            model=model,
            tokens_used=tokens,
        )

    except Exception as exc:
        raise RuntimeError(f"Claude API call failed: {exc}") from exc
