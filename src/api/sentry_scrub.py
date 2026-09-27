# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Keep AI prompts, questions and operator request bodies out of error reports.

Sentry captures the local variables of every frame and the request body by
default. In the AI path those hold the user's question, the schedule
summary sent to the model, and, on the operator routes, email addresses.
``scrub_ai_event`` is the ``before_send`` hook: it drops the locals of AI
frames and the body of AI requests, and leaves every other event as it is.

No imports from the application: ``src/api/app.py`` uses this before the
rest of the app is imported.
"""

from __future__ import annotations

from typing import Any

#: Modules whose frames never keep their locals.
AI_MODULES = frozenset({"src.api.ai_gate", "src.api.routers.ai", "src.analytics.nlp_query"})
#: Single functions elsewhere that handle AI input.
AI_FUNCTIONS = frozenset({("src.api.routers.intelligence", "ask_schedule")})


def _is_ai_path(url: str) -> bool:
    path = url.split("?", 1)[0].rstrip("/")
    return path.endswith("/ask") or path.endswith("/ai/status") or "/superadmin/ai" in path


def _scrub_frames(frames: Any) -> None:
    for frame in frames or []:
        module = frame.get("module")
        if module in AI_MODULES or (module, frame.get("function")) in AI_FUNCTIONS:
            frame.pop("vars", None)


def scrub_ai_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """Sentry ``before_send``: strip AI frame locals and AI request bodies."""
    for key in ("exception", "threads"):
        for value in (event.get(key) or {}).get("values") or []:
            _scrub_frames((value.get("stacktrace") or {}).get("frames"))
    request = event.get("request")
    if isinstance(request, dict) and _is_ai_path(str(request.get("url") or "")):
        request.pop("data", None)
    return event
