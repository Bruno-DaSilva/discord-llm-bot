from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

import pytest

from src.cogs.create_issue import CreateIssueCog, IssuePreviewView
from src.output.discord import FetchResult
from src.ui import CancelIssueButton, CreateIssueButton, ErrorView, RetryIssueButton


@pytest.fixture
def bot():
    b = MagicMock(spec=commands.Bot)
    b.tree = MagicMock()
    return b


@pytest.fixture
def cog(bot):
    mock_transform = AsyncMock()
    mock_transform.run.return_value = MagicMock(input="# Title\nBody", context={})
    return CreateIssueCog(
        bot,
        transform=mock_transform,
    )


class TestCreateIssueCog:
    def test_cog_instantiation(self, cog, bot):
        assert cog.bot is bot

    def _mock_fetch_result(self, messages=None, link="https://discord.com/channels/1/2/3"):
        return FetchResult(
            messages=messages or ["user1: msg"],
            latest_message_link=link,
        )

    def _mock_interaction(self):
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.channel = MagicMock()
        interaction.user = MagicMock()
        interaction.user.display_name = "TestUser"
        return interaction

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_command_defers_first(self, mock_fetch, cog):
        mock_fetch.return_value = self._mock_fetch_result()
        interaction = self._mock_interaction()

        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_command_fetches_messages(self, mock_fetch, cog):
        mock_fetch.return_value = self._mock_fetch_result()
        interaction = self._mock_interaction()

        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)

        mock_fetch.assert_awaited_once_with(interaction.channel, limit=5)

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_command_calls_transform_with_pipeline_data(
        self, mock_fetch, cog
    ):
        mock_fetch.return_value = self._mock_fetch_result(
            messages=["user1: hello", "user2: world"]
        )
        interaction = self._mock_interaction()

        await cog._do_create_issue(
            interaction, repo="owner/repo", topic="login bug", n=10
        )

        cog.transform.run.assert_awaited_once()
        pipeline_data = cog.transform.run.call_args.args[0]
        assert pipeline_data.input == "login bug"
        assert pipeline_data.context["messages"] == [
            "user1: hello",
            "user2: world",
        ]

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_command_sends_preview(self, mock_fetch, cog):
        mock_fetch.return_value = self._mock_fetch_result()
        interaction = self._mock_interaction()

        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)

        interaction.followup.send.assert_awaited_once()
        call_kwargs = interaction.followup.send.call_args.kwargs
        embed = call_kwargs.get("embed")
        assert embed is not None
        assert "# Title" in embed.description
        assert call_kwargs.get("view") is not None

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_no_messages_sends_error(self, mock_fetch, cog):
        mock_fetch.return_value = FetchResult(messages=[], latest_message_link=None)
        interaction = self._mock_interaction()

        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)

        interaction.followup.send.assert_awaited_once()
        call_args = interaction.followup.send.call_args
        content = call_args.kwargs.get("content") or call_args.args[0] if call_args.args else call_args.kwargs.get("content", "")
        assert "internal error" in content.lower()
        cog.transform.run.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_transform_error_sends_error_embed(self, mock_fetch, cog):
        mock_fetch.return_value = self._mock_fetch_result()
        cog.transform.run.side_effect = RuntimeError("Gemini 503")

        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.channel = MagicMock()

        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)

        interaction.followup.send.assert_awaited_once()
        call_kwargs = interaction.followup.send.call_args.kwargs
        assert "RuntimeError" in call_kwargs["embed"].description
        assert isinstance(call_kwargs["view"], ErrorView)
        assert any(isinstance(c, RetryIssueButton) for c in call_kwargs["view"].children)

    @pytest.mark.asyncio
    async def test_expired_interaction_is_ignored(self, cog):
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.response.defer.side_effect = discord.NotFound(
            MagicMock(status=404), {"code": 10062, "message": "Unknown interaction"}
        )

        # Should not raise
        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)


class TestIssuePreviewView:
    def test_preview_view_has_three_children(self):
        view = IssuePreviewView(owner="o", repo="r", cache_key="k1")
        assert len(view.children) == 3

    def test_preview_view_contains_create_button(self):
        view = IssuePreviewView(owner="o", repo="r", cache_key="k1")
        assert any(isinstance(c, CreateIssueButton) for c in view.children)

    def test_preview_view_contains_cancel_button(self):
        view = IssuePreviewView(owner="o", repo="r", cache_key="k1")
        assert any(isinstance(c, CancelIssueButton) for c in view.children)

    def test_preview_view_has_no_timeout(self):
        view = IssuePreviewView(owner="o", repo="r", cache_key="k1")
        assert view.timeout is None

    def test_preview_view_is_persistent(self):
        view = IssuePreviewView(owner="o", repo="r", cache_key="k1")
        assert view.is_persistent()

    def test_preview_view_has_three_children_with_cache_key(self):
        view = IssuePreviewView(owner="o", repo="r", cache_key="abc123")
        assert len(view.children) == 3

    def test_preview_view_contains_retry_button(self):
        view = IssuePreviewView(owner="o", repo="r", cache_key="abc123")
        assert any(isinstance(c, RetryIssueButton) for c in view.children)

    def test_loading_view_has_single_disabled_button(self):
        view = IssuePreviewView(owner="o", repo="r", loading=True)
        assert len(view.children) == 1
        assert view.children[0].disabled is True
        assert "Regenerating" in view.children[0].label

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_command_sends_preview_with_retry_button(self, mock_fetch, cog):
        mock_fetch.return_value = FetchResult(
            messages=["msg"], latest_message_link="https://discord.com/channels/1/2/3"
        )

        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.channel = MagicMock()
        interaction.user = MagicMock()
        interaction.user.display_name = "TestUser"

        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)

        call_kwargs = interaction.followup.send.call_args.kwargs
        view = call_kwargs["view"]
        assert any(isinstance(c, RetryIssueButton) for c in view.children)
