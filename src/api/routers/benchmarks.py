# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Benchmarks router — contribute, compare, and summarize benchmark data."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth import optional_auth
from ..deps import get_store
from ..schemas import (
    BenchmarkCompareResponse,
    BenchmarkSummaryResponse,
    PercentileRankingSchema,
)

router = APIRouter()

# In-memory benchmark store (persisted via Supabase when available)
_benchmark_dataset: list[Any] = []


@router.post("/api/v1/benchmarks/contribute")
def contribute_benchmark(
    project_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """Contribute anonymized schedule metrics to the benchmark database.

    Extracts aggregate metrics (DCMA scores, float distributions, activity
    counts) from the specified project.  No activity names, WBS text, or
    identifying data is stored.

    Args:
        project_id: The project to extract metrics from.

    Returns:
        Extracted benchmark metrics (anonymized).
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from src.analytics.benchmarks import extract_benchmark_metrics

    metrics = extract_benchmark_metrics(schedule)
    _benchmark_dataset.append(metrics)
    return asdict(metrics)


@router.get(
    "/api/v1/benchmarks/compare/{project_id}",
    response_model=BenchmarkCompareResponse,
)
def compare_benchmark(
    project_id: str,
    filter_size: bool = True,
    _user: object = Depends(optional_auth),
) -> BenchmarkCompareResponse:
    """Compare a project's metrics against the benchmark dataset.

    Returns percentile rankings for key schedule quality metrics
    relative to other contributed projects.

    Args:
        project_id: The project to compare.
        filter_size: If True, compare only against same size category.
    """
    store = get_store()
    schedule = store.get(project_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from src.analytics.benchmarks import compare_to_benchmarks

    result = compare_to_benchmarks(schedule, _benchmark_dataset, filter_size=filter_size)

    return BenchmarkCompareResponse(
        rankings=[
            PercentileRankingSchema(
                metric_name=r.metric_name,
                value=r.value,
                percentile=r.percentile,
                benchmark_mean=r.benchmark_mean,
                benchmark_median=r.benchmark_median,
                benchmark_count=r.benchmark_count,
                interpretation=r.interpretation,
            )
            for r in result.rankings
        ],
        overall_percentile=result.overall_percentile,
        benchmark_count=result.benchmark_count,
        size_category=result.size_category,
        project_dcma_score=result.project_metrics.dcma_score,
        project_activity_count=result.project_metrics.activity_count,
        summary=result.summary,
    )


@router.get(
    "/api/v1/benchmarks/summary",
    response_model=BenchmarkSummaryResponse,
)
def get_benchmark_summary(
    _user: object = Depends(optional_auth),
) -> BenchmarkSummaryResponse:
    """Get aggregate statistics of the benchmark dataset.

    Returns total projects, size distribution, and average metrics.
    """
    import statistics as stats

    from src.analytics.benchmarks import BenchmarkMetrics

    dataset: list[BenchmarkMetrics] = _benchmark_dataset

    if not dataset:
        return BenchmarkSummaryResponse()

    size_dist: dict[str, int] = {}
    for b in dataset:
        size_dist[b.size_category] = size_dist.get(b.size_category, 0) + 1

    return BenchmarkSummaryResponse(
        total_projects=len(dataset),
        size_distribution=size_dist,
        avg_dcma_score=round(stats.mean(b.dcma_score for b in dataset), 1),
        avg_activity_count=round(stats.mean(b.activity_count for b in dataset), 0),
        avg_relationship_density=round(stats.mean(b.relationship_density for b in dataset), 2),
    )
