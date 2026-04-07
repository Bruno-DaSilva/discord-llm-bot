from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.sentry_tree import SentryCommandTree


@pytest.fixture
def tree():
    client = MagicMock()
    client._connection._command_tree = None
    return SentryCommandTree(client)


@pytest.fixture
def interaction():
    inter = AsyncMock()
    inter.data = {"name": "create-issue", "type": 1}
    inter.extras = {}
    inter.user.name = "dudewhat"
    return inter


def _fake_start_trace(expected_op=None, expected_name=None, expected_data=None):
    """Return a patched start_trace that records what it was called with."""
    calls = []

    @asynccontextmanager
    async def fake(op, name, *, data=None):
        calls.append({"op": op, "name": name, "data": data})
        yield

    return fake, calls


class TestSentryCommandTree:
    @pytest.mark.asyncio
    async def test_starts_trace_with_correct_op_and_name(self, tree, interaction):
        fake, calls = _fake_start_trace()

        with (
            patch("src.utils.sentry_tree.start_trace", side_effect=fake),
            patch("src.utils.sentry_tree.get_trace_headers", return_value={}),
            patch.object(type(tree).__bases__[0], "_call", new_callable=AsyncMock),
        ):
            await tree._call(interaction)

            assert len(calls) == 1
            assert calls[0]["op"] == "discord.command"
            assert calls[0]["name"] == "dudewhat create-issue"

    @pytest.mark.asyncio
    async def test_sets_agent_name_data(self, tree, interaction):
        fake, calls = _fake_start_trace()

        with (
            patch("src.utils.sentry_tree.start_trace", side_effect=fake),
            patch("src.utils.sentry_tree.get_trace_headers", return_value={}),
            patch.object(type(tree).__bases__[0], "_call", new_callable=AsyncMock),
        ):
            await tree._call(interaction)

            assert calls[0]["data"] == {"gen_ai.agent.name": "create-issue"}

    @pytest.mark.asyncio
    async def test_delegates_to_parent_call(self, tree, interaction):
        fake, _ = _fake_start_trace()

        with (
            patch("src.utils.sentry_tree.start_trace", side_effect=fake),
            patch("src.utils.sentry_tree.get_trace_headers", return_value={}),
            patch.object(type(tree).__bases__[0], "_call", new_callable=AsyncMock) as mock_super,
        ):
            await tree._call(interaction)

            mock_super.assert_awaited_once_with(interaction)

    @pytest.mark.asyncio
    async def test_stores_trace_headers_on_interaction(self, tree, interaction):
        fake, _ = _fake_start_trace()
        headers = {"sentry-trace": "00-abc-def-01", "baggage": "sentry-trace_id=abc"}

        with (
            patch("src.utils.sentry_tree.start_trace", side_effect=fake),
            patch("src.utils.sentry_tree.get_trace_headers", return_value=headers),
            patch.object(type(tree).__bases__[0], "_call", new_callable=AsyncMock),
        ):
            await tree._call(interaction)

            assert interaction.extras["sentry_trace_headers"] == headers

    @pytest.mark.asyncio
    async def test_stores_trace_headers_on_slotted_interaction(self, tree):
        class SlottedInteraction:
            __slots__ = ("data", "extras", "user")

            def __init__(self):
                self.data = {"name": "engine-issue", "type": 1}
                self.extras = {}
                self.user = MagicMock()
                self.user.name = "testuser"

        interaction = SlottedInteraction()
        fake, _ = _fake_start_trace()
        headers = {"sentry-trace": "00-trace-01", "baggage": "bag"}

        with (
            patch("src.utils.sentry_tree.start_trace", side_effect=fake),
            patch("src.utils.sentry_tree.get_trace_headers", return_value=headers),
            patch.object(type(tree).__bases__[0], "_call", new_callable=AsyncMock),
        ):
            await tree._call(interaction)

            assert interaction.extras["sentry_trace_headers"] == headers
            with pytest.raises(AttributeError):
                interaction._sentry_trace_headers = "should fail"

    @pytest.mark.asyncio
    async def test_falls_back_to_unknown_when_no_data(self, tree):
        interaction = AsyncMock()
        interaction.data = None
        interaction.extras = {}

        fake, calls = _fake_start_trace()

        with (
            patch("src.utils.sentry_tree.start_trace", side_effect=fake),
            patch("src.utils.sentry_tree.get_trace_headers", return_value={}),
            patch.object(type(tree).__bases__[0], "_call", new_callable=AsyncMock),
        ):
            await tree._call(interaction)

            username = interaction.user.name
            assert calls[0]["name"] == f"{username} unknown"
