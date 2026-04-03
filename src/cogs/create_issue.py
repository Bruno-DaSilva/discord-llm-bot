import logging
import time

import discord
from discord import app_commands
from discord.errors import NotFound
from discord.ext import commands

from src.models import CachedIssueData, IssueMetadata, PipelineData
from src.output.discord import fetch_messages_with_metadata
from src.transform.protocol import Transform
from src.ui import (
    CancelIssueButton,
    CreateIssueButton,
    ErrorView,
    RetryIssueButton,
    build_error_embed,
    cache_pipeline_data,
)

logger = logging.getLogger(__name__)


async def run_pipeline(
    interaction: discord.Interaction,
    *,
    transform: Transform,
    repo: str,
    topic: str,
    messages: list[str],
    latest_message_link: str | None,
    ephemeral: bool = False,
) -> None:
    data = PipelineData(
        context={"messages": messages},
        input=topic,
    )
    metadata = IssueMetadata(
        author_username=interaction.user.display_name,
        latest_message_link=latest_message_link,
    )

    retry_key = cache_pipeline_data(CachedIssueData(pipeline_data=data, metadata=metadata))
    owner, repo_name = repo.split("/", 1)

    try:
        result = await transform.run(data)
    except Exception as exc:
        logger.exception("Transform failed")
        embed = build_error_embed(exc)
        view = ErrorView(owner=owner, repo=repo_name, retry_key=retry_key)
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
        return

    view = IssuePreviewView(owner=owner, repo=repo_name, cache_key=retry_key)

    embed = discord.Embed(description=result.input)
    await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)


class CreateIssueCog(commands.Cog):
    def __init__(self, bot: commands.Bot, transform: Transform) -> None:
        self.bot = bot
        self.transform = transform
        self.ctx_menu = app_commands.ContextMenu(
            name="Create Issue",
            callback=self.create_issue_context_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def create_issue_context_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await interaction.response.send_modal(CreateIssueModal(message, cog=self))

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
    ) -> None:
        await self._do_create_issue(interaction, repo=repo, topic=topic, n=n)

    async def _do_create_issue(
        self,
        interaction: discord.Interaction,
        repo: str,
        topic: str,
        n: int,
    ) -> None:
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

        await self._run_pipeline(
            interaction,
            repo=repo,
            topic=topic,
            messages=fetch_result.messages,
            latest_message_link=fetch_result.latest_message_link,
        )
        logger.info("create-issue complete (%.0fms)", (time.monotonic() - t0) * 1000)

    async def _run_pipeline(
        self,
        interaction: discord.Interaction,
        *,
        repo: str,
        topic: str,
        messages: list[str],
        latest_message_link: str | None,
    ) -> None:
        await run_pipeline(
            interaction,
            transform=self.transform,
            repo=repo,
            topic=topic,
            messages=messages,
            latest_message_link=latest_message_link,
            ephemeral=True,
        )


class CreateIssueModal(discord.ui.Modal, title="Create Issue"):
    repo = discord.ui.TextInput(
        label="Repository",
        placeholder="owner/repo",
        style=discord.TextStyle.short,
        required=True,
    )
    topic = discord.ui.TextInput(
        label="Topic",
        placeholder="Brief summary of the issue",
        style=discord.TextStyle.short,
        required=True,
    )
    n = discord.ui.TextInput(
        label="Number of messages",
        placeholder="20",
        default="20",
        style=discord.TextStyle.short,
        required=False,
    )

    def __init__(self, message: discord.Message, *, cog: "CreateIssueCog") -> None:
        super().__init__()
        self.target_message = message
        self.cog = cog

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        embed = build_error_embed(error)
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        n = int(self.n.value or "20")
        target_formatted = f"{self.target_message.author.display_name}: {self.target_message.content}"

        fetch_result = await fetch_messages_with_metadata(
            self.target_message.channel, limit=n - 1, before=self.target_message
        )
        messages = [target_formatted] + fetch_result.messages

        guild = self.target_message.guild
        if guild is not None:
            link = f"https://discord.com/channels/{guild.id}/{self.target_message.channel.id}/{self.target_message.id}"
        else:
            link = None

        await self.cog._run_pipeline(
            interaction,
            repo=self.repo.value,
            topic=self.topic.value,
            messages=messages,
            latest_message_link=link,
        )


class IssuePreviewView(discord.ui.View):
    def __init__(
        self,
        owner: str,
        repo: str,
        cache_key: str | None = None,
        loading: bool = False,
    ) -> None:
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
