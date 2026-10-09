# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""AI access gate: who may call the LLM, how much, and what each call cost.

Owner rule (2026-09-27): the AI feature is not available to free or
non-approved accounts. When it is released, it is limited and controlled,
because the operator pays for the tokens. This module is the only one that
may build a model client (:func:`make_client`); ``tests/test_ai_gate.py``
checks that no other module imports the SDK.

Layers, each failing closed:

1. Configuration, read on every request. AI is on only with ``AI_ENABLED=1``
   (the kill switch), ``ANTHROPIC_API_KEY``, an explicit ``AI_MODEL`` with
   both prices (``AI_PRICE_INPUT_USD_PER_MTOK`` /
   ``AI_PRICE_OUTPUT_USD_PER_MTOK``) stated for that same model
   (``AI_PRICED_MODEL``) and within plausible bounds,
   ``AI_GLOBAL_MONTHLY_BUDGET_USD``, the ``anthropic`` SDK importable, and,
   in production, a ledger that survives restarts and is shared by every
   machine. Anything missing means ``ai_disabled`` for everyone. On Fly a
   changed variable takes effect only after a restart; the fastest stop is
   disabling the key in the provider's console.
2. Entitlement: an active ``ai_entitlements`` row, granted by an operator
   listed in ``SUPERADMIN_USER_IDS``.
3. Limits: questions per UTC day and USD per UTC month for each account,
   and USD per UTC month for all accounts. ``ai_reserve`` (migration 035)
   enforces them on a reservation of the call's worst-case cost, taken
   before the call.
4. One call: a single attempt with a bounded timeout. The reservation is
   settled with the provider's reported usage in a ``finally``.

A fifth layer, the spend limit of the API key's workspace at the provider,
lives outside this code.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from typing import Any, Literal

from fastapi import BackgroundTasks, HTTPException, Request

from src.analytics import nlp_query
from src.database.config import settings

from .access import Principal
from .deps import trusted_client_ip
from .notify import notify_operator

logger = logging.getLogger(__name__)

Reason = Literal[
    "ai_disabled",
    "ai_not_entitled",
    "ai_session_required",
    "ai_daily_quota",
    "ai_account_budget",
    "ai_global_budget",
]

#: Longest answer the model may generate, in tokens.
MAX_OUTPUT_TOKENS = 1024
#: Largest prompt (system + message, UTF-8 bytes) the gate will send.
MAX_PROMPT_BYTES = 16_000
#: Tokens added on top of the prompt bytes for message framing.
PROMPT_OVERHEAD_TOKENS = 64
#: Seconds the single provider request may take, and the connect part of it.
#: Kept well under the browser's wait for /ask (ASK_TIMEOUT_MS = 90 s in
#: web/src/lib/api.ts), which also covers the schedule load and the ledger
#: round trips: a call the browser stopped waiting for is still billed.
REQUEST_TIMEOUT_S = 45.0
CONNECT_TIMEOUT_S = 5.0

DEFAULT_DAILY_QUESTIONS = 20
DEFAULT_ACCOUNT_MONTHLY_BUDGET_USD = Decimal("5")

#: Plausible range of a price per million tokens. A price typed per thousand
#: tokens, or per token, falls below it; one typed a thousand times too high
#: falls above it. Either way the prices are treated as not set.
PRICE_MIN_USD_PER_MTOK = Decimal("0.01")
PRICE_MAX_USD_PER_MTOK = Decimal("1000")
#: Prompt size used to show the operator what one question reserves.
TYPICAL_PROMPT_BYTES = 4_000

#: Pending access requests listed on the operator page (the total is reported too).
REQUESTS_PAGE = 200
#: Request states the closed /ask panel knows how to show (migration 036).
ACCESS_STATES = frozenset({"entitled", "pending", "dismissed", "none"})
#: Reasons for which the /ask panel offers or shows an access request.
REQUESTABLE_REASONS = frozenset({"ai_disabled", "ai_not_entitled"})
#: At most this many operator emails per rolling hour for new requests, over
#: all accounts and machines (counted in the table). Requests above it are
#: still recorded and listed on /admin/ai. ``AI_REQUEST_ALERTS_PER_HOUR``
#: overrides it; 0 sends none.
REQUEST_ALERTS_PER_HOUR = 10

# The operator's alert carries nothing about the requester (no address, id or
# note): they are on /admin/ai. See src/api/notify.py.
_REQUEST_ALERT = {
    "subject": "MeridianIQ: new AI access request",
    "text": (
        "An account asked for access to the AI assistant (Ask Your Schedule).\n\n"
        "Review it on the AI admin page of MeridianIQ: /admin/ai"
    ),
}

_MTOK = Decimal(1_000_000)
_MICRO_USD = Decimal("0.000001")

_MESSAGES: dict[str, str] = {
    "ai_disabled": "The AI assistant is not available.",
    "ai_not_entitled": "The AI assistant is available to approved beta accounts only.",
    "ai_session_required": "The AI assistant requires a signed-in session.",
    "ai_daily_quota": "Daily question limit reached.",
    "ai_account_budget": "Monthly AI limit reached for this account.",
    "ai_global_budget": "The AI assistant is paused.",
    "ai_prompt_too_large": "The question is too long.",
    "ai_upstream_failed": "The AI answer failed.",
    "ai_ledger_unavailable": "The AI assistant is unavailable.",
    "ai_account_not_found": "No account uses this address.",
    "ai_entitlement_not_found": "This account has no active AI access.",
    "ai_request_unavailable": "Access requests are unavailable right now.",
    "ai_request_not_found": "This request is no longer pending.",
    "superadmin_required": "SuperAdmin access required",
}

_REFUSAL_STATUS: dict[str, int] = {
    "ai_disabled": 403,
    "ai_not_entitled": 403,
    "ai_session_required": 403,
    "ai_daily_quota": 429,
    "ai_account_budget": 429,
    "ai_global_budget": 429,
}


def error(status_code: int, code: str, headers: dict[str, str] | None = None) -> HTTPException:
    """An HTTPException in the ``{"error_code", "message"}`` shape the frontend reads."""
    return HTTPException(
        status_code=status_code,
        detail={"error_code": code, "message": _MESSAGES.get(code, code)},
        headers=headers,
    )


# ── Configuration ───────────────────────────────────────


def _positive_decimal(name: str) -> Decimal | None:
    raw = os.environ.get(name, "").strip()
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if value.is_finite() and value > 0 else None


def _default_int(name: str, default: int) -> int:
    """An override of a default limit; an unreadable value denies (0)."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s=%r is not an integer; using 0", name, raw)
        return 0
    return max(value, 0)


def _default_decimal(name: str, default: Decimal) -> Decimal:
    """An override of a default budget; an unreadable value denies (0)."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = Decimal(raw)
    except InvalidOperation:
        value = Decimal(-1)
    if not value.is_finite() or value < 0:
        logger.warning("%s=%r is not a non-negative amount; using 0", name, raw)
        return Decimal(0)
    return value


def sdk_available() -> bool:
    """True when the provider SDK imports (the image may not ship it)."""
    if importlib.util.find_spec("anthropic") is None:
        return False
    try:
        import anthropic  # noqa: F401
    except Exception:
        logger.exception("the anthropic SDK is installed but does not import")
        return False
    return True


def _prices() -> tuple[Decimal | None, Decimal | None]:
    """Both prices, or ``(None, None)`` when they cannot be trusted.

    They must be stated for the configured model (``AI_PRICED_MODEL`` equal
    to ``AI_MODEL``), so changing the model without the prices disables AI
    instead of mis-costing every call, and each must lie in the plausible
    range, with output not cheaper than input.
    """
    model = os.environ.get("AI_MODEL", "").strip()
    priced_for = os.environ.get("AI_PRICED_MODEL", "").strip()
    price_in = _positive_decimal("AI_PRICE_INPUT_USD_PER_MTOK")
    price_out = _positive_decimal("AI_PRICE_OUTPUT_USD_PER_MTOK")
    if not model or priced_for != model or price_in is None or price_out is None:
        return None, None
    in_range = all(
        PRICE_MIN_USD_PER_MTOK <= price <= PRICE_MAX_USD_PER_MTOK for price in (price_in, price_out)
    )
    if not in_range or price_out < price_in:
        logger.warning("AI prices outside the plausible range; AI stays disabled")
        return None, None
    return price_in, price_out


def ledger_is_durable(store: Any) -> bool:
    """True when the spend ledger survives restarts and is shared by machines.

    Outside production any store will do. In production only the Supabase
    store qualifies: the in-memory one is per process and starts empty after
    every deploy, which would hand every quota back.
    """
    if settings.ENVIRONMENT != "production":
        return True
    from src.database.store import SupabaseStore

    return isinstance(store, SupabaseStore)


@dataclass(frozen=True)
class AIConfig:
    """The AI configuration of one request (see the module docstring).

    Holds whether the API key is set, never the key: this object is a local
    in the frames an error report may capture. Only :func:`make_client`
    reads the key, straight from the environment.
    """

    enabled: bool
    api_key_set: bool
    model: str
    price_input: Decimal | None
    price_output: Decimal | None
    global_budget: Decimal | None
    default_daily: int
    default_account_budget: Decimal
    sdk_available: bool
    durable_ledger: bool

    def flags(self) -> dict[str, bool]:
        """Which requirement is met; never the values."""
        return {
            "enabled": self.enabled,
            "api_key_set": self.api_key_set,
            "model_set": bool(self.model),
            "prices_set": self.price_input is not None and self.price_output is not None,
            "global_budget_set": self.global_budget is not None,
            "sdk_available": self.sdk_available,
            "durable_ledger": self.durable_ledger,
        }

    @property
    def ready(self) -> bool:
        return all(self.flags().values())


def load_config(store: Any) -> AIConfig:
    """Read the AI configuration from the environment, now."""
    price_input, price_output = _prices()
    return AIConfig(
        enabled=os.environ.get("AI_ENABLED", "").strip() == "1",
        api_key_set=bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
        model=os.environ.get("AI_MODEL", "").strip(),
        price_input=price_input,
        price_output=price_output,
        global_budget=_positive_decimal("AI_GLOBAL_MONTHLY_BUDGET_USD"),
        default_daily=_default_int("AI_DEFAULT_DAILY_QUESTIONS", DEFAULT_DAILY_QUESTIONS),
        default_account_budget=_default_decimal(
            "AI_DEFAULT_ACCOUNT_MONTHLY_BUDGET_USD", DEFAULT_ACCOUNT_MONTHLY_BUDGET_USD
        ),
        sdk_available=sdk_available(),
        durable_ledger=ledger_is_durable(store),
    )


def make_client(config: AIConfig) -> Any:
    """Build the model client: one attempt per call, bounded in time.

    ``config`` must be ready (``config.ready``); the key is read here, from
    the environment, and nowhere else.

    The SDK retries twice by default, and a retry after a read timeout can
    bill a call the provider already answered, so retries are off.
    """
    import anthropic

    # The SDK's own Timeout: 1.x moved to httpx2 and rejects an httpx.Timeout.
    return anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        max_retries=0,
        timeout=anthropic.Timeout(REQUEST_TIMEOUT_S, connect=CONNECT_TIMEOUT_S),
    )


# ── Status ──────────────────────────────────────────────


def _next_utc_midnight(now: datetime) -> datetime:
    day = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return day + timedelta(days=1)


def _next_utc_month(now: datetime) -> datetime:
    first = now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (first + timedelta(days=32)).replace(day=1)


@dataclass(frozen=True)
class AIStatus:
    """Whether a caller may ask now, and their daily counter."""

    available: bool
    reason: Reason | None
    daily_limit: int | None = None
    used_today: int | None = None
    remaining_today: int | None = None
    resets_at: str | None = None


def status_for(principal: Principal, store: Any, config: AIConfig | None = None) -> AIStatus:
    """The caller's AI status, computed with the ledger's own windows.

    The order hides what a caller has no business knowing: an account that
    is not entitled learns nothing about budgets.
    """
    if principal.kind != "user":
        return AIStatus(False, "ai_session_required")
    config = config or load_config(store)
    if not config.ready or config.global_budget is None:
        return AIStatus(False, "ai_disabled")
    try:
        q = store.ai_quota(principal.user_id, config.default_daily, config.default_account_budget)
    except Exception:
        logger.exception("ai_quota failed; reporting the AI assistant as disabled")
        return AIStatus(False, "ai_disabled")
    if not q.entitled:
        return AIStatus(False, "ai_not_entitled")
    reason: Reason | None = None
    if q.used_today >= q.daily_limit:
        reason = "ai_daily_quota"
    elif q.account_spent_usd >= q.account_budget_usd:
        reason = "ai_account_budget"
    elif q.global_spent_usd >= config.global_budget:
        reason = "ai_global_budget"
    return AIStatus(
        available=reason is None,
        reason=reason,
        daily_limit=q.daily_limit,
        used_today=q.used_today,
        remaining_today=max(q.daily_limit - q.used_today, 0),
        resets_at=_next_utc_midnight(datetime.now(UTC)).isoformat(),
    )


def refusal(reason: str) -> HTTPException:
    """The HTTP answer for a status that is not available."""
    headers = None
    now = datetime.now(UTC)
    if reason == "ai_daily_quota":
        headers = {"Retry-After": str(int((_next_utc_midnight(now) - now).total_seconds()) + 1)}
    elif reason in ("ai_account_budget", "ai_global_budget"):
        headers = {"Retry-After": str(int((_next_utc_month(now) - now).total_seconds()) + 1)}
    return error(_REFUSAL_STATUS.get(reason, 403), reason, headers)


# ── Cost ────────────────────────────────────────────────


def _usd(tokens: int, price_per_mtok: Decimal) -> Decimal:
    return Decimal(tokens) * price_per_mtok / _MTOK


def worst_case_cost(prompt_bytes: int, config: AIConfig) -> Decimal:
    """Upper bound of one call's cost, reserved before the call.

    Input tokens are bounded by the prompt's UTF-8 byte count: a byte-level
    tokenizer cannot produce more tokens than bytes. That is well founded for
    byte-level BPE and not verified for this provider, so every settled call
    logs its estimate against the real count, and a call that cost more than
    its reservation logs a warning.
    """
    if config.price_input is None or config.price_output is None:
        raise error(403, "ai_disabled")
    cost = _usd(prompt_bytes + PROMPT_OVERHEAD_TOKENS, config.price_input) + _usd(
        MAX_OUTPUT_TOKENS, config.price_output
    )
    return max(cost.quantize(_MICRO_USD, rounding=ROUND_CEILING), _MICRO_USD)


def cost_of(usage: nlp_query.ModelUsage, config: AIConfig) -> Decimal:
    """The cost of a call from the provider's reported usage.

    Every input token, cached or not, is priced as uncached input: the gate
    does not request prompt caching, so the cache counts are expected to be
    zero.
    """
    if config.price_input is None or config.price_output is None:
        raise error(403, "ai_disabled")
    input_tokens = (
        usage.input_tokens + usage.cache_creation_input_tokens + usage.cache_read_input_tokens
    )
    cost = _usd(input_tokens, config.price_input) + _usd(usage.output_tokens, config.price_output)
    return cost.quantize(_MICRO_USD, rounding=ROUND_CEILING)


def _outcome_of(exc: BaseException) -> str:
    """``failed`` when the provider answered with a 4xx, else ``unknown``.

    A 4xx answer means the request was rejected before generation. Anything
    else (timeout, lost connection, 5xx, an error without an answer) may
    have been billed, so the reservation keeps counting. Read from the
    error's ``status_code`` and ``response`` (the SDK's ``APIStatusError``
    carries both), so this needs no SDK import.
    """
    status = getattr(exc, "status_code", None)
    answered = getattr(exc, "response", None) is not None
    if answered and isinstance(status, int) and 400 <= status < 500:
        return "failed"
    return "unknown"


# ── The gated call ──────────────────────────────────────


@dataclass(frozen=True)
class AIAnswer:
    """What ``/ask`` returns."""

    answer: str
    model: str
    tokens_used: int
    remaining_today: int | None


def answer_question(
    *,
    principal: Principal,
    project_id: str,
    question: str,
    store: Any,
    load_schedule: Callable[[], Any],
) -> AIAnswer:
    """Answer one question about an authorized project, within the limits.

    ``project_id`` must already be authorized for ``principal``. Order:
    cheap status check (no schedule load) → load the schedule → bounded
    prompt → reserve → one call → settle → answer.
    """
    config = load_config(store)
    status = status_for(principal, store, config)
    if not status.available:
        raise refusal(status.reason or "ai_disabled")
    price_input, price_output = config.price_input, config.price_output
    global_budget = config.global_budget
    if price_input is None or price_output is None or global_budget is None:
        raise refusal("ai_disabled")

    schedule = load_schedule()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Project not found")

    system, message = nlp_query.build_prompt(schedule, question)
    prompt_bytes = len(system.encode("utf-8")) + len(message.encode("utf-8"))
    if prompt_bytes > MAX_PROMPT_BYTES:
        raise error(400, "ai_prompt_too_large")
    reserve_usd = worst_case_cost(prompt_bytes, config)

    try:
        client = make_client(config)
    except Exception as exc:
        logger.exception("could not build the model client")
        raise error(500, "ai_ledger_unavailable") from exc

    try:
        reservation_id, reason = store.ai_reserve(
            user_id=principal.user_id,
            project_id=project_id,
            reserve_usd=reserve_usd,
            default_daily=config.default_daily,
            default_account_usd=config.default_account_budget,
            global_budget_usd=global_budget,
            model=config.model,
            price_input=price_input,
            price_output=price_output,
        )
    except Exception as exc:
        logger.exception("ai_reserve failed; the model was not called")
        raise error(500, "ai_ledger_unavailable") from exc
    if reservation_id is None:
        raise refusal(reason or "ai_disabled")

    outcome = "unknown"
    usage: nlp_query.ModelUsage | None = None
    cost: Decimal | None = None
    started = time.monotonic()
    try:
        response = nlp_query.call_model(
            client,
            model=config.model,
            system=system,
            message=message,
            max_tokens=MAX_OUTPUT_TOKENS,
        )
    except Exception as exc:
        outcome = _outcome_of(exc)
        # ERROR, so it reaches the error tracker: a retired model or a revoked
        # key fails every call at no cost, and nobody would see it otherwise.
        # No exc_info: the frames hold the prompt.
        logger.error(
            "ai provider call failed: outcome=%s error=%s status=%s reservation=%s",
            outcome,
            type(exc).__name__,
            getattr(exc, "status_code", None),
            reservation_id,
        )
        raise error(502, "ai_upstream_failed") from exc
    else:
        usage = nlp_query.usage_of(response)
        if usage is not None:
            cost = cost_of(usage, config)
            outcome = "completed"
    finally:
        _settle(
            store,
            principal=principal,
            project_id=project_id,
            reservation_id=reservation_id,
            outcome=outcome,
            usage=usage,
            cost=cost,
            reserve_usd=reserve_usd,
            model=config.model,
            prompt_bytes=prompt_bytes,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    remaining = None
    if status.remaining_today is not None:
        remaining = max(status.remaining_today - 1, 0)
    return AIAnswer(
        answer=nlp_query.answer_text(response),
        model=config.model,
        tokens_used=(usage.input_tokens + usage.output_tokens) if usage else 0,
        remaining_today=remaining,
    )


def _settle(
    store: Any,
    *,
    principal: Principal,
    project_id: str,
    reservation_id: int,
    outcome: str,
    usage: nlp_query.ModelUsage | None,
    cost: Decimal | None,
    reserve_usd: Decimal,
    model: str,
    prompt_bytes: int,
    latency_ms: int,
) -> None:
    """Settle a reservation; a failure here is logged, never raised.

    The answer the provider already billed is still returned; the
    reservation, left unsettled, keeps counting at its worst case.
    """
    input_tokens = (
        usage.input_tokens + usage.cache_creation_input_tokens + usage.cache_read_input_tokens
        if usage
        else None
    )
    try:
        settled = store.ai_settle(
            reservation_id, outcome, input_tokens, usage.output_tokens if usage else None, cost
        )
        if not settled:
            logger.warning("ai reservation %s was not pending when settled", reservation_id)
    except Exception:
        logger.exception(
            "ai_settle failed; reservation %s keeps counting at %s USD", reservation_id, reserve_usd
        )
    if cost is not None and cost > reserve_usd:
        logger.warning(
            "ai call cost %s USD above its reservation %s USD (reservation %s, prompt %s bytes)",
            cost,
            reserve_usd,
            reservation_id,
            prompt_bytes,
        )
    # One line per call. The question is never logged.
    logger.info(
        "ai_call user=%s project=%s reservation=%s model=%s outcome=%s input_tokens=%s "
        "output_tokens=%s cost_usd=%s reserved_usd=%s prompt_bytes=%s latency_ms=%s",
        principal.user_id,
        project_id,
        reservation_id,
        model,
        outcome,
        input_tokens,
        usage.output_tokens if usage else None,
        cost,
        reserve_usd,
        prompt_bytes,
        latency_ms,
    )


# ── Operator ────────────────────────────────────────────


def is_ai_admin(principal: Principal) -> bool:
    """True for a signed-in session whose id is in ``SUPERADMIN_USER_IDS``.

    Only ids count: AI access spends money, and an address claim in a token
    is not proof the address was verified.
    """
    if principal.kind != "user":
        return False
    ids = {s.strip() for s in os.environ.get("SUPERADMIN_USER_IDS", "").split(",") if s.strip()}
    return principal.user_id in ids


def admin_report(store: Any, *, include_requests: bool = True) -> dict[str, Any]:
    """Configuration state, spend, entitlements and pending requests for the operator page.

    The configuration flags are reported even when the ledger cannot be
    read (migration 035 not applied, schema cache stale), so the operator
    can see which requirement is unmet. Pending requests are read
    separately: when they cannot be read, ``requests`` is ``None`` (never an
    empty list, which would read as "no requests") and the rest stands.
    """
    config = load_config(store)
    status: str | None = None if config.ready else "ai_disabled"
    try:
        report = store.ai_admin_report(config.default_daily, config.default_account_budget)
    except Exception:
        logger.exception("ai_admin_report failed")
        status = "ai_ledger_unavailable"
        report = {
            "global_spent_month_usd": Decimal(0),
            "month_calls": {"reserved": 0, "completed": 0, "failed": 0, "unknown": 0},
            "last_failure_at": None,
            "stale_reservations": 0,
            "entitlements": [],
        }
    if status is None and config.global_budget is not None:
        if report["global_spent_month_usd"] >= config.global_budget:
            status = "ai_global_budget"
    typical = None
    if config.price_input is not None and config.price_output is not None:
        typical = worst_case_cost(TYPICAL_PROMPT_BYTES, config)
    requests: list[dict[str, Any]] | None = None
    requests_total: int | None = None
    if include_requests:
        try:
            pending = store.ai_pending_requests(None, REQUESTS_PAGE)
            requests, requests_total = list(pending["items"]), int(pending["total"])
        except Exception as exc:
            logger.warning("ai_pending_requests failed: %s", type(exc).__name__)
    return {
        "available": status is None,
        "reason": status,
        "config": config.flags(),
        "model": config.model or None,
        "global_budget_usd": config.global_budget,
        "global_spent_month_usd": report["global_spent_month_usd"],
        "month_calls": report["month_calls"],
        "last_failure_at": report["last_failure_at"],
        "reserve_per_question_usd": typical,
        "defaults": {
            "daily_questions": config.default_daily,
            "account_monthly_budget_usd": config.default_account_budget,
        },
        "stale_reservations": report["stale_reservations"],
        "entitlements": report["entitlements"],
        "requests": requests,
        "requests_total": requests_total,
    }


def grant(
    store: Any,
    *,
    operator: Principal,
    email: str,
    daily_questions: int | None,
    monthly_budget_usd: Decimal | None,
    note: str | None,
    request: Request | None,
) -> dict[str, Any]:
    """Grant AI access to the account that owns ``email`` (a re-grant replaces it)."""
    address = email.strip().lower()
    user_id = store.user_id_for_email(address)
    if user_id is None:
        raise error(404, "ai_account_not_found")
    store.ai_grant(
        user_id=user_id,
        email=address,
        granted_by=operator.user_id,
        daily_questions=daily_questions,
        monthly_budget_usd=monthly_budget_usd,
        note=note,
        ip_address=trusted_client_ip(request),
        user_agent=request.headers.get("user-agent") if request is not None else None,
    )
    return _entitlement_row(store, user_id)


def _entitlement_row(store: Any, user_id: str) -> dict[str, Any]:
    for row in admin_report(store, include_requests=False)["entitlements"]:
        if str(row["user_id"]) == user_id:
            return dict(row)
    raise error(500, "ai_ledger_unavailable")


def revoke(store: Any, *, operator: Principal, user_id: str, request: Request | None) -> None:
    """Revoke an active entitlement, or 404 when there is none."""
    try:
        revoked = store.ai_revoke(
            user_id=user_id,
            revoked_by=operator.user_id,
            ip_address=trusted_client_ip(request),
            user_agent=request.headers.get("user-agent") if request is not None else None,
        )
    except Exception as exc:
        logger.warning("ai_revoke failed: %s", type(exc).__name__)
        raise error(500, "ai_ledger_unavailable") from exc
    if not revoked:
        raise error(404, "ai_entitlement_not_found")


# ── Access requests (migration 036) ─────────────────────


def access_for(principal: Principal, store: Any, reason: str | None) -> Any | None:
    """The caller's own request state for the closed /ask panel, or ``None``.

    Only for a signed-in user whose status is ``ai_disabled`` or
    ``ai_not_entitled``. A failed lookup (migration 036 not applied yet) is
    ``None``: the page then shows the plain panel. Logged without a stack,
    so every /ask visit does not become an error event.
    """
    if principal.kind != "user" or reason not in REQUESTABLE_REASONS:
        return None
    try:
        state = store.ai_access_state(principal.user_id)
    except Exception as exc:
        logger.warning("ai_access_state failed: %s", type(exc).__name__)
        return None
    return state if state.state in ACCESS_STATES else None


def request_access(
    principal: Principal,
    store: Any,
    note: str | None,
    background: BackgroundTasks,
    *,
    anonymous: bool = False,
) -> Any:
    """Record the caller's request for AI access; email the operator when it is new.

    Idempotent for the caller: a second request while one is pending
    returns ``pending`` (updating the note when given) and sends nothing.
    Anonymous sign-ins cannot ask: each would be a new account and email.
    """
    if principal.kind != "user" or anonymous:
        raise refusal("ai_session_required")
    if not ledger_is_durable(store):
        # The operator would be emailed about a row that disappears on restart.
        raise error(500, "ai_request_unavailable")
    try:
        state = store.ai_request_access(principal.user_id, note)
    except Exception as exc:
        logger.warning("ai_request_access failed: %s", type(exc).__name__)
        raise error(500, "ai_request_unavailable") from exc
    if state.state == "created":
        background.add_task(_alert_operator, store)
    return state


def _request_alerts_per_hour() -> int:
    raw = os.environ.get("AI_REQUEST_ALERTS_PER_HOUR", "").strip()
    if not raw:
        return REQUEST_ALERTS_PER_HOUR
    try:
        return max(int(raw), 0)
    except ValueError:
        logger.warning("AI_REQUEST_ALERTS_PER_HOUR is not an integer; using the default")
        return REQUEST_ALERTS_PER_HOUR


def _alert_operator(store: Any) -> None:
    """Email the operator about a new request, unless the hourly cap is reached.

    The count includes the request just created. A count that cannot be read
    sends nothing: the request is on /admin/ai either way.
    """
    cap = _request_alerts_per_hour()
    try:
        recent = store.ai_requests_since(datetime.now(UTC) - timedelta(hours=1))
    except Exception as exc:
        logger.warning("ai access request alert not sent: count failed: %s", type(exc).__name__)
        return
    if recent > cap:
        logger.info("ai access request alert not sent: %d requests in the last hour", recent)
        return
    notify_operator(dict(_REQUEST_ALERT), label="ai access request alert")


def approve_request(
    store: Any, *, operator: Principal, user_id: str, request: Request | None
) -> dict[str, Any]:
    """Approve a pending request with the default limits; 404 when it is not pending."""
    try:
        approved = store.ai_approve_request(
            user_id=user_id,
            approved_by=operator.user_id,
            ip_address=trusted_client_ip(request),
            user_agent=request.headers.get("user-agent") if request is not None else None,
        )
    except Exception as exc:
        logger.warning("ai_approve_request failed: %s", type(exc).__name__)
        raise error(500, "ai_request_unavailable") from exc
    if not approved:
        raise error(404, "ai_request_not_found")
    return _entitlement_row(store, user_id)


def dismiss_request(
    store: Any, *, operator: Principal, user_id: str, request: Request | None
) -> None:
    """Dismiss a pending request; 404 when it is not pending."""
    try:
        dismissed = store.ai_dismiss_request(
            user_id=user_id,
            dismissed_by=operator.user_id,
            ip_address=trusted_client_ip(request),
            user_agent=request.headers.get("user-agent") if request is not None else None,
        )
    except Exception as exc:
        logger.warning("ai_dismiss_request failed: %s", type(exc).__name__)
        raise error(500, "ai_request_unavailable") from exc
    if not dismissed:
        raise error(404, "ai_request_not_found")


def forget_user(store: Any, user_id: str) -> bool:
    """The user's data erasure, AI part: the request's note and the address copy.

    False when it failed: the failure is logged (class only), the erasure
    goes on, and the route reports ``partial`` instead of ``complete``.
    """
    forget = getattr(store, "ai_forget_user", None)
    if forget is None:
        return True
    try:
        forget(user_id)
    except Exception as exc:
        logger.warning("ai_forget_user failed: %s", type(exc).__name__)
        return False
    return True
