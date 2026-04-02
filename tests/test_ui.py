import re
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.models import CachedIssueData, IssueMetadata, PipelineData
from src.ui import (
    CancelIssueButton,
    CreateIssueButton,
    DeleteButton,
    DeleteView,
    ErrorView,
    RetryIssueButton,
    build_error_embed,
    cache_pipeline_data,
    get_cached_pipeline_data,
)


class TestDeleteButton:
    def test_button_has_trash_emoji(self):
        button = DeleteButton()
        assert str(button.emoji) == "\N{WASTEBASKET}"

    def test_button_style_is_grey(self):
        button = DeleteButton()
        assert button.style == discord.ButtonStyle.grey

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
    def test_view_contains_one_child(self):
        view = DeleteView()
        assert len(view.children) == 1

    def test_view_child_is_delete_button(self):
        view = DeleteView()
        assert isinstance(view.children[0], DeleteButton)

    def test_view_has_no_timeout(self):
        view = DeleteView()
        assert view.timeout is None

    def test_view_is_persistent(self):
        view = DeleteView()
        assert view.is_persistent()


class TestCreateIssueButton:
    def test_custom_id_encodes_owner_repo_and_key(self):
        btn = CreateIssueButton(owner="myorg", repo="myrepo", cache_key="abc1")
        assert btn.custom_id == "create_issue:myorg/myrepo/abc1"

    def test_button_label_is_create(self):
        btn = CreateIssueButton(owner="o", repo="r", cache_key="k")
        assert btn.item.label == "Create"

    def test_button_style_is_green(self):
        btn = CreateIssueButton(owner="o", repo="r", cache_key="k")
        assert btn.item.style == discord.ButtonStyle.green

    @pytest.mark.asyncio
    async def test_from_custom_id_extracts_owner_repo_key(self):
        match = re.match(
            r"create_issue:(?P<owner>[^/]+)/(?P<repo>[^/]+)/(?P<key>.+)",
            "create_issue:myorg/myrepo/abc1",
        )
        interaction = AsyncMock()
        item = MagicMock()
        btn = await CreateIssueButton.from_custom_id(interaction, item, match)
        assert btn.owner == "myorg"
        assert btn.repo == "myrepo"
        assert btn.cache_key == "abc1"

    @pytest.mark.asyncio
    async def test_callback_cache_miss_sends_expired(self):
        btn = CreateIssueButton(owner="o", repo="r", cache_key="missing")
        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await btn.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "expired" in interaction.response.send_message.call_args.args[0].lower()

    @pytest.mark.asyncio
    @patch("src.output.github.create_issue", new_callable=AsyncMock)
    async def test_callback_creates_issue_and_sends_delete_view(self, mock_create):
        mock_create.return_value = "https://github.com/o/r/issues/42"

        cached = _make_cached(author="alice", link="https://discord.com/channels/1/2/3")
        key = cache_pipeline_data(cached)

        btn = CreateIssueButton(owner="o", repo="r", cache_key=key)

        embed = MagicMock()
        embed.description = "# Title\nBody text"

        interaction = AsyncMock()
        interaction.message = MagicMock()
        interaction.message.embeds = [embed]
        interaction.client = MagicMock()
        interaction.client.github_auth = AsyncMock()
        interaction.client.github_auth.get_token = AsyncMock(return_value="ghs_tok")
        interaction.client.http_client = MagicMock()
        interaction.response = AsyncMock()

        await btn.callback(interaction)

        mock_create.assert_awaited_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.args[1] == "o"
        assert call_kwargs.args[2] == "r"
        assert "Author: alice" in call_kwargs.args[4]
        assert "discord.com/channels/1/2/3" in call_kwargs.args[4]

        interaction.response.edit_message.assert_awaited_once()
        edit_kwargs = interaction.response.edit_message.call_args.kwargs
        assert edit_kwargs["view"] is None
        assert "issues/42" in edit_kwargs["content"]

        interaction.channel.send.assert_awaited_once()
        channel_kwargs = interaction.channel.send.call_args.kwargs
        assert isinstance(channel_kwargs["view"], DeleteView)


class TestCancelIssueButton:
    def test_custom_id_encodes_owner_and_repo(self):
        btn = CancelIssueButton(owner="myorg", repo="myrepo")
        assert btn.custom_id == "cancel_issue:myorg/myrepo"

    def test_button_label_is_cancel(self):
        btn = CancelIssueButton(owner="o", repo="r")
        assert btn.item.label == "Cancel"

    def test_button_style_is_red(self):
        btn = CancelIssueButton(owner="o", repo="r")
        assert btn.item.style == discord.ButtonStyle.red

    @pytest.mark.asyncio
    async def test_from_custom_id_extracts_owner_repo(self):
        match = re.match(
            r"cancel_issue:(?P<owner>[^/]+)/(?P<repo>.+)",
            "cancel_issue:myorg/myrepo",
        )
        interaction = AsyncMock()
        item = MagicMock()
        btn = await CancelIssueButton.from_custom_id(interaction, item, match)
        assert btn.owner == "myorg"
        assert btn.repo == "myrepo"

    @pytest.mark.asyncio
    async def test_callback_cancels_and_removes_view(self):
        btn = CancelIssueButton(owner="o", repo="r")
        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await btn.callback(interaction)

        call_kwargs = interaction.response.edit_message.call_args.kwargs
        assert call_kwargs["view"] is None
        assert "cancelled" in call_kwargs["content"].lower()


def _make_cached(input="topic", messages=None, author="tester", link=None):
    pipeline = PipelineData(input=input, context={"messages": messages or ["msg"]})
    metadata = IssueMetadata(author_username=author, latest_message_link=link)
    return CachedIssueData(pipeline_data=pipeline, metadata=metadata)


class TestRetryCache:
    def test_cache_pipeline_data_returns_key(self):
        data = _make_cached()
        key = cache_pipeline_data(data)
        assert isinstance(key, str)
        assert len(key) == 8

    def test_get_cached_pipeline_data_returns_stored_data(self):
        data = _make_cached()
        key = cache_pipeline_data(data)
        assert get_cached_pipeline_data(key) is data

    def test_get_cached_pipeline_data_returns_none_on_miss(self):
        assert get_cached_pipeline_data("nonexistent") is None


class TestRetryIssueButton:
    def test_custom_id_encodes_owner_repo_and_key(self):
        btn = RetryIssueButton(owner="o", repo="r", retry_key="abc123")
        assert btn.custom_id == "retry_issue:o/r/abc123"

    def test_button_label_is_retry(self):
        btn = RetryIssueButton(owner="o", repo="r", retry_key="abc123")
        assert btn.item.label == "Retry"

    def test_button_style_is_blurple(self):
        btn = RetryIssueButton(owner="o", repo="r", retry_key="abc123")
        assert btn.item.style == discord.ButtonStyle.blurple

    @pytest.mark.asyncio
    async def test_from_custom_id_extracts_owner_repo_key(self):
        match = re.match(
            r"retry_issue:(?P<owner>[^/]+)/(?P<repo>[^/]+)/(?P<key>.+)",
            "retry_issue:myorg/myrepo/abc123",
        )
        interaction = AsyncMock()
        item = MagicMock()
        btn = await RetryIssueButton.from_custom_id(interaction, item, match)
        assert btn.owner == "myorg"
        assert btn.repo == "myrepo"
        assert btn.retry_key == "abc123"

    @pytest.mark.asyncio
    async def test_callback_cache_miss_sends_ephemeral_error(self):
        btn = RetryIssueButton(owner="o", repo="r", retry_key="missing_key")
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
    def test_has_two_children(self):
        view = ErrorView(owner="o", repo="r", retry_key="abc")
        assert len(view.children) == 2

    def test_contains_retry_button(self):
        view = ErrorView(owner="o", repo="r", retry_key="abc")
        assert any(isinstance(c, RetryIssueButton) for c in view.children)

    def test_contains_cancel_button(self):
        view = ErrorView(owner="o", repo="r", retry_key="abc")
        assert any(isinstance(c, CancelIssueButton) for c in view.children)

    def test_has_no_timeout(self):
        view = ErrorView(owner="o", repo="r", retry_key="abc")
        assert view.timeout is None

    def test_is_persistent(self):
        view = ErrorView(owner="o", repo="r", retry_key="abc")
        assert view.is_persistent()


class TestRetryIssueButtonErrors:
    @pytest.mark.asyncio
    async def test_callback_transform_error_shows_error_view(self):
        cached = _make_cached()
        key = cache_pipeline_data(cached)

        btn = RetryIssueButton(owner="o", repo="r", retry_key=key)

        mock_cog = MagicMock()
        mock_cog.transform = AsyncMock()
        mock_cog.transform.run.side_effect = RuntimeError("503 Service Unavailable")

        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.client = MagicMock()
        interaction.client.get_cog.return_value = mock_cog

        await btn.callback(interaction)

        interaction.edit_original_response.assert_awaited_once()
        call_kwargs = interaction.edit_original_response.call_args.kwargs
        assert "RuntimeError" in call_kwargs["embed"].description
        assert isinstance(call_kwargs["view"], ErrorView)

    @pytest.mark.asyncio
    async def test_callback_transform_error_caches_new_key(self):
        cached = _make_cached()
        key = cache_pipeline_data(cached)

        btn = RetryIssueButton(owner="o", repo="r", retry_key=key)

        mock_cog = MagicMock()
        mock_cog.transform = AsyncMock()
        mock_cog.transform.run.side_effect = RuntimeError("fail")

        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.client = MagicMock()
        interaction.client.get_cog.return_value = mock_cog

        await btn.callback(interaction)

        view = interaction.edit_original_response.call_args.kwargs["view"]
        retry_btn = [c for c in view.children if isinstance(c, RetryIssueButton)][0]
        assert retry_btn.retry_key != key

    @pytest.mark.asyncio
    async def test_callback_cache_hit_shows_loading_then_result(self):
        cached = _make_cached()
        key = cache_pipeline_data(cached)

        btn = RetryIssueButton(owner="o", repo="r", retry_key=key)

        mock_cog = MagicMock()
        mock_cog.transform = AsyncMock()
        mock_cog.transform.run.return_value = PipelineData(
            input="# New Title\nNew body", context={}
        )

        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.client = MagicMock()
        interaction.client.get_cog.return_value = mock_cog

        await btn.callback(interaction)

        # Shows loading state first
        interaction.response.edit_message.assert_awaited_once()
        loading_view = interaction.response.edit_message.call_args.kwargs["view"]
        assert len(loading_view.children) == 1
        assert loading_view.children[0].disabled is True

        # Then replaces with result
        mock_cog.transform.run.assert_awaited_once_with(cached.pipeline_data)
        interaction.edit_original_response.assert_awaited_once()
        call_kwargs = interaction.edit_original_response.call_args.kwargs
        assert call_kwargs["embed"].description == "# New Title\nNew body"
        assert call_kwargs["view"] is not None
