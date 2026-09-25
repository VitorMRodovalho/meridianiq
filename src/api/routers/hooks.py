# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Internal webhooks called by the platform, not by browsers.

``POST /api/v1/internal/hooks/auth-user-created`` receives the Supabase
Database Webhook fired on ``INSERT`` into ``auth.users`` and emails the
operator that a new account exists. The webhook runs through ``pg_net``,
which is asynchronous, so a slow or failing endpoint never blocks signup.

Configuration (all optional; the endpoint answers 404 until the first two
are set, so an unconfigured deployment exposes nothing):

* ``SIGNUP_WEBHOOK_SECRET``: shared secret the webhook sends in the
  ``X-Webhook-Secret`` header.
* ``RESEND_API_KEY``: sending-only API key for the Resend account.
* ``SIGNUP_ALERT_TO``: recipient address (kept out of the repository).
* ``SIGNUP_ALERT_FROM``: sender; defaults to Resend's onboarding sender,
  which can only deliver to the Resend account's own address.
* ``SIGNUP_ALERT_INCLUDE_EMAIL``: set to ``1`` to include the new user's
  email address in the alert. Off by default: the alert says that an
  account was created, and the dashboard says by whom.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import urllib.request
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from ..deps import RATE_LIMIT_WRITE, limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["internal"])

_RESEND_URL = "https://api.resend.com/emails"
_DEFAULT_FROM = "MeridianIQ <onboarding@resend.dev>"


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
    app_meta = record.get("raw_app_meta_data") or {}
    provider = str(app_meta.get("provider") or "unknown")
    created_at = str(record.get("created_at") or "unknown time")
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


def _send_via_resend(api_key: str, sender: str, recipient: str, alert: dict[str, str]) -> None:
    payload = json.dumps(
        {"from": sender, "to": [recipient], "subject": alert["subject"], "text": alert["text"]}
    ).encode()
    request = urllib.request.Request(
        _RESEND_URL,
        data=payload,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - fixed https URL
            logger.info("signup alert sent (status %s)", response.status)
    except Exception as exc:  # noqa: BLE001 - an alert failure must never surface to the webhook
        logger.error("signup alert failed: %s", type(exc).__name__)


@router.post("/api/v1/internal/hooks/auth-user-created", status_code=202)
@limiter.limit(RATE_LIMIT_WRITE)
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
    if not x_webhook_secret or not hmac.compare_digest(x_webhook_secret, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(body, dict) or body.get("type") != "INSERT":
        return {"status": "ignored"}
    record = body.get("record")
    if not isinstance(record, dict):
        raise HTTPException(status_code=400, detail="Missing record")

    include_email = os.environ.get("SIGNUP_ALERT_INCLUDE_EMAIL", "") == "1"
    alert = build_alert(record, include_email=include_email)
    sender = os.environ.get("SIGNUP_ALERT_FROM", "") or _DEFAULT_FROM
    background.add_task(_send_via_resend, api_key, sender, recipient, alert)
    return {"status": "accepted"}
