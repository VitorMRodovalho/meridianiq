# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Fakes for the AI gate: a provider client that never leaves the process.

``enable_ai`` turns the gate on for one test with a complete, valid
configuration and a fake client. The prices and budget are arbitrary test
values, not the provider's prices.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.api import ai_gate

MODEL = "test-model"

AI_ENV = {
    "AI_ENABLED": "1",
    "ANTHROPIC_API_KEY": "sk-test-not-a-real-key",
    "AI_MODEL": MODEL,
    "AI_PRICE_INPUT_USD_PER_MTOK": "3",
    "AI_PRICE_OUTPUT_USD_PER_MTOK": "15",
    "AI_GLOBAL_MONTHLY_BUDGET_USD": "50",
}


@dataclass
class FakeUsage:
    input_tokens: int = 1200
    output_tokens: int = 300
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class FakeBlock:
    text: str
    type: str = "text"


@dataclass
class FakeResponse:
    content: list[FakeBlock]
    usage: FakeUsage | None


class FakeProviderError(Exception):
    """Shaped like the SDK's APIStatusError: a status code and a response."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"provider answered {status_code}")
        self.status_code = status_code
        self.response = object()


class _Messages:
    def __init__(self, owner: FakeClient) -> None:
        self._owner = owner

    def create(self, **kwargs: Any) -> FakeResponse:
        owner = self._owner
        owner.calls.append(kwargs)
        message = kwargs["messages"][0]["content"]
        owner.questions.append(message.rsplit("Question: ", 1)[-1])
        if owner.raise_exc is not None:
            raise owner.raise_exc
        return FakeResponse(content=[FakeBlock(owner.answer)], usage=owner.usage)


@dataclass
class FakeClient:
    """Records every call; answers with ``answer`` and ``usage``, or raises ``raise_exc``."""

    questions: list[str] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    answer: str = "stub answer"
    usage: FakeUsage | None = field(default_factory=FakeUsage)
    raise_exc: BaseException | None = None

    def __post_init__(self) -> None:
        self.messages = _Messages(self)


def enable_ai(
    monkeypatch: pytest.MonkeyPatch,
    *,
    questions: list[str] | None = None,
    durable: bool = True,
) -> FakeClient:
    """Turn the gate on for this test and return the fake client it will use."""
    for key, value in AI_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(ai_gate, "sdk_available", lambda: True)
    if durable:
        monkeypatch.setattr(ai_gate, "ledger_is_durable", lambda store: True)
    client = FakeClient() if questions is None else FakeClient(questions=questions)
    monkeypatch.setattr(ai_gate, "make_client", lambda config: client)
    return client
