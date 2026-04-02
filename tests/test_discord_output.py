from unittest.mock import MagicMock

import pytest

from src.output.discord import fetch_messages, fetch_messages_with_metadata


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


class TestFetchMessagesWithMetadata:
    def _make_msg(self, name, content, msg_id=100, guild_id=1, channel_id=2):
        msg = MagicMock()
        msg.author.display_name = name
        msg.content = content
        msg.id = msg_id
        msg.guild.id = guild_id
        msg.channel.id = channel_id
        return msg

    @pytest.mark.asyncio
    async def test_returns_messages_list(self):
        msg1 = self._make_msg("Alice", "hello", msg_id=200)
        msg2 = self._make_msg("Bob", "world", msg_id=100)
        channel = MagicMock()

        async def mock_history(limit):
            for m in [msg1, msg2]:
                yield m

        channel.history = mock_history

        result = await fetch_messages_with_metadata(channel, limit=10)
        assert len(result.messages) == 2
        assert "Alice" in result.messages[0]

    @pytest.mark.asyncio
    async def test_latest_message_link_format(self):
        msg = self._make_msg("Alice", "hi", msg_id=999, guild_id=111, channel_id=222)
        channel = MagicMock()

        async def mock_history(limit):
            yield msg

        channel.history = mock_history

        result = await fetch_messages_with_metadata(channel, limit=10)
        assert result.latest_message_link == "https://discord.com/channels/111/222/999"

    @pytest.mark.asyncio
    async def test_empty_channel_returns_none_link(self):
        channel = MagicMock()

        async def mock_history(limit):
            return
            yield

        channel.history = mock_history

        result = await fetch_messages_with_metadata(channel, limit=10)
        assert result.messages == []
        assert result.latest_message_link is None
