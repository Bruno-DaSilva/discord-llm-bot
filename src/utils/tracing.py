"""Centralized tracing abstraction.

All Sentry interaction is consolidated here. Every other module uses these
functions/decorators instead of importing ``sentry_sdk`` directly.
When Sentry is not initialized, all operations are safe no-ops.
"""

from __future__ import annotations

import functools
import re
import uuid
from contextlib import asynccontextmanager
from typing import Any

try:
    import sentry_sdk

    _HAS_SENTRY = True
except ImportError:  # pragma: no cover
    sentry_sdk = None  # type: ignore[assignment]
    _HAS_SENTRY = False


def _sentry_enabled() -> bool:
    return _HAS_SENTRY and sentry_sdk.is_initialized()


# ---------------------------------------------------------------------------
# Trace lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def start_trace(
    op: str, name: str, *, data: dict[str, Any] | None = None
):
    """Start a new Sentry transaction. No-op when Sentry is disabled."""
    if not _sentry_enabled():
        yield
        return
    with sentry_sdk.start_transaction(op=op, name=name) as txn:
        if data:
            for k, v in data.items():
                txn.set_data(k, v)
        yield txn


@asynccontextmanager
async def continue_trace(
    headers: dict[str, str],
    op: str,
    name: str,
    *,
    data: dict[str, Any] | None = None,
):
    """Continue an existing trace from propagation headers. No-op when Sentry is disabled."""
    if not _sentry_enabled():
        yield
        return
    txn = sentry_sdk.continue_trace(headers, op=op, name=name)
    with sentry_sdk.start_transaction(txn) as span:
        if data:
            for k, v in data.items():
                span.set_data(k, v)
        yield span


def get_trace_headers() -> dict[str, str]:
    """Return current trace propagation headers, or empty dict when disabled."""
    if not _sentry_enabled():
        return {}
    return {
        "sentry-trace": sentry_sdk.get_traceparent(),
        "baggage": sentry_sdk.get_baggage(),
    }


def generate_cache_key() -> str:
    """Return the current Sentry trace ID, or a random UUID when unavailable.

    This value is used as the cache key for retry data, which means the trace
    identity is naturally embedded in every button ``custom_id``.
    """
    if _sentry_enabled():
        traceparent = sentry_sdk.get_traceparent()
        if traceparent:
            return traceparent.split("-")[0]
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Modal propagation
# ---------------------------------------------------------------------------


def propagate_trace_to_modal(
    modal: Any, interaction: Any, command_name: str
) -> None:
    """Copy trace headers and command name from the interaction to the modal."""
    modal._trace_headers = interaction.extras.get("sentry_trace_headers")
    modal._command_name = command_name


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


def _resolve_cache_key(obj: Any) -> str | None:
    """Read whichever cache-key attribute exists on a DynamicItem instance."""
    for attr in ("cache_key", "retry_key"):
        val = getattr(obj, attr, None)
        if val is not None:
            return val
    return None


def _action_from_class(cls: type) -> str:
    """Derive a kebab-case action from a button class name.

    ``ConfirmButton`` → ``"confirm"``, ``OutputRetryButton`` → ``"output-retry"``
    """
    stem = cls.__name__.removesuffix("Button")
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", stem).lower()


def traced_callback(fn):
    """Decorator for ``DynamicItem.callback`` that wraps execution in a trace.

    Looks up stored trace headers from the cached pipeline data (via the
    button's cache key) and continues the original trace, or starts a new
    one if no headers are found.

    Transaction name format: ``"{cmd_type}.{action}"``
    """

    @functools.wraps(fn)
    async def wrapper(self, interaction):
        cache_key = _resolve_cache_key(self)
        headers = None
        if cache_key:
            from src.cogs.ui import get_cached_pipeline_data

            cached = get_cached_pipeline_data(cache_key)
            if cached is not None:
                headers = getattr(cached, "trace_headers", None)

        cmd_type = getattr(self, "cmd_type", "unknown")
        action = _action_from_class(type(self))
        txn_name = f"{cmd_type}.{action}"

        if headers:
            ctx = continue_trace(headers, "discord.component", txn_name)
        else:
            ctx = start_trace("discord.component", txn_name)

        async with ctx:
            interaction.extras["sentry_trace_headers"] = get_trace_headers()
            await fn(self, interaction)

    return wrapper


def traced_modal_submit(fn):
    """Decorator for ``Modal.on_submit`` that wraps execution in a trace.

    Reads trace headers from ``self._trace_headers`` (set by
    :func:`propagate_trace_to_modal`) or ``interaction.extras``.

    Transaction name format: ``"{command_name}.modal"``
    """

    @functools.wraps(fn)
    async def wrapper(self, interaction):
        headers = getattr(self, "_trace_headers", None)
        if headers is None:
            headers = interaction.extras.get("sentry_trace_headers")

        command_name = getattr(self, "_command_name", "unknown")
        txn_name = f"{command_name}.modal"

        if headers:
            ctx = continue_trace(headers, "discord.modal", txn_name)
        else:
            ctx = start_trace("discord.modal", txn_name)

        async with ctx:
            interaction.extras["sentry_trace_headers"] = get_trace_headers()
            await fn(self, interaction)

    return wrapper
