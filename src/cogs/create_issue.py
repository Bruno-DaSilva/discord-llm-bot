import logging
import time

import discord
from discord import app_commands
from discord.errors import NotFound
from discord.ext import commands

from src.models import CachedIssueData, IssueMetadata, PipelineData
from src.output.discord import fetch_messages_with_metadata
from src.ui import (
    CancelIssueButton,
    CreateIssueButton,
    ErrorView,
    RetryIssueButton,
    build_error_embed,
    cache_pipeline_data,
)

logger = logging.getLogger(__name__)


class CreateIssueCog(commands.Cog):
    def __init__(self, bot: commands.Bot, transform):
        self.bot = bot
        self.transform = transform

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
        fetch_result = await fetch_messages_with_metadata(interaction.channel, limit=n)
        logger.debug(
            "Fetched %d messages (%.0fms)",
            len(fetch_result.messages),
            (time.monotonic() - t0) * 1000,
        )

        logger.debug("Messages: \n%r\n===", fetch_result.messages)

        if not fetch_result.messages:
            logger.error("No messages retrieved from channel %s", interaction.channel)
            await interaction.followup.send(
                content="Internal error: no messages could be retrieved.",
                ephemeral=True,
            )
            return

        data = PipelineData(
            context={"messages": fetch_result.messages},
            input=topic,
        )
        metadata = IssueMetadata(
            author_username=interaction.user.display_name,
            latest_message_link=fetch_result.latest_message_link,
        )

        retry_key = cache_pipeline_data(CachedIssueData(pipeline_data=data, metadata=metadata))
        owner, repo_name = repo.split("/", 1)

        try:
            result = await self.transform.run(data)
        except Exception as exc:
            logger.exception("Transform failed in create-issue")
            embed = build_error_embed(exc)
            view = ErrorView(owner=owner, repo=repo_name, retry_key=retry_key)
            await interaction.followup.send(embed=embed, view=view)
            return

        view = IssuePreviewView(owner=owner, repo=repo_name, cache_key=retry_key)

        embed = discord.Embed(description=result.input)
        await interaction.followup.send(embed=embed, view=view)
        logger.info("create-issue complete (%.0fms)", (time.monotonic() - t0) * 1000)


class IssuePreviewView(discord.ui.View):
    def __init__(
        self,
        owner: str,
        repo: str,
        cache_key: str | None = None,
        loading: bool = False,
    ):
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
            self.add_item(CreateIssueButton(owner=owner, repo=repo, cache_key=cache_key or ""))
            self.add_item(CancelIssueButton(owner=owner, repo=repo))
            if cache_key is not None:
                self.add_item(RetryIssueButton(owner=owner, repo=repo, retry_key=cache_key))
