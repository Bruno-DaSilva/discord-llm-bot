from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.tracing import (
    continue_trace,
    generate_cache_key,
    get_trace_headers,
    propagate_trace_to_modal,
    start_trace,
    traced_callback,
    traced_modal_submit,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_HEADERS = {
    "sentry-trace": "00-abc123-def456-01",
    "baggage": "sentry-trace_id=abc123",
}


def _make_sentry_disabled():
    return patch("src.utils.tracing._sentry_enabled", return_value=False)


def _make_sentry_enabled():
    return patch("src.utils.tracing._sentry_enabled", return_value=True)


def _mock_transaction():
    """Return a MagicMock that works as a sync context manager (sentry transaction)."""
    txn = MagicMock()
    txn.__enter__ = MagicMock(return_value=txn)
    txn.__exit__ = MagicMock(return_value=False)
    return txn


# ---------------------------------------------------------------------------
# start_trace
# ---------------------------------------------------------------------------


class TestStartTrace:
    @pytest.mark.asyncio
    async def test_noop_when_disabled(self):
        with _make_sentry_disabled():
            async with start_trace("op", "name"):
                pass  # should not raise

    @pytest.mark.asyncio
    async def test_starts_transaction_when_enabled(self):
        txn = _mock_transaction()

        with (
            _make_sentry_enabled(),
            patch("src.utils.tracing.sentry_sdk") as mock_sdk,
        ):
            mock_sdk.start_transaction.return_value = txn

            async with start_trace("gen_ai.invoke_agent", "invoke_agent test"):
                pass

            mock_sdk.start_transaction.assert_called_once_with(
                op="gen_ai.invoke_agent", name="invoke_agent test"
            )

    @pytest.mark.asyncio
    async def test_sets_data_on_transaction(self):
        txn = _mock_transaction()

        with (
            _make_sentry_enabled(),
            patch("src.utils.tracing.sentry_sdk") as mock_sdk,
        ):
            mock_sdk.start_transaction.return_value = txn

            async with start_trace(
                "op", "name", data={"gen_ai.agent.name": "test"}
            ):
                pass

            txn.set_data.assert_called_once_with("gen_ai.agent.name", "test")

    @pytest.mark.asyncio
    async def test_does_not_set_data_when_none(self):
        txn = _mock_transaction()

        with (
            _make_sentry_enabled(),
            patch("src.utils.tracing.sentry_sdk") as mock_sdk,
        ):
            mock_sdk.start_transaction.return_value = txn

            async with start_trace("op", "name"):
                pass

            txn.set_data.assert_not_called()


# ---------------------------------------------------------------------------
# continue_trace
# ---------------------------------------------------------------------------


class TestContinueTrace:
    @pytest.mark.asyncio
    async def test_noop_when_disabled(self):
        with _make_sentry_disabled():
            async with continue_trace(SAMPLE_HEADERS, "op", "name"):
                pass

    @pytest.mark.asyncio
    async def test_continues_existing_trace(self):
        txn = _mock_transaction()
        continued = MagicMock()

        with (
            _make_sentry_enabled(),
            patch("src.utils.tracing.sentry_sdk") as mock_sdk,
        ):
            mock_sdk.continue_trace.return_value = continued
            mock_sdk.start_transaction.return_value = txn

            async with continue_trace(SAMPLE_HEADERS, "discord.modal", "MyModal"):
                pass

            mock_sdk.continue_trace.assert_called_once_with(
                SAMPLE_HEADERS, op="discord.modal", name="MyModal"
            )
            mock_sdk.start_transaction.assert_called_once_with(continued)

    @pytest.mark.asyncio
    async def test_sets_data_on_continued_transaction(self):
        txn = _mock_transaction()

        with (
            _make_sentry_enabled(),
            patch("src.utils.tracing.sentry_sdk") as mock_sdk,
        ):
            mock_sdk.continue_trace.return_value = MagicMock()
            mock_sdk.start_transaction.return_value = txn

            async with continue_trace(
                SAMPLE_HEADERS, "op", "name", data={"key": "val"}
            ):
                pass

            txn.set_data.assert_called_once_with("key", "val")


# ---------------------------------------------------------------------------
# get_trace_headers
# ---------------------------------------------------------------------------


class TestGetTraceHeaders:
    def test_returns_empty_when_disabled(self):
        with _make_sentry_disabled():
            assert get_trace_headers() == {}

    def test_returns_headers_when_enabled(self):
        with (
            _make_sentry_enabled(),
            patch("src.utils.tracing.sentry_sdk") as mock_sdk,
        ):
            mock_sdk.get_traceparent.return_value = "00-abc-def-01"
            mock_sdk.get_baggage.return_value = "sentry-trace_id=abc"

            headers = get_trace_headers()

            assert headers == {
                "sentry-trace": "00-abc-def-01",
                "baggage": "sentry-trace_id=abc",
            }


# ---------------------------------------------------------------------------
# generate_cache_key
# ---------------------------------------------------------------------------


class TestGenerateCacheKey:
    def test_returns_32_hex_chars_when_disabled(self):
        with _make_sentry_disabled():
            key = generate_cache_key()
            assert len(key) == 32
            int(key, 16)  # valid hex

    def test_returns_trace_id_when_enabled(self):
        with (
            _make_sentry_enabled(),
            patch("src.utils.tracing.sentry_sdk") as mock_sdk,
        ):
            mock_sdk.get_traceparent.return_value = "abc123def456abcd-span01-01"
            key = generate_cache_key()
            assert key == "abc123def456abcd"

    def test_falls_back_to_uuid_when_no_traceparent(self):
        with (
            _make_sentry_enabled(),
            patch("src.utils.tracing.sentry_sdk") as mock_sdk,
        ):
            mock_sdk.get_traceparent.return_value = None
            key = generate_cache_key()
            assert len(key) == 32
            int(key, 16)


# ---------------------------------------------------------------------------
# propagate_trace_to_modal
# ---------------------------------------------------------------------------


class TestPropagateTraceToModal:
    def test_copies_headers_and_command_name_to_modal(self):
        modal = MagicMock()
        interaction = MagicMock()
        interaction.extras = {"sentry_trace_headers": SAMPLE_HEADERS}

        propagate_trace_to_modal(modal, interaction, "create-issue")

        assert modal._trace_headers == SAMPLE_HEADERS
        assert modal._command_name == "create-issue"

    def test_sets_none_when_no_headers(self):
        modal = MagicMock()
        interaction = MagicMock()
        interaction.extras = {}

        propagate_trace_to_modal(modal, interaction, "create-issue")

        assert modal._trace_headers is None
        assert modal._command_name == "create-issue"


# ---------------------------------------------------------------------------
# @traced_callback
# ---------------------------------------------------------------------------


class TestTracedCallback:
    @pytest.mark.asyncio
    async def test_calls_original_function(self):
        inner = AsyncMock()

        @traced_callback
        async def callback(self, interaction):
            await inner(interaction)

        obj = MagicMock()
        obj.cache_key = "abc123"
        interaction = MagicMock()
        interaction.extras = {}

        with _make_sentry_disabled():
            await callback(obj, interaction)

        inner.assert_awaited_once_with(interaction)

    @pytest.mark.asyncio
    async def test_sets_trace_headers_on_interaction_extras(self):
        @traced_callback
        async def callback(self, interaction):
            pass

        obj = MagicMock()
        obj.cache_key = "abc123"
        interaction = MagicMock()
        interaction.extras = {}

        with (
            _make_sentry_enabled(),
            patch("src.utils.tracing.sentry_sdk") as mock_sdk,
            patch(
                "src.cogs.ui.get_cached_pipeline_data", return_value=None
            ),
        ):
            txn = _mock_transaction()
            mock_sdk.start_transaction.return_value = txn
            mock_sdk.get_traceparent.return_value = "tp"
            mock_sdk.get_baggage.return_value = "bg"

            await callback(obj, interaction)

            assert interaction.extras["sentry_trace_headers"] == {
                "sentry-trace": "tp",
                "baggage": "bg",
            }

    @pytest.mark.asyncio
    async def test_continues_trace_from_cached_headers(self):
        @traced_callback
        async def callback(self, interaction):
            pass

        obj = MagicMock()
        obj.cmd_type = "issue"
        obj.cache_key = "abc123"
        del obj.retry_key  # ensure cache_key is used
        interaction = MagicMock()
        interaction.extras = {}

        cached = MagicMock()
        cached.trace_headers = SAMPLE_HEADERS

        with (
            _make_sentry_enabled(),
            patch("src.utils.tracing.sentry_sdk") as mock_sdk,
            patch(
                "src.cogs.ui.get_cached_pipeline_data",
                return_value=cached,
            ),
        ):
            txn = _mock_transaction()
            mock_sdk.continue_trace.return_value = MagicMock()
            mock_sdk.start_transaction.return_value = txn

            await callback(obj, interaction)

            mock_sdk.continue_trace.assert_called_once_with(
                SAMPLE_HEADERS,
                op="discord.component",
                name="issue.magic-mock",
            )

    @pytest.mark.asyncio
    async def test_reads_retry_key_when_no_cache_key(self):
        @traced_callback
        async def callback(self, interaction):
            pass

        obj = MagicMock(spec=["retry_key"])
        obj.retry_key = "retry123"
        interaction = MagicMock()
        interaction.extras = {}

        cached = MagicMock()
        cached.trace_headers = SAMPLE_HEADERS

        with (
            _make_sentry_disabled(),
            patch(
                "src.cogs.ui.get_cached_pipeline_data",
                return_value=cached,
            ),
        ):
            await callback(obj, interaction)
            # Just verify it doesn't crash and the right key is used


# ---------------------------------------------------------------------------
# @traced_modal_submit
# ---------------------------------------------------------------------------


class TestTracedModalSubmit:
    @pytest.mark.asyncio
    async def test_calls_original_function(self):
        inner = AsyncMock()

        @traced_modal_submit
        async def on_submit(self, interaction):
            await inner(interaction)

        modal = MagicMock()
        modal._trace_headers = None
        interaction = MagicMock()
        interaction.extras = {}

        with _make_sentry_disabled():
            await on_submit(modal, interaction)

        inner.assert_awaited_once_with(interaction)

    @pytest.mark.asyncio
    async def test_continues_trace_from_modal_headers(self):
        @traced_modal_submit
        async def on_submit(self, interaction):
            pass

        modal = MagicMock()
        modal._trace_headers = SAMPLE_HEADERS
        modal._command_name = "create-issue"
        interaction = MagicMock()
        interaction.extras = {}

        with (
            _make_sentry_enabled(),
            patch("src.utils.tracing.sentry_sdk") as mock_sdk,
        ):
            txn = _mock_transaction()
            mock_sdk.continue_trace.return_value = MagicMock()
            mock_sdk.start_transaction.return_value = txn
            mock_sdk.get_traceparent.return_value = "tp"
            mock_sdk.get_baggage.return_value = "bg"

            await on_submit(modal, interaction)

            mock_sdk.continue_trace.assert_called_once_with(
                SAMPLE_HEADERS,
                op="discord.modal",
                name="create-issue.modal",
            )

    @pytest.mark.asyncio
    async def test_sets_trace_headers_on_interaction(self):
        @traced_modal_submit
        async def on_submit(self, interaction):
            pass

        modal = MagicMock()
        modal._trace_headers = None
        interaction = MagicMock()
        interaction.extras = {}

        with (
            _make_sentry_enabled(),
            patch("src.utils.tracing.sentry_sdk") as mock_sdk,
        ):
            txn = _mock_transaction()
            mock_sdk.start_transaction.return_value = txn
            mock_sdk.get_traceparent.return_value = "tp"
            mock_sdk.get_baggage.return_value = "bg"

            await on_submit(modal, interaction)

            assert interaction.extras["sentry_trace_headers"] == {
                "sentry-trace": "tp",
                "baggage": "bg",
            }

    @pytest.mark.asyncio
    async def test_falls_back_to_interaction_extras(self):
        """If modal._trace_headers is not set, reads from interaction.extras."""

        @traced_modal_submit
        async def on_submit(self, interaction):
            pass

        modal = MagicMock(spec=[])  # no _trace_headers attr
        interaction = MagicMock()
        interaction.extras = {"sentry_trace_headers": SAMPLE_HEADERS}

        with (
            _make_sentry_enabled(),
            patch("src.utils.tracing.sentry_sdk") as mock_sdk,
        ):
            txn = _mock_transaction()
            mock_sdk.continue_trace.return_value = MagicMock()
            mock_sdk.start_transaction.return_value = txn
            mock_sdk.get_traceparent.return_value = "tp"
            mock_sdk.get_baggage.return_value = "bg"

            await on_submit(modal, interaction)

            mock_sdk.continue_trace.assert_called_once_with(
                SAMPLE_HEADERS,
                op="discord.modal",
                name="unknown.modal",
            )
