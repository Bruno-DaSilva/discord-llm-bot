import logging
import time

import discord
from discord import app_commands
from discord.errors import NotFound
from discord.ext import commands

from src.models import PipelineData
from src.output.discord import fetch_messages
from src.ui import CancelIssueButton, CreateIssueButton

logger = logging.getLogger(__name__)


class CreateIssueCog(commands.Cog):
    def __init__(self, bot: commands.Bot, transform, github_token: str):
        self.bot = bot
        self.transform = transform
        self.github_token = github_token

    @app_commands.command(
        name="create-issue",
        description="Generate a GitHub issue from recent channel messages",
    )
    @app_commands.describe(
        repo="GitHub repo (owner/repo)",
        topic="Topic or summary for the issue",
        n="Number of messages to fetch (default 20)",
    )
    async def create_issue_command(
        self,
        interaction: discord.Interaction,
        repo: str,
        topic: str,
        n: int = 20,
    ):
        await self._do_create_issue(interaction, repo=repo, topic=topic, n=n)

    async def _do_create_issue(
        self,
        interaction: discord.Interaction,
        repo: str,
        topic: str,
        n: int,
    ):
        t0 = time.monotonic()
        logger.info("create-issue invoked: repo=%s topic=%r n=%d", repo, topic, n)

        try:
            await interaction.response.defer(ephemeral=True)
        except NotFound:
            elapsed = (time.monotonic() - t0) * 1000
            logger.warning("Interaction 404'd. Did it expire? (%.0fms)", elapsed)
            return

        elapsed = (time.monotonic() - t0) * 1000
        logger.info("Deferred interaction (%.0fms)", elapsed)

        logger.debug("Fetching %d messages", n)
        messages = await fetch_messages(interaction.channel, limit=n)
        logger.debug(
            "Fetched %d messages (%.0fms)",
            len(messages),
            (time.monotonic() - t0) * 1000,
        )

        logger.debug("Messages: \n%r\n===", messages)

        if not messages:
            logger.error("No messages retrieved from channel %s", interaction.channel)
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
        logger.info("create-issue complete (%.0fms)", (time.monotonic() - t0) * 1000)


class IssuePreviewView(discord.ui.View):
    def __init__(self, owner: str, repo: str):
        super().__init__(timeout=None)
        self.add_item(CreateIssueButton(owner=owner, repo=repo))
        self.add_item(CancelIssueButton(owner=owner, repo=repo))
