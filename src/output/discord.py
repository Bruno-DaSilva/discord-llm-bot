async def fetch_messages(channel, limit: int) -> list[str]:
    messages = []
    async for msg in channel.history(limit=limit):
        messages.append(f"{msg.author.display_name}: {msg.content}")
    return messages
