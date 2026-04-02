from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

import pytest

from src.cogs.test_issue import DebugIssueCog


@pytest.fixture
def bot():
    b = MagicMock(spec=commands.Bot)
    b.tree = MagicMock()
    return b


@pytest.fixture
def cog(bot):
    return DebugIssueCog(
        bot,
        gemini_client=AsyncMock(),
        github_token="ghp_test",
    )


class TestDebugIssueCog:
    def test_cog_instantiation(self, cog, bot):
        assert cog.bot is bot

    @pytest.mark.asyncio
    @patch("src.cogs.test_issue.read_messages")
    @patch("src.cogs.test_issue.generate_issue")
    async def test_command_defers_first(self, mock_generate, mock_read, cog):
        mock_read.return_value = ["user1: msg"]
        mock_generate.return_value = MagicMock(input="# Title\nBody", context={})

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await cog._do_test_issue(
            interaction, repo="owner/repo", topic="bug",
            filepath="convos/test1.txt", start_line=1, n=5,
        )

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)

    @pytest.mark.asyncio
    @patch("src.cogs.test_issue.read_messages")
    @patch("src.cogs.test_issue.generate_issue")
    async def test_command_calls_read_messages(self, mock_generate, mock_read, cog):
        mock_read.return_value = ["user1: msg"]
        mock_generate.return_value = MagicMock(input="# Title\nBody", context={})

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await cog._do_test_issue(
            interaction, repo="owner/repo", topic="bug",
            filepath="convos/test1.txt", start_line=3, n=10,
        )

        mock_read.assert_called_once_with(
            "convos/test1.txt", start_line=3, count=10,
        )

    @pytest.mark.asyncio
    @patch("src.cogs.test_issue.read_messages")
    @patch("src.cogs.test_issue.generate_issue")
    async def test_command_calls_gemini_with_pipeline_data(
        self, mock_generate, mock_read, cog
    ):
        mock_read.return_value = ["user1: hello", "user2: world"]
        mock_generate.return_value = MagicMock(input="generated issue", context={})

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await cog._do_test_issue(
            interaction, repo="owner/repo", topic="login bug",
            filepath="convos/test1.txt", start_line=1, n=10,
        )

        mock_generate.assert_awaited_once()
        pipeline_data = mock_generate.call_args.args[0]
        assert pipeline_data.input == "login bug"
        assert pipeline_data.context["messages"] == [
            "user1: hello",
            "user2: world",
        ]

    @pytest.mark.asyncio
    @patch("src.cogs.test_issue.read_messages")
    @patch("src.cogs.test_issue.generate_issue")
    async def test_command_sends_preview(self, mock_generate, mock_read, cog):
        mock_read.return_value = ["msg"]
        mock_generate.return_value = MagicMock(input="issue body", context={})

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await cog._do_test_issue(
            interaction, repo="owner/repo", topic="bug",
            filepath="convos/test1.txt", start_line=1, n=5,
        )

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

        await cog._do_test_issue(
            interaction, repo="owner/repo", topic="bug",
            filepath="convos/test1.txt", start_line=1, n=5,
        )
