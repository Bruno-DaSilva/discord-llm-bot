import pytest

from src.pipeline.create_issue import IssuePipeline
from src.models import PipelineData
from src.output.github import RepoNotInstalled

from tests.conftest import FakeTransform, FakeGitHubClient, FailingTransform


@pytest.fixture
def pipeline():
    return IssuePipeline(transform=FakeTransform(), github=FakeGitHubClient())


class TestBuildPipelineData:
    def test_sets_topic_and_messages(self, pipeline):
        data = pipeline.build_pipeline_data("login bug", ["u1: hi", "u2: bye"])
        assert data.input == "login bug"
        assert data.context["messages"] == ["u1: hi", "u2: bye"]

    def test_empty_messages(self, pipeline):
        data = pipeline.build_pipeline_data("topic", [])
        assert data.input == "topic"
        assert data.context["messages"] == []


class TestBuildCachedData:
    def test_sets_all_fields(self, pipeline):
        pd = PipelineData(input="topic", context={"messages": ["msg"]})
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
        data = PipelineData(input="topic", context={"messages": ["msg"]})
        result = await pipeline.generate(data)
        assert isinstance(result, PipelineData)
        assert result.input == "# Title\nBody"
        assert pipeline.transform.calls == [data]

    @pytest.mark.asyncio
    async def test_propagates_errors(self):
        pipeline = IssuePipeline(
            transform=FailingTransform(), github=FakeGitHubClient()
        )
        data = PipelineData(input="topic", context={"messages": ["msg"]})
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


async def _raise_not_installed(owner, repo):
    raise RepoNotInstalled(owner, repo)


async def _raise_runtime(*args):
    raise RuntimeError("github down")
