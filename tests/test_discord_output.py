from unittest.mock import MagicMock

import pytest

from src.output.discord import (
    fetch_messages_with_metadata,
    format_message,
    resolve_mentions,
)


class TestResolveMentions:
    def _make_user(self, user_id, display_name):
        user = MagicMock()
        user.id = user_id
        user.display_name = display_name
        return user

    def _make_role(self, role_id, name):
        role = MagicMock()
        role.id = role_id
        role.name = name
        return role

    def _make_channel(self, channel_id, name):
        ch = MagicMock()
        ch.id = channel_id
        ch.name = name
        return ch

    def test_resolves_user_mention(self):
        user = self._make_user(123, "Alice")
        result = resolve_mentions("hello <@123>", [user], [], [])
        assert result == "hello @Alice"

    def test_resolves_user_mention_with_exclamation(self):
        user = self._make_user(123, "Alice")
        result = resolve_mentions("hello <@!123>", [user], [], [])
        assert result == "hello @Alice"

    def test_resolves_role_mention(self):
        role = self._make_role(456, "Moderators")
        result = resolve_mentions("ping <@&456>", [], [role], [])
        assert result == "ping @Moderators"

    def test_resolves_channel_mention(self):
        channel = self._make_channel(789, "general")
        result = resolve_mentions("see <#789>", [], [], [channel])
        assert result == "see #general"

    def test_resolves_multiple_mention_types(self):
        user = self._make_user(1, "Bob")
        role = self._make_role(2, "Admin")
        channel = self._make_channel(3, "dev")
        result = resolve_mentions("<@1> asked <@&2> in <#3>", [user], [role], [channel])
        assert result == "@Bob asked @Admin in #dev"

    def test_no_mentions_returns_unchanged(self):
        result = resolve_mentions("just plain text", [], [], [])
        assert result == "just plain text"

    def test_unresolved_mention_left_as_is(self):
        result = resolve_mentions("hello <@999>", [], [], [])
        assert result == "hello <@999>"


class TestFormatMessage:
    def _make_msg(self, name="Alice", content="hello", embeds=None):
        msg = MagicMock()
        msg.author.display_name = name
        msg.content = content
        msg.mentions = []
        msg.role_mentions = []
        msg.channel_mentions = []
        msg.embeds = embeds or []
        return msg

    def _make_embed(self, title=None, description=None, fields=None):
        embed = MagicMock()
        embed.title = title
        embed.description = description
        embed.fields = fields or []
        return embed

    def _make_field(self, name, value):
        field = MagicMock()
        field.name = name
        field.value = value
        return field

    def test_plain_message_no_embeds(self):
        msg = self._make_msg("Alice", "hello")
        assert format_message(msg) == "Alice: hello"

    def test_message_with_embed_title_and_description(self):
        embed = self._make_embed(title="Issue Title", description="Some details")
        msg = self._make_msg("Bot", "check this out", embeds=[embed])
        result = format_message(msg)
        assert result == "Bot: check this out\n[Embed] Issue Title | Some details"

    def test_message_with_embed_fields(self):
        fields = [
            self._make_field("Status", "Open"),
            self._make_field("Priority", "High"),
        ]
        embed = self._make_embed(title="Ticket", fields=fields)
        msg = self._make_msg("Bot", "", embeds=[embed])
        result = format_message(msg)
        assert result == "Bot: \n[Embed] Ticket | Status: Open | Priority: High"

    def test_empty_embed_ignored(self):
        embed = self._make_embed()
        msg = self._make_msg("Bot", "text", embeds=[embed])
        assert format_message(msg) == "Bot: text"

    def test_multiple_embeds(self):
        embed1 = self._make_embed(title="First")
        embed2 = self._make_embed(description="Second desc")
        msg = self._make_msg("Bot", "msg", embeds=[embed1, embed2])
        result = format_message(msg)
        assert result == "Bot: msg\n[Embed] First\n[Embed] Second desc"

    def test_embed_with_only_description(self):
        embed = self._make_embed(description="just a description")
        msg = self._make_msg("Bot", "x", embeds=[embed])
        result = format_message(msg)
        assert result == "Bot: x\n[Embed] just a description"


class TestFetchMessagesWithMetadata:
    def _make_msg(self, name, content, msg_id=100, guild_id=1, channel_id=2):
        msg = MagicMock()
        msg.author.display_name = name
        msg.content = content
        msg.id = msg_id
        msg.guild.id = guild_id
        msg.channel.id = channel_id
        msg.embeds = []
        msg.mentions = []
        msg.role_mentions = []
        msg.channel_mentions = []
        return msg

    @pytest.mark.asyncio
    async def test_returns_messages_in_chronological_order(self):
        # channel.history() yields newest-first; result should be oldest-first
        newest = self._make_msg("Alice", "hello", msg_id=200)
        oldest = self._make_msg("Bob", "world", msg_id=100)
        channel = MagicMock()

        async def mock_history(limit, **kwargs):
            for m in [newest, oldest]:
                yield m

        channel.history = mock_history

        result = await fetch_messages_with_metadata(channel, limit=10)
        assert len(result.messages) == 2
        assert "Bob" in result.messages[0]
        assert "Alice" in result.messages[1]

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
