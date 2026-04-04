from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.cogs.engine_issue import EngineIssueCog, EngineIssueModal, REPO
from src.output.discord import FetchResult
from src.ui import ConfirmButton, ErrorView

from tests.conftest import FakeTransform, mock_interaction as _mock_interaction


@pytest.fixture
def cog(bot):
    fake = FakeTransform()
    mock_transform = AsyncMock(wraps=fake)
    mock_github = AsyncMock()
    mock_github.check_repo_installation = AsyncMock()
    mock_github.create_issue = AsyncMock(
        return_value="https://github.com/o/r/issues/1"
    )
    return EngineIssueCog(bot, transform=mock_transform, github=mock_github)


class TestEngineIssueCogCommand:
    @pytest.mark.asyncio
    @patch.object(EngineIssueCog, "_do_engine_issue", new_callable=AsyncMock)
    async def test_command_delegates(self, mock_do, cog):
        interaction = _mock_interaction()
        await cog.engine_issue_command.callback(
            cog,
            interaction,
            topic="bug",
            n=10,
        )
        mock_do.assert_awaited_once_with(interaction, topic="bug", n=10)

    def test_hardcoded_repo(self):
        assert REPO == "beyond-all-reason/recoilengine"


class TestEngineIssueCog:
    def test_cog_instantiation(self, cog, bot):
        assert cog.bot is bot

    def _mock_fetch_result(
        self, messages=None, link="https://discord.com/channels/1/2/3"
    ):
        return FetchResult(
            messages=messages or ["user1: msg"],
            latest_message_link=link,
        )

    @pytest.mark.asyncio
    @patch("src.cogs.engine_issue.fetch_messages_with_metadata")
    async def test_command_defers_first(self, mock_fetch, cog):
        mock_fetch.return_value = self._mock_fetch_result()
        interaction = _mock_interaction()
        await cog._do_engine_issue(interaction, topic="bug", n=5)
        interaction.response.defer.assert_awaited_once_with(ephemeral=True)

    @pytest.mark.asyncio
    @patch("src.cogs.engine_issue.fetch_messages_with_metadata")
    async def test_command_fetches_messages(self, mock_fetch, cog):
        mock_fetch.return_value = self._mock_fetch_result()
        interaction = _mock_interaction()
        await cog._do_engine_issue(interaction, topic="bug", n=5)
        mock_fetch.assert_awaited_once_with(interaction.channel, limit=5)

    @pytest.mark.asyncio
    @patch("src.cogs.engine_issue.fetch_messages_with_metadata")
    async def test_command_passes_hardcoded_repo(self, mock_fetch, cog):
        mock_fetch.return_value = self._mock_fetch_result()
        interaction = _mock_interaction()
        await cog._do_engine_issue(interaction, topic="bug", n=5)
        interaction.followup.send.assert_awaited_once()
        call_kwargs = interaction.followup.send.call_args.kwargs
        view = call_kwargs["view"]
        confirm_btn = [c for c in view.children if isinstance(c, ConfirmButton)][0]
        from src.ui import get_cached_pipeline_data

        cached = get_cached_pipeline_data(confirm_btn.cache_key)
        assert cached.extra["owner"] == "beyond-all-reason"
        assert cached.extra["repo"] == "recoilengine"

    @pytest.mark.asyncio
    @patch("src.cogs.engine_issue.fetch_messages_with_metadata")
    async def test_no_messages_sends_error(self, mock_fetch, cog):
        mock_fetch.return_value = FetchResult(messages=[], latest_message_link=None)
        interaction = _mock_interaction()
        await cog._do_engine_issue(interaction, topic="bug", n=5)
        interaction.followup.send.assert_awaited_once()
        call_args = interaction.followup.send.call_args
        content = (
            call_args.kwargs.get("content") or call_args.args[0]
            if call_args.args
            else call_args.kwargs.get("content", "")
        )
        assert "internal error" in content.lower()
        cog.transform.run.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.cogs.engine_issue.fetch_messages_with_metadata")
    async def test_transform_error_sends_error_embed(self, mock_fetch, cog):
        mock_fetch.return_value = self._mock_fetch_result()
        cog.transform.run.side_effect = RuntimeError("Gemini 503")
        interaction = _mock_interaction()
        await cog._do_engine_issue(interaction, topic="bug", n=5)
        interaction.followup.send.assert_awaited_once()
        call_kwargs = interaction.followup.send.call_args.kwargs
        assert "Gemini 503" in call_kwargs["embed"].description
        assert isinstance(call_kwargs["view"], ErrorView)

    @pytest.mark.asyncio
    async def test_expired_interaction_is_ignored(self, cog):
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.response.defer.side_effect = discord.NotFound(
            MagicMock(status=404), {"code": 10062, "message": "Unknown interaction"}
        )
        await cog._do_engine_issue(interaction, topic="bug", n=5)


class TestEngineIssueModal:
    def _mock_message(self, *, guild_id=111, channel_id=222, message_id=333):
        msg = MagicMock()
        msg.author.display_name = "Alice"
        msg.content = "something is broken"
        msg.id = message_id
        msg.channel.id = channel_id
        msg.guild.id = guild_id
        return msg

    def test_modal_has_expected_fields(self, cog):
        msg = self._mock_message()
        modal = EngineIssueModal(msg, cog=cog)
        assert hasattr(modal, "topic")
        assert hasattr(modal, "n")

    @pytest.mark.asyncio
    @patch("src.cogs.engine_issue.fetch_messages_with_metadata")
    async def test_on_submit_defers(self, mock_fetch, cog):
        mock_fetch.return_value = FetchResult(
            messages=["Bob: earlier"], latest_message_link=None
        )
        msg = self._mock_message()
        modal = EngineIssueModal(msg, cog=cog)
        modal.topic._value = "bug report"
        modal.n._value = "20"
        interaction = _mock_interaction()
        await modal.on_submit(interaction)
        interaction.response.defer.assert_awaited_once_with(ephemeral=True)

    @pytest.mark.asyncio
    @patch("src.cogs.engine_issue.fetch_messages_with_metadata")
    async def test_on_submit_uses_hardcoded_repo(self, mock_fetch, cog):
        mock_fetch.return_value = FetchResult(
            messages=["Bob: earlier"], latest_message_link=None
        )
        msg = self._mock_message()
        modal = EngineIssueModal(msg, cog=cog)
        modal.topic._value = "bug report"
        modal.n._value = "20"
        interaction = _mock_interaction()
        await modal.on_submit(interaction)
        call_kwargs = interaction.followup.send.call_args.kwargs
        view = call_kwargs["view"]
        confirm_btn = [c for c in view.children if isinstance(c, ConfirmButton)][0]
        from src.ui import get_cached_pipeline_data

        cached = get_cached_pipeline_data(confirm_btn.cache_key)
        assert cached.extra["owner"] == "beyond-all-reason"
        assert cached.extra["repo"] == "recoilengine"

    @pytest.mark.asyncio
    @patch("src.cogs.engine_issue.fetch_messages_with_metadata")
    async def test_on_submit_prepends_target_message(self, mock_fetch, cog):
        mock_fetch.return_value = FetchResult(
            messages=["Bob: earlier"], latest_message_link=None
        )
        msg = self._mock_message()
        modal = EngineIssueModal(msg, cog=cog)
        modal.topic._value = "bug report"
        modal.n._value = "20"
        interaction = _mock_interaction()
        await modal.on_submit(interaction)
        cog.transform.run.assert_awaited_once()
        pipeline_data = cog.transform.run.call_args.args[0]
        assert pipeline_data.context["messages"][0] == "Alice: something is broken"
        assert pipeline_data.context["messages"][1] == "Bob: earlier"


class TestEngineContextMenu:
    def test_context_menu_registered_on_tree(self, bot):
        mock_transform = AsyncMock()
        EngineIssueCog(bot, transform=mock_transform, github=AsyncMock())
        bot.tree.add_command.assert_called_once()
        cmd = bot.tree.add_command.call_args.args[0]
        assert cmd.name == "Engine Issue"

    @pytest.mark.asyncio
    async def test_context_menu_callback_sends_modal(self, cog):
        msg = MagicMock()
        interaction = _mock_interaction()
        await cog.engine_issue_context_menu(interaction, msg)
        interaction.response.send_modal.assert_awaited_once()
        modal = interaction.response.send_modal.call_args.args[0]
        assert isinstance(modal, EngineIssueModal)
        assert modal.target_message is msg

    @pytest.mark.asyncio
    async def test_cog_unload_removes_context_menu(self, cog, bot):
        await cog.cog_unload()
        bot.tree.remove_command.assert_called_once()
