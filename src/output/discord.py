from dataclasses import dataclass


@dataclass
class FetchResult:
    messages: list[str]
    latest_message_link: str | None


async def fetch_messages(channel, limit: int) -> list[str]:
    messages = []
    async for msg in channel.history(limit=limit):
        messages.append(f"{msg.author.display_name}: {msg.content}")
    return messages


async def fetch_messages_with_metadata(channel, limit: int) -> FetchResult:
    messages = []
    latest_message_link = None
    first = True
    async for msg in channel.history(limit=limit):
        messages.append(f"{msg.author.display_name}: {msg.content}")
        if first:
            latest_message_link = (
                f"https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}"
            )
            first = False
    return FetchResult(messages=messages, latest_message_link=latest_message_link)
