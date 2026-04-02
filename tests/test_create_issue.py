from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

import pytest

from src.cogs.create_issue import CreateIssueCog, IssuePreviewView
from src.ui import CancelIssueButton, CreateIssueButton


@pytest.fixture
def bot():
    b = MagicMock(spec=commands.Bot)
    b.tree = MagicMock()
    return b


@pytest.fixture
def cog(bot):
    return CreateIssueCog(
        bot,
        gemini_client=AsyncMock(),
        github_token="ghp_test",
    )


class TestCreateIssueCog:
    def test_cog_instantiation(self, cog, bot):
        assert cog.bot is bot

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages")
    @patch("src.cogs.create_issue.generate_issue")
    async def test_command_defers_first(self, mock_generate, mock_fetch, cog):
        mock_fetch.return_value = ["user1: msg"]
        mock_generate.return_value = MagicMock(input="# Title\nBody", context={})

        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.channel = MagicMock()

        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages")
    @patch("src.cogs.create_issue.generate_issue")
    async def test_command_fetches_messages(self, mock_generate, mock_fetch, cog):
        mock_fetch.return_value = ["user1: msg"]
        mock_generate.return_value = MagicMock(input="# Title\nBody", context={})

        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.channel = MagicMock()

        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)

        mock_fetch.assert_awaited_once_with(interaction.channel, limit=5)

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages")
    @patch("src.cogs.create_issue.generate_issue")
    async def test_command_calls_gemini_with_pipeline_data(
        self, mock_generate, mock_fetch, cog
    ):
        mock_fetch.return_value = ["user1: hello", "user2: world"]
        mock_generate.return_value = MagicMock(input="generated issue", context={})

        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.channel = MagicMock()

        await cog._do_create_issue(
            interaction, repo="owner/repo", topic="login bug", n=10
        )

        mock_generate.assert_awaited_once()
        call_args = mock_generate.call_args
        pipeline_data = call_args.args[0]
        assert pipeline_data.input == "login bug"
        assert pipeline_data.context["messages"] == [
            "user1: hello",
            "user2: world",
        ]

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages")
    @patch("src.cogs.create_issue.generate_issue")
    async def test_command_sends_preview(self, mock_generate, mock_fetch, cog):
        mock_fetch.return_value = ["msg"]
        mock_generate.return_value = MagicMock(input="issue body", context={})

        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.channel = MagicMock()

        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)

        interaction.followup.send.assert_awaited_once()
        call_kwargs = interaction.followup.send.call_args.kwargs
        assert "issue body" in call_kwargs.get("content", "")
        assert call_kwargs.get("view") is not None

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
    def test_preview_view_has_two_children(self):
        view = IssuePreviewView(owner="o", repo="r")
        assert len(view.children) == 2

    def test_preview_view_contains_create_button(self):
        view = IssuePreviewView(owner="o", repo="r")
        assert any(isinstance(c, CreateIssueButton) for c in view.children)

    def test_preview_view_contains_cancel_button(self):
        view = IssuePreviewView(owner="o", repo="r")
        assert any(isinstance(c, CancelIssueButton) for c in view.children)

    def test_preview_view_has_no_timeout(self):
        view = IssuePreviewView(owner="o", repo="r")
        assert view.timeout is None

    def test_preview_view_is_persistent(self):
        view = IssuePreviewView(owner="o", repo="r")
        assert view.is_persistent()
