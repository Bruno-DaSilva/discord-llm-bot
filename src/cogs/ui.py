import logging
import re
import time
from typing import Self

import discord

from src.models import CachedCommandData, CachedOutputData
from src.utils.tracing import traced_callback

logger = logging.getLogger(__name__)

_CACHE_TTL = 86400  # 24 hours
_retry_cache: dict[str, tuple[float, CachedCommandData | CachedOutputData]] = {}


def _evict_expired() -> None:
    now = time.monotonic()
    expired = [k for k, (ts, _) in _retry_cache.items() if now - ts > _CACHE_TTL]
    for k in expired:
        del _retry_cache[k]


def cache_pipeline_data(data: CachedCommandData | CachedOutputData) -> str:
    """Evict stale entries, store data under the current trace ID, and return the key."""
    from src.utils.tracing import generate_cache_key, get_trace_headers

    _evict_expired()
    key = generate_cache_key()
    data.trace_headers = get_trace_headers() or None
    _retry_cache[key] = (time.monotonic(), data)
    return key


def get_cached_pipeline_data(
    key: str,
) -> CachedCommandData | CachedOutputData | None:
    """Return cached data for key, or None if missing. Deletes the entry if expired."""
    entry = _retry_cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _retry_cache[key]
        return None
    return data


def build_error_embed(error: Exception) -> discord.Embed:
    error_type = type(error).__name__
    return discord.Embed(
        title="Something went wrong",
        description=f"**{error_type}**: {error}\n\nYou can retry or cancel.",
        color=discord.Color.red(),
    )


class DeleteButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            style=discord.ButtonStyle.grey,
            emoji="\N{WASTEBASKET}",
            custom_id="delete_issue_msg",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.message.delete()


class DeleteView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(DeleteButton())


# ---------------------------------------------------------------------------
# Generic command buttons — dispatch via cmd_type to registered handlers
# ---------------------------------------------------------------------------


class ConfirmButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"confirm:(?P<cmd_type>[^:]+):(?P<key>.+)",
):
    def __init__(
        self, cmd_type: str, cache_key: str, *, label: str = "Confirm"
    ) -> None:
        self.cmd_type = cmd_type
        self.cache_key = cache_key
        super().__init__(
            discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.green,
                custom_id=f"confirm:{cmd_type}:{cache_key}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
    ) -> Self:
        return cls(cmd_type=match["cmd_type"], cache_key=match["key"])

    @traced_callback
    async def callback(self, interaction: discord.Interaction) -> None:
        """Look up cached data and dispatch to the registered handler's on_confirm."""
        logger.info("Confirm button pressed: cmd_type=%s", self.cmd_type)

        cached = get_cached_pipeline_data(self.cache_key)
        if cached is None:
            await interaction.response.send_message(
                "Session expired. Please run the command again.",
                ephemeral=True,
            )
            return

        from src.cogs.registry import get_handler

        handler = get_handler(self.cmd_type)
        if handler is None:
            await interaction.response.send_message(
                "Unknown command type.",
                ephemeral=True,
            )
            return

        await handler.on_confirm(interaction, cached)


class RetryButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"retry:(?P<cmd_type>[^:]+):(?P<key>.+)",
):
    def __init__(self, cmd_type: str, retry_key: str) -> None:
        self.cmd_type = cmd_type
        self.retry_key = retry_key
        super().__init__(
            discord.ui.Button(
                label="Retry",
                style=discord.ButtonStyle.blurple,
                custom_id=f"retry:{cmd_type}:{retry_key}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
    ) -> Self:
        return cls(cmd_type=match["cmd_type"], retry_key=match["key"])

    @traced_callback
    async def callback(self, interaction: discord.Interaction) -> None:
        """Look up cached CachedCommandData and dispatch to the registered handler's on_retry."""
        data = get_cached_pipeline_data(self.retry_key)
        if data is None or not isinstance(data, CachedCommandData):
            await interaction.response.send_message(
                "Session expired. Please run the command again.",
                ephemeral=True,
            )
            return

        from src.cogs.registry import get_handler

        handler = get_handler(self.cmd_type)
        if handler is None:
            await interaction.response.send_message(
                "Unknown command type.",
                ephemeral=True,
            )
            return

        await handler.on_retry(interaction, data)


class CancelButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"cancel:(?P<cmd_type>[^:]+):(?P<key>.+)",
):
    def __init__(self, cmd_type: str, cache_key: str) -> None:
        self.cmd_type = cmd_type
        self.cache_key = cache_key
        super().__init__(
            discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.red,
                custom_id=f"cancel:{cmd_type}:{cache_key}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
    ) -> Self:
        return cls(cmd_type=match["cmd_type"], cache_key=match["key"])

    async def callback(self, interaction: discord.Interaction) -> None:
        logger.info("Cancel button pressed")
        await interaction.response.edit_message(
            content="Cancelled.", embed=None, view=None
        )


class OutputRetryButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"output_retry:(?P<cmd_type>[^:]+):(?P<key>.+)",
):
    def __init__(self, cmd_type: str, retry_key: str) -> None:
        self.cmd_type = cmd_type
        self.retry_key = retry_key
        super().__init__(
            discord.ui.Button(
                label="Retry",
                style=discord.ButtonStyle.blurple,
                custom_id=f"output_retry:{cmd_type}:{retry_key}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
    ) -> Self:
        return cls(cmd_type=match["cmd_type"], retry_key=match["key"])

    @traced_callback
    async def callback(self, interaction: discord.Interaction) -> None:
        """Look up cached CachedOutputData and dispatch to the registered handler's on_output_retry."""
        cached = get_cached_pipeline_data(self.retry_key)
        if not isinstance(cached, CachedOutputData):
            await interaction.response.send_message(
                "Session expired. Please run the command again.",
                ephemeral=True,
            )
            return

        from src.cogs.registry import get_handler

        handler = get_handler(self.cmd_type)
        if handler is None:
            await interaction.response.send_message(
                "Unknown command type.",
                ephemeral=True,
            )
            return

        await handler.on_output_retry(interaction, cached)


# ---------------------------------------------------------------------------
# Generic views
# ---------------------------------------------------------------------------


class PreviewView(discord.ui.View):
    def __init__(
        self,
        cmd_type: str,
        cache_key: str | None = None,
        *,
        confirm_label: str = "Confirm",
        loading: bool = False,
    ) -> None:
        """Build a preview view. If loading, shows a single disabled button; otherwise adds confirm/cancel/retry."""
        super().__init__(timeout=None)
        if loading:
            self.add_item(
                discord.ui.Button(
                    label="Regenerating\N{HORIZONTAL ELLIPSIS}",
                    style=discord.ButtonStyle.blurple,
                    disabled=True,
                    custom_id="retry_loading",
                )
            )
        else:
            self.add_item(
                ConfirmButton(
                    cmd_type, cache_key or "", label=confirm_label
                )
            )
            self.add_item(CancelButton(cmd_type, cache_key or ""))
            if cache_key is not None:
                self.add_item(RetryButton(cmd_type, retry_key=cache_key))


class ErrorView(discord.ui.View):
    def __init__(self, cmd_type: str, retry_key: str) -> None:
        super().__init__(timeout=None)
        self.add_item(RetryButton(cmd_type, retry_key=retry_key))
        self.add_item(CancelButton(cmd_type, cache_key=retry_key))


class OutputErrorView(discord.ui.View):
    def __init__(self, cmd_type: str, retry_key: str) -> None:
        super().__init__(timeout=None)
        self.add_item(OutputRetryButton(cmd_type, retry_key=retry_key))
        self.add_item(CancelButton(cmd_type, cache_key=retry_key))
