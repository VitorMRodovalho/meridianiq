# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Internal webhooks called by the platform, not by browsers.

``POST /api/v1/internal/hooks/auth-user-created`` is called by the
``notify_signup_alert`` trigger on ``INSERT`` into ``auth.users``
(migration 032) and emails the operator that a new account exists. The
trigger posts through ``pg_net``, which is asynchronous, and it sends only
the sign-in provider and creation time, so a slow or failing endpoint never
blocks signup and the full user row never leaves the database.

Configuration (the endpoint answers 404 until the first three are set):

* ``SIGNUP_WEBHOOK_SECRET``: shared secret the webhook sends in the
  ``X-Webhook-Secret`` header.
* ``RESEND_API_KEY``: sending-only API key for the Resend account.
* ``SIGNUP_ALERT_TO``: recipient address (kept out of the repository).
* ``SIGNUP_ALERT_FROM``: sender; defaults to Resend's onboarding sender,
  which can only deliver to the Resend account's own address.
* ``SIGNUP_ALERT_INCLUDE_EMAIL``: set to ``1`` to include the new user's
  email address in the alert (the trigger must then also send it). Off by
  default: the alert says that an account was created, and the dashboard
  says by whom. Turning it on sends the address to Resend, a processor
  outside Brazil (an LGPD art. 33 international transfer).
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["internal"])

_RESEND_URL = "https://api.resend.com/emails"
_DEFAULT_FROM = "MeridianIQ <onboarding@resend.dev>"
# Resend sits behind Cloudflare, which rejects urllib's default agent (403, 1010).
_USER_AGENT = "meridianiq-signup-alert/1.0"


def _configured() -> tuple[str, str, str] | None:
    secret = os.environ.get("SIGNUP_WEBHOOK_SECRET", "")
    api_key = os.environ.get("RESEND_API_KEY", "")
    recipient = os.environ.get("SIGNUP_ALERT_TO", "")
    if not (secret and api_key and recipient):
        return None
    return secret, api_key, recipient


def build_alert(record: dict[str, Any], *, include_email: bool) -> dict[str, str]:
    """Build the alert subject and text from the ``auth.users`` row.

    Only the sign-in provider and creation time are used, unless
    ``include_email`` is set.
    """
    app_meta = record.get("raw_app_meta_data")
    if not isinstance(app_meta, dict):
        app_meta = {}
    provider = str(app_meta.get("provider") or "unknown")
    created_at = _as_utc(record.get("created_at"))
    lines = [
        "A new MeridianIQ account was created.",
        "",
        f"Sign-in provider: {provider}",
        f"Created at (UTC): {created_at}",
    ]
    if include_email and record.get("email"):
        lines.append(f"Email: {record['email']}")
    lines += ["", "Details: Supabase dashboard > Authentication > Users."]
    return {"subject": "MeridianIQ: new account created", "text": "\n".join(lines)}


def _as_utc(value: Any) -> str:
    """Render a timestamp in UTC; fall back to the raw value if it does not parse."""
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return str(value) if value else "unknown time"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _send_via_resend(api_key: str, sender: str, recipient: str, alert: dict[str, str]) -> None:
    payload = json.dumps(
        {"from": sender, "to": [recipient], "subject": alert["subject"], "text": alert["text"]}
    ).encode()
    request = urllib.request.Request(
        _RESEND_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    # Failures log only a status code or an error class: never the message,
    # which could echo the request, and never at error level, which an error
    # tracker would capture together with the request scope.
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - fixed https URL
            try:
                message_id = json.loads(response.read() or b"{}").get("id", "?")
            except ValueError:
                message_id = "?"
            logger.info("signup alert sent (status %s, id %s)", response.status, message_id)
    except urllib.error.HTTPError as exc:
        logger.warning("signup alert failed: HTTP %s", exc.code)
    except Exception as exc:  # noqa: BLE001 - an alert failure must never surface to the webhook
        logger.warning("signup alert failed: %s", type(exc).__name__)


@router.post("/api/v1/internal/hooks/auth-user-created", status_code=202, include_in_schema=False)
async def auth_user_created(
    request: Request,
    background: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None),
) -> dict[str, str]:
    """Receive the Supabase ``auth.users`` INSERT webhook and email the operator."""
    config = _configured()
    if config is None:
        raise HTTPException(status_code=404, detail="Not Found")
    secret, api_key, recipient = config
    # Bytes comparison: a non-ASCII header must be a 401, not a TypeError (500).
    if not x_webhook_secret or not hmac.compare_digest(x_webhook_secret.encode(), secret.encode()):
        logger.warning("signup webhook rejected: bad or missing secret")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    if (body.get("type"), body.get("schema"), body.get("table")) != ("INSERT", "auth", "users"):
        return {"status": "ignored"}
    record = body.get("record")
    if not isinstance(record, dict):
        raise HTTPException(status_code=400, detail="Missing record")

    include_email = os.environ.get("SIGNUP_ALERT_INCLUDE_EMAIL", "") == "1"
    alert = build_alert(record, include_email=include_email)
    sender = os.environ.get("SIGNUP_ALERT_FROM", "") or _DEFAULT_FROM
    background.add_task(_send_via_resend, api_key, sender, recipient, alert)
    return {"status": "accepted"}
