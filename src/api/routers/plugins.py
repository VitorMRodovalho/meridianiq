# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""HTTP surface for the plugin registry.

Exposes the in-process registry from :mod:`src.plugins` over the API so
operators can discover what's installed and run plugins against stored
schedules without writing their own Python.

Endpoints:

* ``GET  /api/v1/plugins`` — list registered plugins
* ``POST /api/v1/plugins/{name}/run/{project_id}`` — invoke one plugin
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.plugins import get_plugin, list_plugins

from ..auth import optional_auth
from ..deps import get_store

router = APIRouter()


@router.get("/api/v1/plugins")
def list_registered_plugins(_user: object = Depends(optional_auth)) -> dict:
    """Return every plugin currently in the registry (sorted by name)."""
    return {
        "plugins": [
            {"name": p.name, "version": p.version, "entry_point": p.entry_point}
            for p in list_plugins()
        ]
    }


@router.post("/api/v1/plugins/{name}/run/{project_id}")
def run_plugin(
    name: str,
    project_id: str,
    _user: object = Depends(optional_auth),
) -> dict:
    """Run one registered plugin against a stored schedule.

    Returns the plugin's raw dict result wrapped under ``{plugin, result}``.
    A plugin error becomes HTTP 500 with the exception text — the host
    process is never affected.
    """
    record = get_plugin(name)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {name}")

    user_id = _user["id"] if _user else None  # type: ignore[index]
    store = get_store()
    schedule = store.get(project_id, user_id=user_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    try:
        result = record.instance.analyze(schedule)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Plugin {name!r} raised: {exc}") from exc

    return {
        "plugin": {"name": record.name, "version": record.version},
        "result": result,
    }
