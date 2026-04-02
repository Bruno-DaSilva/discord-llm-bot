import logging
import time

import discord
from discord import app_commands
from discord.errors import NotFound
from discord.ext import commands

from src.cogs.create_issue import IssuePreviewView
from src.input.file import read_messages
from src.models import PipelineData

logger = logging.getLogger(__name__)


class DebugIssueCog(commands.Cog):
    def __init__(self, bot: commands.Bot, transform, github_token: str):
        self.bot = bot
        self.transform = transform
        self.github_token = github_token

    @app_commands.command(
        name="test-issue",
        description="Generate a GitHub issue from a conversation file (testing utility)",
    )
    @app_commands.describe(
        repo="GitHub repo (owner/repo)",
        topic="Topic or summary for the issue",
        filepath="Path to conversation file",
        start_line="Line number to start reading from (1-indexed, default 1)",
        n="Number of messages to read (default 20)",
    )
    async def test_issue_command(
        self,
        interaction: discord.Interaction,
        repo: str,
        topic: str,
        filepath: str,
        start_line: int = 1,
        n: int = 20,
    ):
        await self._do_test_issue(
            interaction,
            repo=repo,
            topic=topic,
            filepath=filepath,
            start_line=start_line,
            n=n,
        )

    async def _do_test_issue(
        self,
        interaction: discord.Interaction,
        repo: str,
        topic: str,
        filepath: str,
        start_line: int,
        n: int,
    ):
        t0 = time.monotonic()
        logger.info(
            "test-issue invoked: repo=%s topic=%r filepath=%s start=%d n=%d",
            repo,
            topic,
            filepath,
            start_line,
            n,
        )

        try:
            await interaction.response.defer(ephemeral=True)
        except NotFound:
            logger.warning("Interaction expired")
            return

        messages = read_messages(filepath, start_line=start_line, count=n)
        logger.debug("Read %d messages from %s", len(messages), filepath)

        if not messages:
            logger.error(
                "No messages read from %s (start_line=%d, n=%d)",
                filepath, start_line, n,
            )
            await interaction.followup.send(
                content="Internal error: no messages could be retrieved.",
                ephemeral=True,
            )
            return

        data = PipelineData(
            context={"messages": messages},
            input=topic,
        )

        result = await self.transform.run(data)

        owner, repo_name = repo.split("/", 1)
        view = IssuePreviewView(owner=owner, repo=repo_name)

        embed = discord.Embed(description=result.input)
        await interaction.followup.send(embed=embed, view=view)
        logger.info("test-issue complete (%.0fms)", (time.monotonic() - t0) * 1000)
