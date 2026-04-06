import discord

_FORBIDDEN_MSG = (
    "I couldn't DM you. Please enable DMs from server members and try again."
)


class ResponseTarget:
    """Default delivery: edit the loading message in place (ephemeral followup)."""

    async def send_preview(self, loading_msg, embed: discord.Embed, view) -> None:
        await loading_msg.edit(embed=embed, view=view)

    async def send_error(
        self, loading_msg, embed: discord.Embed, view=None
    ) -> None:
        if view is not None:
            await loading_msg.edit(embed=embed, view=view)
        else:
            await loading_msg.edit(embed=embed)

    @property
    def channel_id(self) -> int | None:
        return None


class DmResponseTarget(ResponseTarget):
    """Send previews and errors to the user's DMs; leave a stub in-channel."""

    def __init__(
        self,
        user: discord.User | discord.Member,
        origin_channel_id: int,
    ) -> None:
        self._user = user
        self._origin_channel_id = origin_channel_id

    async def send_preview(self, loading_msg, embed: discord.Embed, view) -> None:
        try:
            await self._user.send(embed=embed, view=view)
            await loading_msg.edit(
                content="Check your DMs for the issue preview.", embed=None
            )
        except discord.Forbidden:
            await loading_msg.edit(content=_FORBIDDEN_MSG, embed=None)

    async def send_error(
        self, loading_msg, embed: discord.Embed, view=None
    ) -> None:
        try:
            if view is not None:
                await self._user.send(embed=embed, view=view)
            else:
                await self._user.send(embed=embed)
            await loading_msg.edit(
                content="Check your DMs for details.", embed=None
            )
        except discord.Forbidden:
            await loading_msg.edit(content=_FORBIDDEN_MSG, embed=None)

    @property
    def channel_id(self) -> int | None:
        return self._origin_channel_id
