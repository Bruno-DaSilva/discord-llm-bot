from unittest.mock import AsyncMock, MagicMock, patch

from discord.ext import commands

import pytest

from src.cogs.create_issue import CreateIssueCog


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
    async def test_command_defers_first(
        self, mock_generate, mock_fetch, cog
    ):
        mock_fetch.return_value = ["user1: msg"]
        mock_generate.return_value = MagicMock(
            input="# Title\nBody", context={}
        )

        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.channel = MagicMock()

        await cog._do_create_issue(
            interaction, repo="owner/repo", topic="bug", n=5
        )

        interaction.response.defer.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages")
    @patch("src.cogs.create_issue.generate_issue")
    async def test_command_fetches_messages(
        self, mock_generate, mock_fetch, cog
    ):
        mock_fetch.return_value = ["user1: msg"]
        mock_generate.return_value = MagicMock(
            input="# Title\nBody", context={}
        )

        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.channel = MagicMock()

        await cog._do_create_issue(
            interaction, repo="owner/repo", topic="bug", n=5
        )

        mock_fetch.assert_awaited_once_with(interaction.channel, limit=5)

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages")
    @patch("src.cogs.create_issue.generate_issue")
    async def test_command_calls_gemini_with_pipeline_data(
        self, mock_generate, mock_fetch, cog
    ):
        mock_fetch.return_value = ["user1: hello", "user2: world"]
        mock_generate.return_value = MagicMock(
            input="generated issue", context={}
        )

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
    async def test_command_sends_preview(
        self, mock_generate, mock_fetch, cog
    ):
        mock_fetch.return_value = ["msg"]
        mock_generate.return_value = MagicMock(
            input="issue body", context={}
        )

        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.channel = MagicMock()

        await cog._do_create_issue(
            interaction, repo="owner/repo", topic="bug", n=5
        )

        interaction.edit_original_response.assert_awaited_once()
        call_kwargs = interaction.edit_original_response.call_args.kwargs
        assert "issue body" in call_kwargs.get("content", "")
        assert call_kwargs.get("view") is not None
