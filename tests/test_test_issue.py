from unittest.mock import AsyncMock, MagicMock, patch

import discord

import pytest

from src.cogs.test_issue import DebugIssueCog
from src.ui import ErrorView, RetryIssueButton

from tests.conftest import FakeTransform


@pytest.fixture
def cog(bot):
    fake = FakeTransform()
    mock_transform = AsyncMock(wraps=fake)
    return DebugIssueCog(bot, transform=mock_transform)


class TestDebugIssueCogCommand:
    @pytest.mark.asyncio
    @patch.object(DebugIssueCog, "_do_test_issue", new_callable=AsyncMock)
    async def test_command_delegates_to_do_test_issue(self, mock_do, cog):
        interaction = AsyncMock()
        await cog.test_issue_command.callback(
            cog, interaction, repo="owner/repo", topic="bug",
            filepath="convos/test.txt", start_line=5, n=10,
        )
        mock_do.assert_awaited_once_with(
            interaction, repo="owner/repo", topic="bug",
            filepath="convos/test.txt", start_line=5, n=10,
        )


class TestDebugIssueCog:
    def test_cog_instantiation(self, cog, bot):
        assert cog.bot is bot

    @pytest.mark.asyncio
    @patch("src.cogs.test_issue.read_messages")
    async def test_command_defers_first(self, mock_read, cog):
        mock_read.return_value = ["user1: msg"]

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await cog._do_test_issue(
            interaction, repo="owner/repo", topic="bug",
            filepath="convos/test1.txt", start_line=1, n=5,
        )

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)

    @pytest.mark.asyncio
    @patch("src.cogs.test_issue.read_messages")
    async def test_command_calls_read_messages(self, mock_read, cog):
        mock_read.return_value = ["user1: msg"]

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
    async def test_command_calls_transform_with_pipeline_data(
        self, mock_read, cog
    ):
        mock_read.return_value = ["user1: hello", "user2: world"]

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await cog._do_test_issue(
            interaction, repo="owner/repo", topic="login bug",
            filepath="convos/test1.txt", start_line=1, n=10,
        )

        cog.transform.run.assert_awaited_once()
        pipeline_data = cog.transform.run.call_args.args[0]
        assert pipeline_data.input == "login bug"
        assert pipeline_data.context["messages"] == [
            "user1: hello",
            "user2: world",
        ]

    @pytest.mark.asyncio
    @patch("src.cogs.test_issue.read_messages")
    async def test_command_sends_preview(self, mock_read, cog):
        mock_read.return_value = ["msg"]

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await cog._do_test_issue(
            interaction, repo="owner/repo", topic="bug",
            filepath="convos/test1.txt", start_line=1, n=5,
        )

        interaction.followup.send.assert_awaited_once()
        call_kwargs = interaction.followup.send.call_args.kwargs
        embed = call_kwargs.get("embed")
        assert embed is not None
        assert "# Title" in embed.description
        assert call_kwargs.get("view") is not None

    @pytest.mark.asyncio
    @patch("src.cogs.test_issue.read_messages")
    async def test_no_messages_sends_error(self, mock_read, cog):
        mock_read.return_value = []

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await cog._do_test_issue(
            interaction, repo="owner/repo", topic="bug",
            filepath="convos/test1.txt", start_line=1, n=5,
        )

        interaction.followup.send.assert_awaited_once()
        content = interaction.followup.send.call_args.kwargs.get("content", "")
        assert "internal error" in content.lower()
        cog.transform.run.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.cogs.test_issue.read_messages")
    async def test_transform_error_sends_error_embed(self, mock_read, cog):
        mock_read.return_value = ["msg"]
        cog.transform.run.side_effect = RuntimeError("Gemini 503")

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await cog._do_test_issue(
            interaction, repo="owner/repo", topic="bug",
            filepath="convos/test1.txt", start_line=1, n=5,
        )

        interaction.followup.send.assert_awaited_once()
        call_kwargs = interaction.followup.send.call_args.kwargs
        assert "RuntimeError" in call_kwargs["embed"].description
        assert isinstance(call_kwargs["view"], ErrorView)

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

    @pytest.mark.asyncio
    @patch("src.cogs.test_issue.read_messages")
    async def test_command_sends_preview_with_retry_button(self, mock_read, cog):
        mock_read.return_value = ["msg"]

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await cog._do_test_issue(
            interaction, repo="owner/repo", topic="bug",
            filepath="convos/test1.txt", start_line=1, n=5,
        )

        call_kwargs = interaction.followup.send.call_args.kwargs
        view = call_kwargs["view"]
        assert any(isinstance(c, RetryIssueButton) for c in view.children)
