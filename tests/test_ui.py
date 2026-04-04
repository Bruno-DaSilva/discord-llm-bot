from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.models import CachedOutputData
from src.ui import (
    CancelButton,
    ConfirmButton,
    DeleteButton,
    DeleteView,
    ErrorView,
    OutputErrorView,
    OutputRetryButton,
    PreviewView,
    RetryButton,
    build_error_embed,
    cache_pipeline_data,
    get_cached_pipeline_data,
)

from tests.conftest import make_cached


class TestDeleteButton:
    def test_button_has_trash_emoji(self):
        button = DeleteButton()
        assert str(button.emoji) == "\N{WASTEBASKET}"

    def test_button_has_no_text_label(self):
        button = DeleteButton()
        assert button.label is None

    def test_button_has_persistent_custom_id(self):
        button = DeleteButton()
        assert button.custom_id == "delete_issue_msg"

    @pytest.mark.asyncio
    async def test_callback_deletes_message(self):
        button = DeleteButton()
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.message = AsyncMock()

        await button.callback(interaction)

        interaction.response.defer.assert_awaited_once()
        interaction.message.delete.assert_awaited_once()


class TestDeleteView:
    def test_view_child_is_delete_button(self):
        view = DeleteView()
        assert isinstance(view.children[0], DeleteButton)

    def test_view_has_no_timeout(self):
        view = DeleteView()
        assert view.timeout is None

    def test_view_is_persistent(self):
        view = DeleteView()
        assert view.is_persistent()


class TestConfirmButton:
    @pytest.mark.asyncio
    async def test_custom_id_round_trips(self):
        btn = ConfirmButton(cmd_type="issue", cache_key="abc1")
        match = ConfirmButton.__discord_ui_compiled_template__.match(btn.custom_id)
        assert match is not None
        interaction = AsyncMock()
        item = MagicMock()
        parsed = await ConfirmButton.from_custom_id(interaction, item, match)
        assert parsed.cmd_type == "issue"
        assert parsed.cache_key == "abc1"

    @pytest.mark.asyncio
    async def test_callback_cache_miss_sends_expired(self):
        btn = ConfirmButton(cmd_type="issue", cache_key="missing")
        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await btn.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "expired" in interaction.response.send_message.call_args.args[0].lower()

    @pytest.mark.asyncio
    async def test_callback_dispatches_to_handler(self):
        cached = make_cached(author="alice", link="https://discord.com/channels/1/2/3")
        key = cache_pipeline_data(cached)

        btn = ConfirmButton(cmd_type="issue", cache_key=key)

        mock_handler = MagicMock()
        mock_handler.on_confirm = AsyncMock()

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        from src.cogs.registry import _handlers

        _handlers["issue"] = mock_handler
        try:
            await btn.callback(interaction)
            mock_handler.on_confirm.assert_awaited_once_with(interaction, cached)
        finally:
            _handlers.pop("issue", None)

    @pytest.mark.asyncio
    async def test_callback_unknown_cmd_type_sends_error(self):
        cached = make_cached()
        key = cache_pipeline_data(cached)

        btn = ConfirmButton(cmd_type="nonexistent", cache_key=key)
        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await btn.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "unknown" in interaction.response.send_message.call_args.args[0].lower()


class TestCancelButton:
    @pytest.mark.asyncio
    async def test_custom_id_round_trips(self):
        btn = CancelButton(cmd_type="issue", cache_key="abc1")
        match = CancelButton.__discord_ui_compiled_template__.match(btn.custom_id)
        assert match is not None
        interaction = AsyncMock()
        item = MagicMock()
        parsed = await CancelButton.from_custom_id(interaction, item, match)
        assert parsed.cmd_type == "issue"
        assert parsed.cache_key == "abc1"

    @pytest.mark.asyncio
    async def test_callback_cancels_and_removes_view(self):
        btn = CancelButton(cmd_type="issue", cache_key="abc1")
        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await btn.callback(interaction)

        call_kwargs = interaction.response.edit_message.call_args.kwargs
        assert call_kwargs["view"] is None
        assert "cancelled" in call_kwargs["content"].lower()


class TestRetryCache:
    def test_cache_pipeline_data_returns_key(self):
        data = make_cached()
        key = cache_pipeline_data(data)
        assert isinstance(key, str)
        assert key  # non-empty

    def test_get_cached_pipeline_data_returns_stored_data(self):
        data = make_cached()
        key = cache_pipeline_data(data)
        assert get_cached_pipeline_data(key) is data

    def test_get_cached_pipeline_data_returns_none_on_miss(self):
        assert get_cached_pipeline_data("nonexistent") is None


class TestRetryButton:
    @pytest.mark.asyncio
    async def test_custom_id_round_trips(self):
        btn = RetryButton(cmd_type="issue", retry_key="abc123")
        match = RetryButton.__discord_ui_compiled_template__.match(btn.custom_id)
        assert match is not None
        interaction = AsyncMock()
        item = MagicMock()
        parsed = await RetryButton.from_custom_id(interaction, item, match)
        assert parsed.cmd_type == "issue"
        assert parsed.retry_key == "abc123"

    @pytest.mark.asyncio
    async def test_callback_cache_miss_sends_ephemeral_error(self):
        btn = RetryButton(cmd_type="issue", retry_key="missing_key")
        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await btn.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        call_kwargs = interaction.response.send_message.call_args
        assert "expired" in call_kwargs.args[0].lower()
        assert call_kwargs.kwargs["ephemeral"] is True


class TestBuildErrorEmbed:
    def test_includes_exception_type(self):
        embed = build_error_embed(ValueError("bad input"))
        assert "ValueError" in embed.description

    def test_includes_error_message(self):
        embed = build_error_embed(ValueError("bad input"))
        assert "bad input" in embed.description

    def test_has_red_color(self):
        embed = build_error_embed(RuntimeError("fail"))
        assert embed.color == discord.Color.red()

    def test_has_title(self):
        embed = build_error_embed(RuntimeError("fail"))
        assert embed.title is not None


class TestErrorView:
    def test_contains_retry_button(self):
        view = ErrorView(cmd_type="issue", retry_key="abc")
        assert any(isinstance(c, RetryButton) for c in view.children)

    def test_contains_cancel_button(self):
        view = ErrorView(cmd_type="issue", retry_key="abc")
        assert any(isinstance(c, CancelButton) for c in view.children)

    def test_has_no_timeout(self):
        view = ErrorView(cmd_type="issue", retry_key="abc")
        assert view.timeout is None

    def test_is_persistent(self):
        view = ErrorView(cmd_type="issue", retry_key="abc")
        assert view.is_persistent()


class TestRetryButtonDispatch:
    @pytest.mark.asyncio
    async def test_callback_dispatches_to_handler(self):
        cached = make_cached()
        key = cache_pipeline_data(cached)

        btn = RetryButton(cmd_type="issue", retry_key=key)

        mock_handler = MagicMock()
        mock_handler.on_retry = AsyncMock()

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        from src.cogs.registry import _handlers

        _handlers["issue"] = mock_handler
        try:
            await btn.callback(interaction)
            mock_handler.on_retry.assert_awaited_once_with(interaction, cached)
        finally:
            _handlers.pop("issue", None)

    @pytest.mark.asyncio
    async def test_callback_unknown_cmd_type_sends_error(self):
        cached = make_cached()
        key = cache_pipeline_data(cached)

        btn = RetryButton(cmd_type="nonexistent", retry_key=key)
        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await btn.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "unknown" in interaction.response.send_message.call_args.args[0].lower()


class TestOutputRetryButton:
    @pytest.mark.asyncio
    async def test_custom_id_round_trips(self):
        btn = OutputRetryButton(cmd_type="issue", retry_key="abc123")
        match = OutputRetryButton.__discord_ui_compiled_template__.match(btn.custom_id)
        assert match is not None
        interaction = AsyncMock()
        item = MagicMock()
        parsed = await OutputRetryButton.from_custom_id(interaction, item, match)
        assert parsed.cmd_type == "issue"
        assert parsed.retry_key == "abc123"

    @pytest.mark.asyncio
    async def test_callback_expired_cache_sends_ephemeral(self):
        btn = OutputRetryButton(cmd_type="issue", retry_key="missing")
        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await btn.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "expired" in interaction.response.send_message.call_args.args[0].lower()
        assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_callback_dispatches_to_handler(self):
        data = CachedOutputData(
            cmd_type="issue", payload={"title": "My Title", "body": "My body"}
        )
        key = cache_pipeline_data(data)

        btn = OutputRetryButton(cmd_type="issue", retry_key=key)

        mock_handler = MagicMock()
        mock_handler.on_output_retry = AsyncMock()

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        from src.cogs.registry import _handlers

        _handlers["issue"] = mock_handler
        try:
            await btn.callback(interaction)
            mock_handler.on_output_retry.assert_awaited_once_with(interaction, data)
        finally:
            _handlers.pop("issue", None)


class TestOutputErrorView:
    def test_contains_output_retry_button(self):
        view = OutputErrorView(cmd_type="issue", retry_key="abc")
        assert any(isinstance(c, OutputRetryButton) for c in view.children)

    def test_contains_cancel_button(self):
        view = OutputErrorView(cmd_type="issue", retry_key="abc")
        assert any(isinstance(c, CancelButton) for c in view.children)

    def test_has_no_timeout(self):
        view = OutputErrorView(cmd_type="issue", retry_key="abc")
        assert view.timeout is None

    def test_is_persistent(self):
        view = OutputErrorView(cmd_type="issue", retry_key="abc")
        assert view.is_persistent()


class TestPreviewView:
    def test_contains_confirm_button(self):
        view = PreviewView(cmd_type="issue", cache_key="k1")
        assert any(isinstance(c, ConfirmButton) for c in view.children)

    def test_contains_cancel_button(self):
        view = PreviewView(cmd_type="issue", cache_key="k1")
        assert any(isinstance(c, CancelButton) for c in view.children)

    def test_contains_retry_button(self):
        view = PreviewView(cmd_type="issue", cache_key="abc123")
        assert any(isinstance(c, RetryButton) for c in view.children)

    def test_has_no_timeout(self):
        view = PreviewView(cmd_type="issue", cache_key="k1")
        assert view.timeout is None

    def test_is_persistent(self):
        view = PreviewView(cmd_type="issue", cache_key="k1")
        assert view.is_persistent()

    def test_loading_view_has_single_disabled_button(self):
        view = PreviewView(cmd_type="issue", loading=True)
        assert len(view.children) == 1
        assert view.children[0].disabled is True
        assert "Regenerating" in view.children[0].label

    def test_custom_confirm_label(self):
        view = PreviewView(cmd_type="issue", cache_key="k1", confirm_label="Create")
        confirm_btn = [c for c in view.children if isinstance(c, ConfirmButton)][0]
        assert confirm_btn.item.label == "Create"
