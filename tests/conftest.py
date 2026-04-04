import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from discord.ext import commands

from src.models import CachedIssueData, IssueMetadata, PipelineData


# ---------------------------------------------------------------------------
# Shared test key material (moved from test_github_auth.py)
# ---------------------------------------------------------------------------
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEST_PRIVATE_KEY_PEM = _private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
# Expose the key object for JWT verification in test_github_auth
test_private_key = _private_key


# ---------------------------------------------------------------------------
# Isolate tests from host proxy configuration
#   needed mostly for when running in a sandbox... like in claude code
# ---------------------------------------------------------------------------
_PROXY_VARS = (
    "ALL_PROXY",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "all_proxy",
    "https_proxy",
    "http_proxy",
)


@pytest.fixture(autouse=True, scope="session")
def _clear_proxy_env():
    saved = {k: os.environ.pop(k) for k in _PROXY_VARS if k in os.environ}
    yield
    os.environ.update(saved)


# ---------------------------------------------------------------------------
# Shared test doubles
# ---------------------------------------------------------------------------
class FakeTransform:
    """Satisfies Transform protocol. Returns configurable output, records calls."""

    def __init__(self, output_text="# Title\nBody"):
        self.output_text = output_text
        self.calls: list[PipelineData] = []

    async def run(self, data: PipelineData) -> PipelineData:
        self.calls.append(data)
        return PipelineData(
            input=self.output_text,
            context={**data.context, "generated": [self.output_text]},
        )


class FakeGitHubClient:
    """Satisfies GitHubClient protocol. Returns canned URLs, records calls."""

    def __init__(self, issue_url="https://github.com/o/r/issues/1"):
        self.issue_url = issue_url
        self.create_issue_calls: list[tuple] = []
        self.check_calls: list[tuple] = []

    async def create_issue(self, owner: str, repo: str, title: str, body: str) -> str:
        self.create_issue_calls.append((owner, repo, title, body))
        return self.issue_url

    async def check_repo_installation(self, owner: str, repo: str) -> None:
        self.check_calls.append((owner, repo))


class FailingTransform:
    """Raises on run(). For error-path tests."""

    def __init__(self, error=None):
        self.error = error or RuntimeError("transform failed")

    async def run(self, data: PipelineData) -> PipelineData:
        raise self.error


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def bot():
    b = MagicMock(spec=commands.Bot)
    b.tree = MagicMock()
    return b


@pytest.fixture
def fake_transform():
    return FakeTransform()


@pytest.fixture
def failing_transform():
    return FailingTransform()


def mock_interaction():
    interaction = AsyncMock()
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=True)
    interaction.channel = MagicMock()
    interaction.client = MagicMock()
    interaction.client.github = AsyncMock()
    interaction.client.github.check_repo_installation = AsyncMock()
    interaction.client.github.create_issue = AsyncMock(
        return_value="https://github.com/o/r/issues/1"
    )
    interaction.user = MagicMock()
    interaction.user.display_name = "TestUser"
    return interaction


def make_cached(input="topic", messages=None, author="tester", link=None):
    pipeline = PipelineData(input=input, context={"messages": messages or ["msg"]})
    metadata = IssueMetadata(author_username=author, latest_message_link=link)
    return CachedIssueData(pipeline_data=pipeline, metadata=metadata)


# ---------------------------------------------------------------------------
# Cache cleanup — prevents cross-test leakage
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clear_cache():
    from src.ui import _retry_cache

    _retry_cache.clear()
    yield
    _retry_cache.clear()
