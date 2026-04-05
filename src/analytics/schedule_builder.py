# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Conversational schedule builder — NLP-driven schedule generation.

Uses Claude API to interpret a natural language project description and
extract structured parameters, then calls the schedule generation engine
to produce a complete schedule.

References:
    - AbdElMottaleb (2025) — ML for Construction Scheduling
    - PMI Practice Standard for Scheduling — Schedule Development
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from src.analytics.schedule_generation import GeneratedSchedule, GenerationInput, generate_schedule

logger = logging.getLogger(__name__)


@dataclass
class BuilderResult:
    """Result of conversational schedule building."""

    generated: GeneratedSchedule | None = None
    extracted_params: dict[str, Any] = field(default_factory=dict)
    interpretation: str = ""
    methodology: str = ""
    summary: dict[str, Any] = field(default_factory=dict)


_EXTRACTION_PROMPT = """You are a construction scheduling expert. Extract project parameters from the user's description.

Return ONLY a JSON object with these fields (use defaults if not mentioned):
{
    "project_type": "commercial" | "industrial" | "infrastructure" | "residential",
    "project_name": "string",
    "target_duration_days": 0,
    "size_category": "small" | "medium" | "large" | "mega",
    "complexity_factor": 1.0,
    "interpretation": "One sentence explaining your understanding of the project"
}

Rules:
- "small" = <100 activities, "medium" = 100-500, "large" = 500-2000, "mega" = >2000
- complexity_factor: 0.5 = simple/repetitive, 1.0 = normal, 2.0 = complex/unique
- If duration is mentioned in months, convert to days (1 month ≈ 22 working days)
- If not enough info for a field, use sensible defaults

User's project description:
"""


async def build_schedule(
    description: str,
    api_key: str | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> BuilderResult:
    """Build a schedule from a natural language project description.

    Uses Claude to interpret the description, extract parameters, and
    generate a complete schedule.

    Args:
        description: Natural language project description.
        api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
        model: Claude model to use.

    Returns:
        BuilderResult with generated schedule and interpretation.

    References:
        - AbdElMottaleb (2025) — ML for Construction Scheduling
        - PMI Practice Standard for Scheduling
    """
    result = BuilderResult()

    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        # Fallback: parse keywords manually
        return _fallback_build(description)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        response = client.messages.create(
            model=model,
            max_tokens=500,
            messages=[{"role": "user", "content": _EXTRACTION_PROMPT + description}],
        )

        # Parse JSON from response
        text = response.content[0].text.strip()
        # Handle markdown code blocks
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        params_dict = json.loads(text)
        result.extracted_params = params_dict
        result.interpretation = params_dict.get("interpretation", "")

    except Exception as exc:
        logger.warning("Claude extraction failed, using fallback: %s", exc)
        return _fallback_build(description)

    # Build GenerationInput from extracted params
    gen_input = GenerationInput(
        project_type=params_dict.get("project_type", "commercial"),
        project_name=params_dict.get("project_name", "Generated Project"),
        target_duration_days=params_dict.get("target_duration_days", 0),
        size_category=params_dict.get("size_category", "medium"),
        complexity_factor=params_dict.get("complexity_factor", 1.0),
    )

    result.generated = generate_schedule(gen_input)

    result.methodology = (
        "NLP-driven schedule generation: Claude API parameter extraction + "
        "template-based generation (AbdElMottaleb 2025)"
    )

    result.summary = {
        "description": description[:200],
        "extracted_params": result.extracted_params,
        "interpretation": result.interpretation,
        "activity_count": result.generated.activity_count if result.generated else 0,
        "predicted_duration_days": (
            result.generated.predicted_duration_days if result.generated else 0
        ),
        "methodology": result.methodology,
    }

    return result


def _fallback_build(description: str) -> BuilderResult:
    """Keyword-based fallback when Claude API is not available."""
    desc_lower = description.lower()

    # Detect project type
    if any(w in desc_lower for w in ["factory", "plant", "refinery", "industrial", "pipeline"]):
        ptype = "industrial"
    elif any(w in desc_lower for w in ["road", "bridge", "highway", "tunnel", "railway"]):
        ptype = "infrastructure"
    elif any(w in desc_lower for w in ["house", "residential", "apartment", "housing"]):
        ptype = "residential"
    else:
        ptype = "commercial"

    # Detect size
    if any(w in desc_lower for w in ["small", "simple", "minor"]):
        size = "small"
    elif any(w in desc_lower for w in ["large", "major", "complex"]):
        size = "large"
    elif any(w in desc_lower for w in ["mega", "massive", "giant"]):
        size = "mega"
    else:
        size = "medium"

    gen_input = GenerationInput(
        project_type=ptype,
        project_name="Generated Project",
        size_category=size,
    )

    generated = generate_schedule(gen_input)

    return BuilderResult(
        generated=generated,
        extracted_params={"project_type": ptype, "size_category": size},
        interpretation=f"Keyword-based interpretation: {ptype} project, {size} size",
        methodology="Keyword-based fallback (no Claude API available)",
        summary={
            "description": description[:200],
            "activity_count": generated.activity_count,
            "predicted_duration_days": generated.predicted_duration_days,
        },
    )
