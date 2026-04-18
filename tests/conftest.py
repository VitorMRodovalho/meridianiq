# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Shared test configuration.

Forces the ENVIRONMENT to ``development`` so tests always use
the InMemoryStore backend.  Auto-generates synthetic XER test
fixtures if they don't exist (they are gitignored).
"""

import os
from pathlib import Path

import pytest

os.environ["ENVIRONMENT"] = "development"
os.environ["SUPABASE_JWT_SECRET"] = "test-secret"
os.environ["RATE_LIMIT_ENABLED"] = "false"

# Auto-generate synthetic XER fixtures (gitignored via *.xer)
_fixtures_dir = Path(__file__).parent / "fixtures"

if not (_fixtures_dir / "sample.xer").exists():
    from tests.fixtures.sample_xer_generator import generate_sample_xer

    generate_sample_xer()

if not (_fixtures_dir / "sample_update.xer").exists():
    from tests.fixtures.sample_update_generator import generate_sample_update_xer

    generate_sample_update_xer()

if not (_fixtures_dir / "sample_update2.xer").exists():
    from tests.fixtures.sample_update2_generator import generate_sample_update2_xer

    generate_sample_update2_xer()


@pytest.fixture(autouse=True)
def _reset_kpi_cache() -> None:
    """InMemoryStore reuses sequential project_ids (proj-0001, proj-0002...)
    and resets the counter on ``clear()``. Without flushing the API-level KPI
    cache between tests, a fresh schedule under a re-issued project_id would
    receive a stale bundle from the previous test. Production uses
    Supabase-generated UUIDs so this collision can't happen there.
    """
    from src.api.cache import invalidate_namespace

    invalidate_namespace("schedule:kpis")
