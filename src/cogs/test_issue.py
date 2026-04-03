import logging
import time

import discord
from discord import app_commands
from discord.errors import NotFound
from discord.ext import commands

from src.cogs.create_issue import run_pipeline
from src.input.file import read_messages
from src.transform.protocol import Transform

logger = logging.getLogger(__name__)


class DebugIssueCog(commands.Cog):
    def __init__(self, bot: commands.Bot, transform: Transform) -> None:
        self.bot = bot
        self.transform = transform

    @app_commands.command(
        name="test-issue",
        description="Generate a GitHub issue from a conversation file (testing utility)",
    )
    @app_commands.describe(
        repo="GitHub repo (owner/repo)",
        topic="Topic or summary for the issue",
        filepath="Path to conversation file",
        end_line="Line number to read up to (1-indexed, default 1)",
        n="Number of messages to read (default 20)",
    )
    async def test_issue_command(
        self,
        interaction: discord.Interaction,
        repo: str,
        topic: str,
        filepath: str,
        end_line: int = 1,
        n: int = 20,
    ) -> None:
        await self._do_test_issue(
            interaction,
            repo=repo,
            topic=topic,
            filepath=filepath,
            end_line=end_line,
            n=n,
        )

    async def _do_test_issue(
        self,
        interaction: discord.Interaction,
        repo: str,
        topic: str,
        filepath: str,
        end_line: int,
        n: int,
    ) -> None:
        t0 = time.monotonic()
        logger.info(
            "test-issue invoked: repo=%s topic=%r filepath=%s start=%d n=%d",
            repo,
            topic,
            filepath,
            end_line,
            n,
        )

        try:
            await interaction.response.defer(ephemeral=True)
        except NotFound:
            logger.warning("Interaction expired")
            return

        messages = read_messages(filepath, end_line=end_line, count=n)
        logger.debug("Read %d messages from %s", len(messages), filepath)

        if not messages:
            logger.error(
                "No messages read from %s (end_line=%d, n=%d)",
                filepath, end_line, n,
            )
            await interaction.followup.send(
                content="Internal error: no messages could be retrieved.",
                ephemeral=True,
            )
            return

        await run_pipeline(
            interaction,
            transform=self.transform,
            repo=repo,
            topic=topic,
            messages=messages,
            latest_message_link=None,
        )
        logger.info("test-issue complete (%.0fms)", (time.monotonic() - t0) * 1000)
