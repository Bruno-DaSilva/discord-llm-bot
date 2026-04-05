import logging
import time

import discord
from discord import app_commands
from discord.errors import NotFound
from discord.ext import commands

from src.cogs.registry import register_handler
from src.models import CachedCommandData, CachedOutputData
from src.utils.discord import fetch_messages_with_metadata, resolve_mentions
from src.output.github import RepoNotInstalled
from src.pipeline.create_issue import IssuePipeline
from src.cogs.ui import (
    DeleteView,
    ErrorView,
    OutputErrorView,
    PreviewView,
    build_error_embed,
    cache_pipeline_data,
)

logger = logging.getLogger(__name__)


class CreateIssueHandler:
    """Implements CommandHandler for issue creation."""

    def __init__(self, pipeline: IssuePipeline) -> None:
        self.pipeline = pipeline

    async def on_confirm(
        self, interaction: discord.Interaction, cached: CachedCommandData
    ) -> None:
        """Extract title/body from the preview embed, append a footer, and create the GitHub issue."""
        issue_body = interaction.message.embeds[0].description
        title, body = self.pipeline.parse_preview(issue_body)

        body = self.pipeline.build_issue_body(
            body,
            cached.extra["author_username"],
            cached.extra.get("latest_message_link"),
            model=cached.extra.get("model"),
        )

        owner = cached.extra["owner"]
        repo = cached.extra["repo"]

        try:
            url = await self.pipeline.create_issue(owner, repo, title, body)
        except Exception as exc:
            logger.exception("Failed to create issue on GitHub")
            github_data = CachedOutputData(
                cmd_type=IssuePipeline.CMD_TYPE,
                payload={
                    "title": title,
                    "body": body,
                    "owner": owner,
                    "repo": repo,
                },
            )
            new_key = cache_pipeline_data(github_data)
            embed = build_error_embed(exc)
            view = OutputErrorView(
                cmd_type=IssuePipeline.CMD_TYPE, retry_key=new_key
            )
            await interaction.response.edit_message(embed=embed, view=view)
            return

        await interaction.response.edit_message(
            content=f"Issue created: {url}", view=None
        )
        await interaction.channel.send(
            content=f"Issue created: {url}", view=DeleteView()
        )

    async def on_retry(
        self, interaction: discord.Interaction, cached: CachedCommandData
    ) -> None:
        """Show a loading state, re-run the transform, and display a new preview or error."""
        loading_view = PreviewView(cmd_type=IssuePipeline.CMD_TYPE, loading=True)
        await interaction.response.edit_message(view=loading_view)

        new_key = cache_pipeline_data(cached)

        try:
            result = await self.pipeline.generate(cached.pipeline_data)
        except Exception as exc:
            logger.exception("Transform failed in retry")
            embed = build_error_embed(exc)
            view = ErrorView(cmd_type=IssuePipeline.CMD_TYPE, retry_key=new_key)
            await interaction.edit_original_response(embed=embed, view=view)
            return

        view = PreviewView(
            cmd_type=IssuePipeline.CMD_TYPE,
            cache_key=new_key,
            confirm_label="Create",
        )
        embed = discord.Embed(description=result.input)
        await interaction.edit_original_response(embed=embed, view=view)

    async def on_output_retry(
        self, interaction: discord.Interaction, cached: CachedOutputData
    ) -> None:
        """Retry a previously failed GitHub issue creation using the cached payload."""
        title = cached.payload["title"]
        body = cached.payload["body"]
        owner = cached.payload["owner"]
        repo = cached.payload["repo"]

        try:
            url = await self.pipeline.create_issue(owner, repo, title, body)
        except Exception as exc:
            logger.exception("GitHub retry failed")
            new_data = CachedOutputData(
                cmd_type=IssuePipeline.CMD_TYPE,
                payload={
                    "title": title,
                    "body": body,
                    "owner": owner,
                    "repo": repo,
                },
            )
            new_key = cache_pipeline_data(new_data)
            embed = build_error_embed(exc)
            view = OutputErrorView(
                cmd_type=IssuePipeline.CMD_TYPE, retry_key=new_key
            )
            await interaction.response.edit_message(embed=embed, view=view)
            return

        await interaction.response.edit_message(
            content=f"Issue created: {url}", embed=None, view=None
        )
        await interaction.channel.send(
            content=f"Issue created: {url}", view=DeleteView()
        )


class CreateIssueCog(commands.Cog):
    def __init__(self, bot: commands.Bot, pipeline: IssuePipeline) -> None:
        self.bot = bot
        self.pipeline = pipeline
        self.handler = CreateIssueHandler(pipeline)
        register_handler(IssuePipeline.CMD_TYPE, self.handler)
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
        """Defer the interaction, fetch channel messages, and run the issue-creation pipeline."""
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

        try:
            logger.debug("Fetching %d messages", n)
            fetch_result = await fetch_messages_with_metadata(
                interaction.channel, limit=n
            )
            logger.debug(
                "Fetched %d messages (%.0fms)",
                len(fetch_result.messages),
                (time.monotonic() - t0) * 1000,
            )

            logger.debug("Messages: \n%r\n===", fetch_result.messages)

            if not fetch_result.messages:
                logger.error(
                    "No messages retrieved from channel %s", interaction.channel
                )
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
            logger.info(
                "create-issue complete (%.0fms)", (time.monotonic() - t0) * 1000
            )
        except Exception as exc:
            logger.exception("create-issue failed")
            embed = build_error_embed(exc)
            await interaction.followup.send(embed=embed, ephemeral=True)

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
            pipeline=self.pipeline,
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

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        embed = build_error_embed(error)
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Fetch messages anchored before the target, prepend the target, and run the pipeline."""
        t0 = time.monotonic()
        await interaction.response.defer(ephemeral=True)

        n = int(self.n.value or "20")
        logger.info(
            "create-issue modal submitted: repo=%s topic=%r n=%d",
            self.repo.value,
            self.topic.value,
            n,
        )

        try:
            resolved_content = resolve_mentions(
                self.target_message.content,
                self.target_message.mentions,
                self.target_message.role_mentions,
                self.target_message.channel_mentions,
            )
            target_formatted = (
                f"{self.target_message.author.display_name}: {resolved_content}"
            )

            logger.debug("Fetching %d messages before target", n - 1)
            fetch_result = await fetch_messages_with_metadata(
                self.target_message.channel, limit=n - 1, before=self.target_message
            )
            messages = [target_formatted] + fetch_result.messages
            logger.debug(
                "Fetched %d messages (%.0fms)",
                len(messages),
                (time.monotonic() - t0) * 1000,
            )
            logger.debug("Messages: \n%r\n===", messages)

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
            logger.info(
                "create-issue modal complete (%.0fms)",
                (time.monotonic() - t0) * 1000,
            )
        except Exception as exc:
            logger.exception("create-issue modal failed")
            embed = build_error_embed(exc)
            await interaction.followup.send(embed=embed, ephemeral=True)

async def run_pipeline(
    interaction: discord.Interaction,
    *,
    pipeline: IssuePipeline,
    repo: str,
    topic: str,
    messages: list[str],
    latest_message_link: str | None,
    ephemeral: bool = False,
) -> None:
    """Check repo installation, run the LLM transform, and display a preview with confirm/retry/cancel buttons."""
    data = pipeline.build_pipeline_data(topic, messages)

    owner, repo_name = repo.split("/", 1)

    loading_embed = discord.Embed(
        description="Generating issue\N{HORIZONTAL ELLIPSIS}",
        color=discord.Color.blurple(),
    )
    loading_msg = await interaction.followup.send(
        embed=loading_embed, ephemeral=ephemeral, wait=True
    )

    try:
        await pipeline.check_repo(owner, repo_name)
    except RepoNotInstalled:
        embed = discord.Embed(
            title="Repository not available",
            description=(
                f"The GitHub App is not installed on **{owner}/{repo_name}**.\n\n"
                "Ask the repository owner to install the app, then try again."
            ),
            color=discord.Color.red(),
        )
        await loading_msg.edit(embed=embed)
        return

    cached = pipeline.build_cached_data(
        data,
        author_username=interaction.user.display_name,
        latest_message_link=latest_message_link,
        owner=owner,
        repo=repo_name,
    )
    retry_key = cache_pipeline_data(cached)

    try:
        result = await pipeline.generate(data)
    except Exception as exc:
        logger.exception("Transform failed")
        embed = build_error_embed(exc)
        view = ErrorView(cmd_type=IssuePipeline.CMD_TYPE, retry_key=retry_key)
        await loading_msg.edit(embed=embed, view=view)
        return

    view = PreviewView(
        cmd_type=IssuePipeline.CMD_TYPE,
        cache_key=retry_key,
        confirm_label="Create",
    )

    embed = discord.Embed(description=result.input)
    await loading_msg.edit(embed=embed, view=view)
