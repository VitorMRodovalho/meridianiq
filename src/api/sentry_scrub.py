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


#: What an error report keeps of the request, on every route: the method and
#: the path. Headers go too, not only the SDK's sensitive ones: Fly-Client-IP
#: carries the client's address and is not on that list. So do cookies, the
#: environment, the query string and the body. PRIVACY.md §2 states this.
_KEPT_REQUEST_FIELDS = frozenset({"method", "url"})

#: Query data the SDK's HTTP integrations record on outgoing calls. The calls
#: to Supabase's REST API carry PostgREST filters there (``user_id=eq.<id>``,
#: and an address on the lookups by email), on spans and on breadcrumbs.
_QUERY_KEYS = ("http.query", "http.fragment")

#: An object path in a Supabase Storage URL: ``{user_id}/{upload_id}/{project
#: name}.xer``. It is on outgoing-call spans (description and url), on their
#: breadcrumbs, and in an HTTP error's message, so it is replaced wherever a
#: string in the event carries it. A project name is client data.
_STORAGE_OBJECT = re.compile(r"(/storage/v1/object/)[^'\"?#\r\n]+")

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


def _drop_query(data: Any) -> None:
    if not isinstance(data, dict):
        return
    for key in _QUERY_KEYS:
        data.pop(key, None)
    if isinstance(data.get("url"), str):
        data["url"] = data["url"].split("?", 1)[0]


def _drop_queries(event: dict[str, Any]) -> None:
    for span in event.get("spans") or []:
        if isinstance(span, dict):
            _drop_query(span.get("data"))
    _drop_query(((event.get("contexts") or {}).get("trace") or {}).get("data"))
    crumbs = event.get("breadcrumbs")
    values = crumbs.get("values") if isinstance(crumbs, dict) else crumbs
    for crumb in values or []:
        if isinstance(crumb, dict):
            _drop_query(crumb.get("data"))


def _redact_storage_paths(value: Any) -> Any:
    if isinstance(value, str):
        return _STORAGE_OBJECT.sub(r"\1{path}", value)
    if isinstance(value, dict):
        for key, item in value.items():
            value[key] = _redact_storage_paths(item)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = _redact_storage_paths(item)
    return value


def scrub_ai_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """Sentry ``before_send`` / ``before_send_transaction``: minimal request, no AI data.

    Every event keeps only the request's method and path (see
    ``_KEPT_REQUEST_FIELDS``), and loses the query strings of the outgoing
    calls recorded on its spans, trace context and breadcrumbs, and the
    object path of every Storage URL anywhere in it.

    On an AI route the request's own data is also in framework frames
    (FastAPI's body parsing, the threadpool, the rate limiter), so every
    frame loses its locals, not only ours.
    """
    request = event.get("request")
    if isinstance(request, dict):
        for field in [k for k in request if k not in _KEPT_REQUEST_FIELDS]:
            request.pop(field)
        if "url" in request:
            request["url"] = str(request["url"] or "").split("?", 1)[0]
    _drop_queries(event)
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
    _redact_storage_paths(event)
    return event
