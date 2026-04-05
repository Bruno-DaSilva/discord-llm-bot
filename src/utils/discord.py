from dataclasses import dataclass

import discord


@dataclass
class FetchResult:
    messages: list[str]
    latest_message_link: str | None


def resolve_mentions(
    content: str,
    mentions: list,
    role_mentions: list,
    channel_mentions: list,
) -> str:
    """Replace raw Discord mention markup (<@id>, <@&id>, <#id>) with human-readable names."""
    for user in mentions:
        content = content.replace(f"<@{user.id}>", f"@{user.display_name}")
        content = content.replace(f"<@!{user.id}>", f"@{user.display_name}")
    for role in role_mentions:
        content = content.replace(f"<@&{role.id}>", f"@{role.name}")
    for channel in channel_mentions:
        content = content.replace(f"<#{channel.id}>", f"#{channel.name}")
    return content


def format_message(msg: discord.Message) -> str:
    """Format a Discord message as 'Author: content', appending any embed titles, descriptions, and fields."""
    resolved_content = resolve_mentions(
        msg.content, msg.mentions, msg.role_mentions, msg.channel_mentions
    )
    parts = [f"{msg.author.display_name}: {resolved_content}"]

    for embed in msg.embeds:
        embed_parts = []
        if embed.title:
            embed_parts.append(embed.title)
        if embed.description:
            embed_parts.append(embed.description)
        for field in embed.fields:
            embed_parts.append(f"{field.name}: {field.value}")
        if embed_parts:
            parts.append("[Embed] " + " | ".join(embed_parts))

    return "\n".join(parts)


def _message_link(msg: discord.Message) -> str | None:
    if msg.guild is None:
        return None
    return f"https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}"


async def fetch_messages_with_metadata(
    channel: discord.abc.Messageable,
    limit: int,
    anchor: discord.Message | None = None,
) -> FetchResult:
    """Fetch up to *limit* messages from the channel, return them in chronological order with a link to the latest.

    When *anchor* is provided, fetch *limit - 1* messages strictly before it and
    append the formatted anchor at the end; the returned link points to the anchor.
    """
    if anchor is not None:
        messages = [
            format_message(m)
            async for m in channel.history(limit=limit - 1, before=anchor)
        ]
        messages.reverse()
        messages.append(format_message(anchor))
        return FetchResult(messages=messages, latest_message_link=_message_link(anchor))

    messages = []
    latest_message_link = None
    first = True
    async for msg in channel.history(limit=limit):
        messages.append(format_message(msg))
        if first:
            latest_message_link = _message_link(msg)
            first = False
    messages.reverse()
    return FetchResult(messages=messages, latest_message_link=latest_message_link)
