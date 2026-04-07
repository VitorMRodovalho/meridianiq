# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Shared test configuration.

Forces the ENVIRONMENT to ``development`` so tests always use
the InMemoryStore backend.  Auto-generates synthetic XER test
fixtures if they don't exist (they are gitignored).
"""

import os
from pathlib import Path

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
