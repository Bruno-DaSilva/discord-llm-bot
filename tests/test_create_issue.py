from unittest.mock import AsyncMock, MagicMock, patch

import discord

import pytest

from src.cogs.create_issue import CreateIssueCog, CreateIssueModal
from src.utils.discord import FetchResult
from src.pipeline.create_issue import IssuePipeline

from tests.conftest import (
    FakeTransform,
    mock_fetch_result as _mock_fetch_result,
    mock_interaction as _mock_interaction,
    mock_message as _mock_message,
)


@pytest.fixture
def cog(bot):
    fake = FakeTransform()
    mock_transform = AsyncMock(wraps=fake)
    mock_github = AsyncMock()
    mock_github.check_repo_installation = AsyncMock()
    mock_github.create_issue = AsyncMock(return_value="https://github.com/o/r/issues/1")
    pipeline = IssuePipeline(transform=mock_transform, github=mock_github)
    return CreateIssueCog(bot, pipeline=pipeline)


def _channel_with_history(*messages):
    """Attach an async-generator `history` mock to a fresh channel mock."""
    channel = MagicMock()

    async def history(limit, **kwargs):
        for m in messages[:limit]:
            yield m

    channel.history = history
    return channel


class TestCreateIssueCogCommand:
    @pytest.mark.asyncio
    @patch.object(CreateIssueCog, "_run", new_callable=AsyncMock)
    async def test_command_delegates_to_run(self, mock_run, cog):
        interaction = _mock_interaction()
        await cog.create_issue_command.callback(
            cog,
            interaction,
            repo="owner/repo",
            topic="bug",
            n=10,
        )
        mock_run.assert_awaited_once_with(
            interaction,
            repo="owner/repo",
            topic="bug",
            n=10,
        )


class TestCreateIssueCog:
    def test_cog_instantiation(self, cog, bot):
        assert cog.bot is bot

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_run_defers_first(self, mock_fetch, cog):
        mock_fetch.return_value = _mock_fetch_result()
        anchor = _mock_message()
        interaction = _mock_interaction()

        await cog._run(interaction, repo="owner/repo", topic="bug", n=5, anchor=anchor)

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_run_without_anchor_resolves_latest_from_channel(
        self, mock_fetch, cog
    ):
        mock_fetch.return_value = _mock_fetch_result()
        latest = _mock_message()
        interaction = _mock_interaction()
        interaction.channel = _channel_with_history(latest)

        await cog._run(interaction, repo="owner/repo", topic="bug", n=5)

        mock_fetch.assert_awaited_once()
        call_kwargs = mock_fetch.call_args.kwargs
        assert call_kwargs["limit"] == 5
        assert call_kwargs["anchor"] is latest

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_run_with_anchor_passes_it_through(self, mock_fetch, cog):
        mock_fetch.return_value = _mock_fetch_result()
        anchor = _mock_message()
        interaction = _mock_interaction()

        await cog._run(interaction, repo="owner/repo", topic="bug", n=7, anchor=anchor)

        mock_fetch.assert_awaited_once()
        call_kwargs = mock_fetch.call_args.kwargs
        assert call_kwargs["limit"] == 7
        assert call_kwargs["anchor"] is anchor

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_run_calls_pipeline(self, mock_fetch, cog):
        mock_fetch.return_value = _mock_fetch_result(
            messages=["user1: hello", "user2: world"],
            link="https://discord.com/channels/1/2/3",
        )
        anchor = _mock_message()
        interaction = _mock_interaction()

        with patch.object(cog.pipeline, "run", new_callable=AsyncMock) as mock_run:
            await cog._run(
                interaction,
                repo="owner/repo",
                topic="login bug",
                n=10,
                anchor=anchor,
            )

            mock_run.assert_awaited_once_with(
                interaction,
                repo="owner/repo",
                topic="login bug",
                messages=["user1: hello", "user2: world"],
                latest_message_link="https://discord.com/channels/1/2/3",
                ephemeral=True,
            )

    @pytest.mark.asyncio
    async def test_run_empty_channel_sends_error(self, cog):
        interaction = _mock_interaction()
        interaction.channel = _channel_with_history()  # no messages

        with patch.object(cog.pipeline, "run", new_callable=AsyncMock) as mock_run:
            await cog._run(interaction, repo="owner/repo", topic="bug", n=5)

            interaction.followup.send.assert_awaited_once()
            content = interaction.followup.send.call_args.kwargs.get("content", "")
            assert "internal error" in content.lower()
            mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_run_empty_fetch_sends_error(self, mock_fetch, cog):
        mock_fetch.return_value = FetchResult(messages=[], latest_message_link=None)
        anchor = _mock_message()
        interaction = _mock_interaction()

        with patch.object(cog.pipeline, "run", new_callable=AsyncMock) as mock_run:
            await cog._run(
                interaction, repo="owner/repo", topic="bug", n=5, anchor=anchor
            )

            interaction.followup.send.assert_awaited_once()
            mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_run_fetch_error_sends_error_embed(self, mock_fetch, cog):
        mock_fetch.side_effect = RuntimeError("Discord API down")
        anchor = _mock_message()
        interaction = _mock_interaction()

        await cog._run(interaction, repo="owner/repo", topic="bug", n=5, anchor=anchor)

        interaction.followup.send.assert_awaited_once()
        call_kwargs = interaction.followup.send.call_args.kwargs
        assert "RuntimeError" in call_kwargs["embed"].description
        assert call_kwargs["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_expired_interaction_is_ignored(self, cog):
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.response.defer.side_effect = discord.NotFound(
            MagicMock(status=404), {"code": 10062, "message": "Unknown interaction"}
        )

        # Should not raise
        await cog._run(interaction, repo="owner/repo", topic="bug", n=5)


class TestCreateIssueModal:
    def test_modal_has_expected_fields(self, cog):
        msg = _mock_message()
        modal = CreateIssueModal(msg, cog=cog)
        assert hasattr(modal, "repo")
        assert hasattr(modal, "topic")
        assert hasattr(modal, "n")

    @pytest.mark.asyncio
    async def test_on_submit_delegates_to_run_with_anchor(self, cog):
        msg = _mock_message()
        modal = CreateIssueModal(msg, cog=cog)
        modal.repo._value = "owner/repo"
        modal.topic._value = "bug report"
        modal.n._value = "15"
        interaction = _mock_interaction()

        with patch.object(cog, "_run", new_callable=AsyncMock) as mock_run:
            await modal.on_submit(interaction)

            mock_run.assert_awaited_once_with(
                interaction,
                repo="owner/repo",
                topic="bug report",
                n=15,
                anchor=msg,
            )

    @pytest.mark.asyncio
    async def test_on_submit_defaults_n_when_blank(self, cog):
        msg = _mock_message()
        modal = CreateIssueModal(msg, cog=cog)
        modal.repo._value = "owner/repo"
        modal.topic._value = "bug"
        modal.n._value = ""
        interaction = _mock_interaction()

        with patch.object(cog, "_run", new_callable=AsyncMock) as mock_run:
            await modal.on_submit(interaction)
            assert mock_run.call_args.kwargs["n"] == 20

    @pytest.mark.asyncio
    async def test_on_error_sends_ephemeral_error(self, cog):
        msg = _mock_message()
        modal = CreateIssueModal(msg, cog=cog)
        interaction = _mock_interaction()
        error = RuntimeError("something broke")
        await modal.on_error(interaction, error)
        interaction.followup.send.assert_awaited_once()
        call_kwargs = interaction.followup.send.call_args.kwargs
        assert call_kwargs["ephemeral"] is True
        assert "something broke" in call_kwargs["embed"].description

    @pytest.mark.asyncio
    async def test_on_error_defers_if_not_responded(self, cog):
        msg = _mock_message()
        modal = CreateIssueModal(msg, cog=cog)
        interaction = _mock_interaction()
        interaction.response.is_done = MagicMock(return_value=False)
        error = RuntimeError("boom")
        await modal.on_error(interaction, error)
        interaction.response.defer.assert_awaited_once_with(ephemeral=True)


class TestContextMenu:
    def test_context_menu_registered_on_tree(self, bot):
        mock_transform = AsyncMock()
        mock_transform.run.return_value = MagicMock(input="# Title\nBody", context={})
        pipeline = IssuePipeline(transform=mock_transform, github=AsyncMock())
        CreateIssueCog(bot, pipeline=pipeline)
        bot.tree.add_command.assert_called_once()
        cmd = bot.tree.add_command.call_args.args[0]
        assert cmd.name == "Create Issue"

    @pytest.mark.asyncio
    async def test_context_menu_callback_sends_modal(self, cog):
        msg = MagicMock()
        interaction = _mock_interaction()
        await cog.create_issue_context_menu(interaction, msg)
        interaction.response.send_modal.assert_awaited_once()
        modal = interaction.response.send_modal.call_args.args[0]
        assert isinstance(modal, CreateIssueModal)
        assert modal.target_message is msg

    @pytest.mark.asyncio
    async def test_cog_unload_removes_context_menu(self, cog, bot):
        await cog.cog_unload()
        bot.tree.remove_command.assert_called_once()
