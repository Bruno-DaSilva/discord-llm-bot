from unittest.mock import AsyncMock, MagicMock, patch

import discord

import pytest

from src.cogs.create_issue import CreateIssueCog, CreateIssueModal, IssuePreviewView
from src.output.discord import FetchResult
from src.output.github import RepoNotInstalled
from src.ui import CancelIssueButton, CreateIssueButton, ErrorView, RetryIssueButton

from tests.conftest import FakeTransform, mock_interaction as _mock_interaction


@pytest.fixture
def cog(bot):
    fake = FakeTransform()
    mock_transform = AsyncMock(wraps=fake)
    return CreateIssueCog(bot, transform=mock_transform)


class TestCreateIssueCogCommand:
    @pytest.mark.asyncio
    @patch.object(CreateIssueCog, "_do_create_issue", new_callable=AsyncMock)
    async def test_command_delegates_to_do_create_issue(self, mock_do, cog):
        interaction = _mock_interaction()
        await cog.create_issue_command.callback(
            cog,
            interaction,
            repo="owner/repo",
            topic="bug",
            n=10,
        )
        mock_do.assert_awaited_once_with(
            interaction,
            repo="owner/repo",
            topic="bug",
            n=10,
        )


class TestRunPipeline:
    @pytest.mark.asyncio
    async def test_calls_transform_with_pipeline_data(self, cog):
        interaction = _mock_interaction()
        await cog._run_pipeline(
            interaction,
            repo="owner/repo",
            topic="login bug",
            messages=["user1: hello", "user2: world"],
            latest_message_link="https://discord.com/channels/1/2/3",
        )
        cog.transform.run.assert_awaited_once()
        pipeline_data = cog.transform.run.call_args.args[0]
        assert pipeline_data.input == "login bug"
        assert pipeline_data.context["messages"] == ["user1: hello", "user2: world"]

    @pytest.mark.asyncio
    async def test_sends_preview_embed(self, cog):
        interaction = _mock_interaction()
        await cog._run_pipeline(
            interaction,
            repo="owner/repo",
            topic="bug",
            messages=["user1: msg"],
            latest_message_link=None,
        )
        interaction.followup.send.assert_awaited_once()
        call_kwargs = interaction.followup.send.call_args.kwargs
        assert "# Title" in call_kwargs["embed"].description
        assert isinstance(call_kwargs["view"], IssuePreviewView)

    @pytest.mark.asyncio
    async def test_sends_error_embed_on_transform_failure(self, cog):
        cog.transform.run.side_effect = RuntimeError("Gemini 503")
        interaction = _mock_interaction()
        await cog._run_pipeline(
            interaction,
            repo="owner/repo",
            topic="bug",
            messages=["user1: msg"],
            latest_message_link=None,
        )
        interaction.followup.send.assert_awaited_once()
        call_kwargs = interaction.followup.send.call_args.kwargs
        assert "Gemini 503" in call_kwargs["embed"].description
        assert isinstance(call_kwargs["view"], ErrorView)

    @pytest.mark.asyncio
    async def test_preview_includes_retry_button(self, cog):
        interaction = _mock_interaction()
        await cog._run_pipeline(
            interaction,
            repo="owner/repo",
            topic="bug",
            messages=["user1: msg"],
            latest_message_link="https://discord.com/channels/1/2/3",
        )
        call_kwargs = interaction.followup.send.call_args.kwargs
        view = call_kwargs["view"]
        assert any(isinstance(c, RetryIssueButton) for c in view.children)

    @pytest.mark.asyncio
    async def test_repo_not_installed_sends_error_embed(self, cog):
        interaction = _mock_interaction()
        interaction.client.github.check_repo_installation = AsyncMock(
            side_effect=RepoNotInstalled("acme", "widgets")
        )
        await cog._run_pipeline(
            interaction,
            repo="acme/widgets",
            topic="bug",
            messages=["user1: msg"],
            latest_message_link=None,
        )
        interaction.followup.send.assert_awaited_once()
        call_kwargs = interaction.followup.send.call_args.kwargs
        assert call_kwargs["embed"].color == discord.Color.red()
        assert "not installed" in call_kwargs["embed"].description.lower()
        assert "acme/widgets" in call_kwargs["embed"].description
        cog.transform.run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_repo_installed_proceeds_to_transform(self, cog):
        interaction = _mock_interaction()
        await cog._run_pipeline(
            interaction,
            repo="owner/repo",
            topic="bug",
            messages=["user1: msg"],
            latest_message_link=None,
        )
        interaction.client.github.check_repo_installation.assert_awaited_once()
        cog.transform.run.assert_awaited_once()


class TestCreateIssueCog:
    def test_cog_instantiation(self, cog, bot):
        assert cog.bot is bot

    def _mock_fetch_result(
        self, messages=None, link="https://discord.com/channels/1/2/3"
    ):
        return FetchResult(
            messages=messages or ["user1: msg"],
            latest_message_link=link,
        )

    def _mock_interaction(self):
        return _mock_interaction()

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
    async def test_command_calls_transform_with_pipeline_data(self, mock_fetch, cog):
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
        content = (
            call_args.kwargs.get("content") or call_args.args[0]
            if call_args.args
            else call_args.kwargs.get("content", "")
        )
        assert "internal error" in content.lower()
        cog.transform.run.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_transform_error_sends_error_embed(self, mock_fetch, cog):
        mock_fetch.return_value = self._mock_fetch_result()
        cog.transform.run.side_effect = RuntimeError("Gemini 503")

        interaction = self._mock_interaction()

        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)

        interaction.followup.send.assert_awaited_once()
        call_kwargs = interaction.followup.send.call_args.kwargs
        assert "Gemini 503" in call_kwargs["embed"].description
        assert isinstance(call_kwargs["view"], ErrorView)
        assert any(
            isinstance(c, RetryIssueButton) for c in call_kwargs["view"].children
        )

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_fetch_error_sends_error_embed(self, mock_fetch, cog):
        mock_fetch.side_effect = RuntimeError("Discord API down")
        interaction = self._mock_interaction()

        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)

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
        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)


class TestIssuePreviewView:
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

        interaction = _mock_interaction()

        await cog._do_create_issue(interaction, repo="owner/repo", topic="bug", n=5)

        call_kwargs = interaction.followup.send.call_args.kwargs
        view = call_kwargs["view"]
        assert any(isinstance(c, RetryIssueButton) for c in view.children)


class TestCreateIssueModal:
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
        modal = CreateIssueModal(msg, cog=cog)
        assert hasattr(modal, "repo")
        assert hasattr(modal, "topic")
        assert hasattr(modal, "n")

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_on_submit_defers(self, mock_fetch, cog):
        mock_fetch.return_value = FetchResult(
            messages=["Bob: earlier"], latest_message_link=None
        )
        msg = self._mock_message()
        modal = CreateIssueModal(msg, cog=cog)
        modal.repo._value = "owner/repo"
        modal.topic._value = "bug report"
        modal.n._value = "20"
        interaction = _mock_interaction()
        await modal.on_submit(interaction)
        interaction.response.defer.assert_awaited_once_with(ephemeral=True)

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_on_submit_fetches_messages_anchored_at_target(self, mock_fetch, cog):
        mock_fetch.return_value = FetchResult(
            messages=["Bob: earlier"], latest_message_link=None
        )
        msg = self._mock_message()
        modal = CreateIssueModal(msg, cog=cog)
        modal.repo._value = "owner/repo"
        modal.topic._value = "bug report"
        modal.n._value = "20"
        interaction = _mock_interaction()
        await modal.on_submit(interaction)
        mock_fetch.assert_awaited_once_with(msg.channel, limit=19, before=msg)

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_on_submit_prepends_target_message(self, mock_fetch, cog):
        mock_fetch.return_value = FetchResult(
            messages=["Bob: earlier"], latest_message_link=None
        )
        msg = self._mock_message()
        modal = CreateIssueModal(msg, cog=cog)
        modal.repo._value = "owner/repo"
        modal.topic._value = "bug report"
        modal.n._value = "20"
        interaction = _mock_interaction()
        await modal.on_submit(interaction)
        cog.transform.run.assert_awaited_once()
        pipeline_data = cog.transform.run.call_args.args[0]
        assert pipeline_data.context["messages"][0] == "Alice: something is broken"
        assert pipeline_data.context["messages"][1] == "Bob: earlier"

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_on_submit_builds_message_link(self, mock_fetch, cog):
        mock_fetch.return_value = FetchResult(messages=[], latest_message_link=None)
        msg = self._mock_message(guild_id=1, channel_id=2, message_id=3)
        modal = CreateIssueModal(msg, cog=cog)
        modal.repo._value = "owner/repo"
        modal.topic._value = "bug"
        modal.n._value = "20"
        interaction = _mock_interaction()
        await modal.on_submit(interaction)
        from src.ui import get_cached_pipeline_data

        call_kwargs = interaction.followup.send.call_args.kwargs
        view = call_kwargs["view"]
        create_btn = [c for c in view.children if isinstance(c, CreateIssueButton)][0]
        cached = get_cached_pipeline_data(create_btn.cache_key)
        assert (
            cached.metadata.latest_message_link == "https://discord.com/channels/1/2/3"
        )

    @pytest.mark.asyncio
    @patch("src.cogs.create_issue.fetch_messages_with_metadata")
    async def test_on_submit_handles_no_guild(self, mock_fetch, cog):
        mock_fetch.return_value = FetchResult(messages=[], latest_message_link=None)
        msg = self._mock_message()
        msg.guild = None
        modal = CreateIssueModal(msg, cog=cog)
        modal.repo._value = "owner/repo"
        modal.topic._value = "bug"
        modal.n._value = "20"
        interaction = _mock_interaction()
        await modal.on_submit(interaction)
        from src.ui import get_cached_pipeline_data

        call_kwargs = interaction.followup.send.call_args.kwargs
        view = call_kwargs["view"]
        create_btn = [c for c in view.children if isinstance(c, CreateIssueButton)][0]
        cached = get_cached_pipeline_data(create_btn.cache_key)
        assert cached.metadata.latest_message_link is None

    @pytest.mark.asyncio
    async def test_on_error_sends_ephemeral_error(self, cog):
        msg = self._mock_message()
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
        msg = self._mock_message()
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
        CreateIssueCog(bot, transform=mock_transform)
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
