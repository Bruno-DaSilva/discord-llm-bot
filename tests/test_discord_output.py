from unittest.mock import MagicMock

import pytest

from src.output.discord import fetch_messages


class TestFetchMessages:
    @pytest.mark.asyncio
    async def test_returns_formatted_messages(self):
        msg1 = MagicMock()
        msg1.author.display_name = "Alice"
        msg1.content = "login is broken"

        msg2 = MagicMock()
        msg2.author.display_name = "Bob"
        msg2.content = "same here"

        channel = MagicMock()

        async def mock_history(limit):
            for msg in [msg1, msg2]:
                yield msg

        channel.history = mock_history

        result = await fetch_messages(channel, limit=10)

        assert len(result) == 2
        assert "Alice" in result[0]
        assert "login is broken" in result[0]
        assert "Bob" in result[1]

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        channel = MagicMock()

        messages_yielded = []

        async def mock_history(limit):
            for i in range(limit):
                msg = MagicMock()
                msg.author.display_name = f"user{i}"
                msg.content = f"msg{i}"
                messages_yielded.append(msg)
                yield msg

        channel.history = mock_history

        result = await fetch_messages(channel, limit=5)
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_empty_channel(self):
        channel = MagicMock()

        async def mock_history(limit):
            return
            yield

        channel.history = mock_history

        result = await fetch_messages(channel, limit=10)
        assert result == []
