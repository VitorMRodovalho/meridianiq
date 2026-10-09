# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Keep AI prompts, questions and operator request bodies out of error reports.

Sentry captures the local variables of every frame and the request body by
default, and attaches the body to sampled performance transactions too. In
the AI path those hold the user's question, the schedule summary sent to the
model, an access request's note, and, on the operator routes, email
addresses, and they sit in the framework's frames as well as ours.
``scrub_ai_event`` is both the ``before_send`` and the
``before_send_transaction`` hook: for a request to an AI route it drops the
locals of EVERY frame and the request body; for any other event it drops the
locals of the AI modules' frames only; everything else stays as it is.

No imports from the application: ``src/api/app.py`` uses this before the
rest of the app is imported.
"""

from __future__ import annotations

import re
from typing import Any

#: Modules whose frames never keep their locals.
AI_MODULES = frozenset({"src.api.ai_gate", "src.api.routers.ai", "src.analytics.nlp_query"})
#: Single functions elsewhere that handle AI input, a request note or an address.
AI_FUNCTIONS = frozenset(
    {("src.api.routers.intelligence", "ask_schedule")}
    | {
        ("src.database.store", name)
        for name in (
            "ai_request_access",
            "ai_pending_requests",
            "ai_approve_request",
            "ai_dismiss_request",
            "ai_grant",
            "ai_revoke",
            "user_id_for_email",
            "ai_access_state",
            "ai_forget_user",
            "_rpc_bool",
        )
    }
)


_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _is_ai_path(url: str) -> bool:
    path = url.split("?", 1)[0].rstrip("/")
    return path.endswith("/ask") or "/ai/" in path or path.endswith("/superadmin/ai")


def _scrub_frames(frames: Any) -> None:
    for frame in frames or []:
        module = frame.get("module")
        if module in AI_MODULES or (module, frame.get("function")) in AI_FUNCTIONS:
            frame.pop("vars", None)


def _drop_all_locals(frames: Any) -> None:
    for frame in frames or []:
        frame.pop("vars", None)


def scrub_ai_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """Sentry ``before_send`` / ``before_send_transaction``: strip AI data.

    On an AI route the request's own data is also in framework frames
    (FastAPI's body parsing, the threadpool, the rate limiter), so every
    frame loses its locals, not only ours.
    """
    request = event.get("request")
    ai_request = isinstance(request, dict) and _is_ai_path(str(request.get("url") or ""))
    for key in ("exception", "threads"):
        for value in (event.get(key) or {}).get("values") or []:
            frames = (value.get("stacktrace") or {}).get("frames")
            if ai_request:
                _drop_all_locals(frames)
            else:
                _scrub_frames(frames)
    if ai_request and isinstance(request, dict):
        request.pop("data", None)
        # The operator routes carry the requester's id in the path.
        request["url"] = _UUID.sub("{id}", str(request.get("url") or ""))
        # Log lines recorded during the request are not scrubbed: drop them.
        event.pop("breadcrumbs", None)
    return event
