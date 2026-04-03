from unittest.mock import MagicMock

import pytest

from src.output.discord import fetch_messages_with_metadata


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

        async def mock_history(limit, **kwargs):
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

        async def mock_history(limit, **kwargs):
            yield msg

        channel.history = mock_history

        result = await fetch_messages_with_metadata(channel, limit=10)
        assert result.latest_message_link == "https://discord.com/channels/111/222/999"

    @pytest.mark.asyncio
    async def test_empty_channel_returns_none_link(self):
        channel = MagicMock()

        async def mock_history(limit, **kwargs):
            return
            yield

        channel.history = mock_history

        result = await fetch_messages_with_metadata(channel, limit=10)
        assert result.messages == []
        assert result.latest_message_link is None

    @pytest.mark.asyncio
    async def test_before_anchor_is_passed_to_history(self):
        msg = self._make_msg("Alice", "hi", msg_id=999)
        anchor = MagicMock()
        channel = MagicMock()
        received_kwargs = {}

        async def mock_history(limit, **kwargs):
            received_kwargs.update(kwargs)
            yield msg

        channel.history = mock_history

        await fetch_messages_with_metadata(channel, limit=5, before=anchor)
        assert received_kwargs.get("before") is anchor
