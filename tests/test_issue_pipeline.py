from unittest.mock import AsyncMock

import discord
import pytest

from src.pipeline.create_issue import IssuePipeline
from src.models import PipelineData
from src.output.github import RepoNotInstalled
from src.cogs.ui import (
    ErrorView,
    PreviewView,
    RetryButton,
    cache_pipeline_data,
)

from tests.conftest import FakeTransform, FakeGitHubClient, FailingTransform
from tests.conftest import make_cached, mock_interaction as _mock_interaction


@pytest.fixture
def pipeline():
    return IssuePipeline(transform=FakeTransform(), github=FakeGitHubClient())


@pytest.fixture
def mock_pipeline():
    """Pipeline with AsyncMock-wrapped fakes, for orchestration tests."""
    fake = FakeTransform()
    mock_transform = AsyncMock(wraps=fake)
    mock_github = AsyncMock()
    mock_github.check_repo_installation = AsyncMock()
    mock_github.create_issue = AsyncMock(
        return_value="https://github.com/o/r/issues/1"
    )
    return IssuePipeline(transform=mock_transform, github=mock_github)


# ------------------------------------------------------------------
# Business logic
# ------------------------------------------------------------------


class TestBuildPipelineData:
    def test_sets_focus_and_messages(self, pipeline):
        data = pipeline.build_pipeline_data("login bug", ["u1: hi", "u2: bye"])
        assert data.input == "login bug"
        assert data.context["messages"] == ["u1: hi", "u2: bye"]

    def test_empty_messages(self, pipeline):
        data = pipeline.build_pipeline_data("focus", [])
        assert data.input == "focus"
        assert data.context["messages"] == []


class TestBuildCachedData:
    def test_sets_all_fields(self, pipeline):
        pd = PipelineData(input="focus", context={"messages": ["msg"]})
        cached = pipeline.build_cached_data(
            pd,
            author_username="alice",
            latest_message_link="https://discord.com/channels/1/2/3",
            owner="acme",
            repo="widgets",
        )
        assert cached.cmd_type == IssuePipeline.CMD_TYPE
        assert cached.pipeline_data is pd
        assert cached.extra["author_username"] == "alice"
        assert cached.extra["latest_message_link"] == "https://discord.com/channels/1/2/3"
        assert cached.extra["owner"] == "acme"
        assert cached.extra["repo"] == "widgets"


class TestParsePreview:
    def test_title_and_body(self):
        title, body = IssuePipeline.parse_preview("# My Title\nSome body text")
        assert title == "My Title"
        assert body == "Some body text"

    def test_title_only(self):
        title, body = IssuePipeline.parse_preview("# Title Only")
        assert title == "Title Only"
        assert body == ""


class TestBuildIssueBody:
    def test_with_link(self):
        result = IssuePipeline.build_issue_body(
            "body text", "alice", "https://discord.com/channels/1/2/3"
        )
        assert "alice" in result
        assert "https://discord.com/channels/1/2/3" in result
        assert result.startswith("body text")

    def test_without_link(self):
        result = IssuePipeline.build_issue_body("body text", "alice", None)
        assert "alice" in result
        assert "Discord" not in result

    def test_includes_model(self):
        result = IssuePipeline.build_issue_body(
            "body text", "alice", None, model="gemini-3-flash-preview"
        )
        assert "Model: gemini-3-flash-preview" in result


class TestGenerate:
    @pytest.mark.asyncio
    async def test_delegates_to_transform(self, pipeline):
        data = PipelineData(input="focus", context={"messages": ["msg"]})
        result = await pipeline.generate(data)
        assert isinstance(result, PipelineData)
        assert result.input == "# Title\nBody"
        assert pipeline.transform.calls == [data]

    @pytest.mark.asyncio
    async def test_propagates_errors(self):
        pipeline = IssuePipeline(
            transform=FailingTransform(), github=FakeGitHubClient()
        )
        data = PipelineData(input="focus", context={"messages": ["msg"]})
        with pytest.raises(RuntimeError, match="transform failed"):
            await pipeline.generate(data)


class TestCheckRepo:
    @pytest.mark.asyncio
    async def test_delegates_to_github(self, pipeline):
        await pipeline.check_repo("acme", "widgets")
        assert pipeline.github.check_calls == [("acme", "widgets")]

    @pytest.mark.asyncio
    async def test_propagates_not_installed(self):
        github = FakeGitHubClient()
        github.check_repo_installation = _raise_not_installed
        pipeline = IssuePipeline(transform=FakeTransform(), github=github)
        with pytest.raises(RepoNotInstalled):
            await pipeline.check_repo("acme", "widgets")


class TestCreateIssue:
    @pytest.mark.asyncio
    async def test_delegates_to_github(self, pipeline):
        url = await pipeline.create_issue("acme", "widgets", "title", "body")
        assert url == "https://github.com/o/r/issues/1"
        assert pipeline.github.create_issue_calls == [
            ("acme", "widgets", "title", "body")
        ]

    @pytest.mark.asyncio
    async def test_propagates_errors(self):
        github = FakeGitHubClient()
        github.create_issue = _raise_runtime
        pipeline = IssuePipeline(transform=FakeTransform(), github=github)
        with pytest.raises(RuntimeError, match="github down"):
            await pipeline.create_issue("acme", "widgets", "title", "body")


# ------------------------------------------------------------------
# Pipeline.run() orchestration
# ------------------------------------------------------------------


class TestRun:
    @pytest.mark.asyncio
    async def test_calls_transform_with_pipeline_data(self, mock_pipeline):
        interaction = _mock_interaction()
        await mock_pipeline.run(
            interaction,
            repo="owner/repo",
            focus="login bug",
            messages=["user1: hello", "user2: world"],
            latest_message_link="https://discord.com/channels/1/2/3",
        )
        mock_pipeline.transform.run.assert_awaited_once()
        pipeline_data = mock_pipeline.transform.run.call_args.args[0]
        assert pipeline_data.input == "login bug"
        assert pipeline_data.context["messages"] == ["user1: hello", "user2: world"]

    @pytest.mark.asyncio
    async def test_sends_loading_message(self, mock_pipeline):
        interaction = _mock_interaction()
        loading_msg = AsyncMock()
        interaction.followup.send.return_value = loading_msg

        await mock_pipeline.run(
            interaction,
            repo="owner/repo",
            focus="bug",
            messages=["user1: msg"],
            latest_message_link=None,
        )
        interaction.followup.send.assert_awaited_once()
        send_kwargs = interaction.followup.send.call_args.kwargs
        assert send_kwargs["wait"] is True
        embed = send_kwargs["embed"]
        assert "generat" in embed.description.lower()

    @pytest.mark.asyncio
    async def test_edits_loading_with_preview(self, mock_pipeline):
        interaction = _mock_interaction()
        loading_msg = AsyncMock()
        interaction.followup.send.return_value = loading_msg

        await mock_pipeline.run(
            interaction,
            repo="owner/repo",
            focus="bug",
            messages=["user1: msg"],
            latest_message_link=None,
        )
        loading_msg.edit.assert_awaited_once()
        edit_kwargs = loading_msg.edit.call_args.kwargs
        assert "# Title" in edit_kwargs["embed"].description
        assert isinstance(edit_kwargs["view"], PreviewView)

    @pytest.mark.asyncio
    async def test_edits_loading_with_error_on_transform_failure(self, mock_pipeline):
        mock_pipeline.transform.run.side_effect = RuntimeError("Gemini 503")
        interaction = _mock_interaction()
        loading_msg = AsyncMock()
        interaction.followup.send.return_value = loading_msg

        await mock_pipeline.run(
            interaction,
            repo="owner/repo",
            focus="bug",
            messages=["user1: msg"],
            latest_message_link=None,
        )
        loading_msg.edit.assert_awaited_once()
        edit_kwargs = loading_msg.edit.call_args.kwargs
        assert "Gemini 503" in edit_kwargs["embed"].description
        assert isinstance(edit_kwargs["view"], ErrorView)

    @pytest.mark.asyncio
    async def test_preview_includes_retry_button(self, mock_pipeline):
        interaction = _mock_interaction()
        loading_msg = AsyncMock()
        interaction.followup.send.return_value = loading_msg

        await mock_pipeline.run(
            interaction,
            repo="owner/repo",
            focus="bug",
            messages=["user1: msg"],
            latest_message_link="https://discord.com/channels/1/2/3",
        )
        edit_kwargs = loading_msg.edit.call_args.kwargs
        view = edit_kwargs["view"]
        assert any(isinstance(c, RetryButton) for c in view.children)

    @pytest.mark.asyncio
    async def test_edits_loading_with_repo_not_installed_error(self, mock_pipeline):
        mock_pipeline.github.check_repo_installation = AsyncMock(
            side_effect=RepoNotInstalled("acme", "widgets")
        )
        interaction = _mock_interaction()
        loading_msg = AsyncMock()
        interaction.followup.send.return_value = loading_msg

        await mock_pipeline.run(
            interaction,
            repo="acme/widgets",
            focus="bug",
            messages=["user1: msg"],
            latest_message_link=None,
        )
        loading_msg.edit.assert_awaited_once()
        edit_kwargs = loading_msg.edit.call_args.kwargs
        assert edit_kwargs["embed"].color == discord.Color.red()
        assert "not installed" in edit_kwargs["embed"].description.lower()
        assert "acme/widgets" in edit_kwargs["embed"].description
        mock_pipeline.transform.run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_repo_installed_proceeds_to_transform(self, mock_pipeline):
        interaction = _mock_interaction()
        await mock_pipeline.run(
            interaction,
            repo="owner/repo",
            focus="bug",
            messages=["user1: msg"],
            latest_message_link=None,
        )
        mock_pipeline.github.check_repo_installation.assert_awaited_once()
        mock_pipeline.transform.run.assert_awaited_once()


# ------------------------------------------------------------------
# CommandHandler protocol (on_retry, on_confirm, on_output_retry)
# ------------------------------------------------------------------


class TestOnRetry:
    @pytest.mark.asyncio
    async def test_shows_loading_then_result(self):
        fake = FakeTransform(output_text="# New Title\nNew body")
        pipeline = IssuePipeline(transform=fake, github=AsyncMock())

        cached = make_cached()
        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await pipeline.on_retry(interaction, cached)

        interaction.response.edit_message.assert_awaited_once()
        loading_view = interaction.response.edit_message.call_args.kwargs["view"]
        assert len(loading_view.children) == 1
        assert loading_view.children[0].disabled is True

        interaction.edit_original_response.assert_awaited_once()
        call_kwargs = interaction.edit_original_response.call_args.kwargs
        assert call_kwargs["embed"].description == "# New Title\nNew body"
        assert isinstance(call_kwargs["view"], PreviewView)

    @pytest.mark.asyncio
    async def test_transform_error_shows_error_view(self):
        mock_transform = AsyncMock()
        mock_transform.run = AsyncMock(
            side_effect=RuntimeError("503 Service Unavailable")
        )
        pipeline = IssuePipeline(transform=mock_transform, github=AsyncMock())

        cached = make_cached()
        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await pipeline.on_retry(interaction, cached)

        interaction.edit_original_response.assert_awaited_once()
        call_kwargs = interaction.edit_original_response.call_args.kwargs
        assert "503 Service Unavailable" in call_kwargs["embed"].description
        assert isinstance(call_kwargs["view"], ErrorView)

    @pytest.mark.asyncio
    async def test_error_caches_new_key_for_re_retry(self):
        mock_transform = AsyncMock()
        mock_transform.run = AsyncMock(side_effect=RuntimeError("fail"))
        pipeline = IssuePipeline(transform=mock_transform, github=AsyncMock())

        cached = make_cached()
        original_key = cache_pipeline_data(cached)

        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await pipeline.on_retry(interaction, cached)

        view = interaction.edit_original_response.call_args.kwargs["view"]
        retry_btn = [c for c in view.children if isinstance(c, RetryButton)][0]
        assert retry_btn.retry_key != original_key


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

async def _raise_not_installed(owner, repo):
    raise RepoNotInstalled(owner, repo)


async def _raise_runtime(*args):
    raise RuntimeError("github down")
