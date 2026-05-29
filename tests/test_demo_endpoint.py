# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the public, no-auth demo endpoint.

Regression coverage for the landing-page "Try with sample data" flow
(GET /api/v1/demo/project). The endpoint previously shipped as dead code
that 500'd on every call (wrong class names + signatures + field names);
these tests lock the working contract the frontend consumes and ensure it
never silently breaks again.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.routers.upload import _demo_sample_path


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_demo_sample_path_resolves_inside_package() -> None:
    """Prod-shipping guard: the demo fixture must live inside the package
    (src/api/demo_data/, shipped by the Dockerfile's `COPY src/ src/`), NOT
    under tests/ (never copied into the image). A missing asset here means
    the public /demo endpoint 404s in production."""
    path = _demo_sample_path()
    assert path.exists(), f"demo fixture missing at {path}"
    assert "demo_data" in path.parts
    assert "tests" not in path.parts


def test_demo_asset_matches_generated_fixture(tmp_path: Path) -> None:
    """The shipped demo fixture must stay byte-identical to the (deterministic)
    synthetic generator, so editing the generator can't silently leave the prod
    demo on stale data."""
    from tests.fixtures.sample_xer_generator import generate_sample_xer

    generated = generate_sample_xer(tmp_path / "sample.xer")
    assert generated.read_bytes() == _demo_sample_path().read_bytes(), (
        "src/api/demo_data/sample.xer drifted from the generator — regenerate via "
        "tests.fixtures.sample_xer_generator.generate_sample_xer("
        "'src/api/demo_data/sample.xer')"
    )


def test_demo_project_returns_200_without_auth(client: TestClient) -> None:
    """The demo endpoint must work with NO authentication (it is the
    zero-friction, no-login front door)."""
    resp = client.get("/api/v1/demo/project")
    assert resp.status_code == 200, resp.text


def test_demo_project_contract_shape(client: TestClient) -> None:
    """The response shape must match what web/src/routes/demo/+page.svelte
    consumes (DemoProjectResponse)."""
    data = client.get("/api/v1/demo/project").json()

    # project block
    project = data["project"]
    assert isinstance(project["name"], str) and project["name"]
    for key in ("activity_count", "relationship_count", "calendar_count", "wbs_count"):
        assert isinstance(project[key], int)
    assert project["activity_count"] > 0

    # validation block (DCMA 14-Point)
    validation = data["validation"]
    assert 0.0 <= validation["overall_score"] <= 100.0
    assert isinstance(validation["passed_count"], int)
    assert isinstance(validation["failed_count"], int)
    assert validation["metrics"], "expected non-empty DCMA metrics"
    metric = validation["metrics"][0]
    for key in ("number", "name", "value", "threshold", "unit", "passed", "direction"):
        assert key in metric, f"metric missing key {key}"
    assert validation["passed_count"] + validation["failed_count"] == len(validation["metrics"])

    # critical path block
    cp = data["critical_path"]
    assert isinstance(cp["length"], int)
    assert isinstance(cp["activities"], list)
    assert len(cp["activities"]) <= 20  # endpoint caps the preview at 20
    if cp["activities"]:
        act = cp["activities"][0]
        for key in ("task_code", "task_name", "total_float"):
            assert key in act, f"critical-path activity missing key {key}"


def test_demo_project_is_deterministic(client: TestClient) -> None:
    """Memoized payload must be stable across calls (same immutable fixture)."""
    first = client.get("/api/v1/demo/project").json()
    second = client.get("/api/v1/demo/project").json()
    assert first == second
