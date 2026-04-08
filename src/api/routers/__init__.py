# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""FastAPI router registration.

Centralizes all sub-routers so ``app.py`` only needs to call
``include_all_routers(app)`` after creating the FastAPI instance.
"""

from __future__ import annotations

from fastapi import FastAPI


def include_all_routers(app: FastAPI) -> None:
    """Register every API router with the application."""
    from .health import router as health_router
    from .programs import router as programs_router
    from .projects import router as projects_router
    from .upload import router as upload_router
    from .evm import router as evm_router
    from .risk import router as risk_router
    from .tia import router as tia_router
    from .forensics import router as forensics_router
    from .cost import router as cost_router
    from .benchmarks import router as benchmarks_router
    from .admin import router as admin_router
    from .exports import router as exports_router
    from .analysis import router as analysis_router
    from .intelligence import router as intelligence_router
    from .whatif import router as whatif_router
    from .schedule_ops import router as schedule_ops_router
    from .comparison import router as comparison_router
    from .reports import router as reports_router

    app.include_router(health_router)
    app.include_router(upload_router)
    app.include_router(projects_router)
    app.include_router(programs_router)
    app.include_router(analysis_router)
    app.include_router(comparison_router)
    app.include_router(forensics_router)
    app.include_router(tia_router)
    app.include_router(evm_router)
    app.include_router(risk_router)
    app.include_router(intelligence_router)
    app.include_router(whatif_router)
    app.include_router(schedule_ops_router)
    app.include_router(cost_router)
    app.include_router(exports_router)
    app.include_router(benchmarks_router)
    app.include_router(reports_router)
    app.include_router(admin_router)
