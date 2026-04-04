from __future__ import annotations

import logging
from typing import Protocol

import discord

from src.models import CachedCommandData, CachedOutputData

logger = logging.getLogger(__name__)


class CommandHandler(Protocol):
    async def on_confirm(
        self, interaction: discord.Interaction, cached: CachedCommandData
    ) -> None: ...

    async def on_retry(
        self, interaction: discord.Interaction, cached: CachedCommandData
    ) -> None: ...

    async def on_output_retry(
        self, interaction: discord.Interaction, cached: CachedOutputData
    ) -> None: ...


_handlers: dict[str, CommandHandler] = {}


def register_handler(cmd_type: str, handler: CommandHandler) -> None:
    _handlers[cmd_type] = handler
    logger.info("Registered command handler: %s", cmd_type)


def get_handler(cmd_type: str) -> CommandHandler | None:
    return _handlers.get(cmd_type)
