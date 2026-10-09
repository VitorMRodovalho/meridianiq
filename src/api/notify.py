# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Email the operator through Resend.

Shared by the new-account alert (``routers/hooks.py``) and the AI access
request alert (``ai_gate.request_access``). Configuration:

* ``RESEND_API_KEY``: sending-only API key.
* ``SIGNUP_ALERT_TO``: the operator's address (kept out of the repository).
* ``SIGNUP_ALERT_FROM``: sender; defaults to Resend's onboarding sender.

Messages carry no personal data of the user they are about (no address, no
user id, no free text): Resend is a processor outside Brazil (LGPD art. 33),
and the operator reads the details in the app. Delivery is best effort: a
failure is logged, never raised, and a task queued on a machine that stops
is lost, so the app's pages, not the email, are the record.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
DEFAULT_FROM = "MeridianIQ <onboarding@resend.dev>"
# Resend sits behind Cloudflare, which rejects urllib's default agent (403, 1010).
USER_AGENT = "meridianiq-operator-alert/1.0"


def send_resend_email(
    api_key: str,
    sender: str,
    recipient: str,
    alert: dict[str, str],
    *,
    label: str,
    user_agent: str,
    log: logging.Logger,
) -> None:
    """Send one plain-text email. Failures are logged by ``log``, never raised.

    Failures log only a status code or an error class: never the message,
    which could echo the request, and never at error level, which an error
    tracker would capture together with the request scope.
    """
    payload = json.dumps(
        {"from": sender, "to": [recipient], "subject": alert["subject"], "text": alert["text"]}
    ).encode()
    request = urllib.request.Request(
        RESEND_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - fixed https URL
            try:
                message_id = json.loads(response.read() or b"{}").get("id", "?")
            except ValueError:
                message_id = "?"
            log.info("%s sent (status %s, id %s)", label, response.status, message_id)
    except urllib.error.HTTPError as exc:
        log.warning("%s failed: HTTP %s", label, exc.code)
    except Exception as exc:  # noqa: BLE001 - an alert failure must never surface
        log.warning("%s failed: %s", label, type(exc).__name__)


def notify_operator(alert: dict[str, str], *, label: str) -> None:
    """Email the operator, or do nothing when Resend or the recipient is not configured."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    recipient = os.environ.get("SIGNUP_ALERT_TO", "")
    if not (api_key and recipient):
        logger.info("%s not sent: operator email is not configured", label)
        return
    sender = os.environ.get("SIGNUP_ALERT_FROM", "") or DEFAULT_FROM
    send_resend_email(
        api_key, sender, recipient, alert, label=label, user_agent=USER_AGENT, log=logger
    )
