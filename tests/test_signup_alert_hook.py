# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for the new-account email alert webhook (src/api/routers/hooks.py)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api import app as app_module
from src.api.routers import hooks

URL = "/api/v1/internal/hooks/auth-user-created"
SECRET = "test-webhook-secret"
NEW_USER = {
    "type": "INSERT",
    "table": "users",
    "schema": "auth",
    "record": {
        "id": "00000000-0000-4000-8000-0000000000c1",
        "email": "new.person@example.com",
        "created_at": "2026-09-25T13:38:00Z",
        "raw_app_meta_data": {"provider": "google"},
    },
    "old_record": None,
}


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Configure the alert and capture what would be sent to Resend."""
    monkeypatch.setenv("SIGNUP_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("SIGNUP_ALERT_TO", "operator@example.com")
    monkeypatch.delenv("SIGNUP_ALERT_INCLUDE_EMAIL", raising=False)
    calls: list[dict[str, Any]] = []

    def fake_send(api_key: str, sender: str, recipient: str, alert: dict[str, str]) -> None:
        calls.append({"api_key": api_key, "from": sender, "to": recipient, **alert})

    monkeypatch.setattr(hooks, "_send_via_resend", fake_send)
    return calls


@pytest.fixture
def client() -> TestClient:
    return TestClient(app_module.app)


def test_unconfigured_endpoint_is_not_found(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ("SIGNUP_WEBHOOK_SECRET", "RESEND_API_KEY", "SIGNUP_ALERT_TO"):
        monkeypatch.delenv(key, raising=False)
    response = client.post(URL, json=NEW_USER, headers={"X-Webhook-Secret": SECRET})
    assert response.status_code == 404


def test_wrong_or_missing_secret_is_rejected_and_sends_nothing(
    client: TestClient, sent: list[dict[str, Any]]
) -> None:
    assert client.post(URL, json=NEW_USER).status_code == 401
    assert client.post(URL, json=NEW_USER, headers={"X-Webhook-Secret": "nope"}).status_code == 401
    assert sent == []


def test_new_account_sends_one_alert_without_personal_data(
    client: TestClient, sent: list[dict[str, Any]]
) -> None:
    response = client.post(URL, json=NEW_USER, headers={"X-Webhook-Secret": SECRET})
    assert response.status_code == 202
    assert len(sent) == 1
    alert = sent[0]
    assert alert["to"] == "operator@example.com"
    assert alert["from"] == hooks._DEFAULT_FROM
    assert "google" in alert["text"]
    assert "2026-09-25T13:38:00Z" in alert["text"]
    assert "new.person@example.com" not in alert["text"]
    assert NEW_USER["record"]["id"] not in alert["text"]


def test_email_is_included_only_when_opted_in(
    client: TestClient, sent: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIGNUP_ALERT_INCLUDE_EMAIL", "1")
    client.post(URL, json=NEW_USER, headers={"X-Webhook-Secret": SECRET})
    assert "new.person@example.com" in sent[0]["text"]


def test_non_insert_events_are_ignored(client: TestClient, sent: list[dict[str, Any]]) -> None:
    update = {**NEW_USER, "type": "UPDATE"}
    response = client.post(URL, json=update, headers={"X-Webhook-Secret": SECRET})
    assert response.status_code == 202
    assert response.json() == {"status": "ignored"}
    assert sent == []


def test_resend_failure_never_reaches_the_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    """A network error while emailing is logged, not raised."""

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise OSError("network down")

    monkeypatch.setattr(hooks.urllib.request, "urlopen", boom)
    hooks._send_via_resend(
        "re_test", "a@example.com", "b@example.com", {"subject": "s", "text": "t"}
    )


def test_resend_request_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """The request carries the bearer key and the JSON body Resend expects."""
    import json

    captured: dict[str, Any] = {}

    class _Resp:
        status = 200

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    def fake_urlopen(request: Any, timeout: float) -> _Resp:
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return _Resp()

    monkeypatch.setattr(hooks.urllib.request, "urlopen", fake_urlopen)
    hooks._send_via_resend("re_key", "from@x", "to@x", {"subject": "S", "text": "T"})
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["auth"] == "Bearer re_key"
    assert captured["body"] == {"from": "from@x", "to": ["to@x"], "subject": "S", "text": "T"}
    assert captured["timeout"] == 5
