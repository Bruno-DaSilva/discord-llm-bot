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
    for user in mentions:
        content = content.replace(f"<@{user.id}>", f"@{user.display_name}")
        content = content.replace(f"<@!{user.id}>", f"@{user.display_name}")
    for role in role_mentions:
        content = content.replace(f"<@&{role.id}>", f"@{role.name}")
    for channel in channel_mentions:
        content = content.replace(f"<#{channel.id}>", f"#{channel.name}")
    return content


def format_message(msg: discord.Message) -> str:
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


async def fetch_messages_with_metadata(
    channel: discord.abc.Messageable, limit: int, before: discord.Message | None = None
) -> FetchResult:
    messages = []
    latest_message_link = None
    first = True
    kwargs = {"limit": limit}
    if before is not None:
        kwargs["before"] = before
    async for msg in channel.history(**kwargs):
        messages.append(format_message(msg))
        if first:
            latest_message_link = (
                f"https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}"
            )
            first = False
    messages.reverse()
    return FetchResult(messages=messages, latest_message_link=latest_message_link)
