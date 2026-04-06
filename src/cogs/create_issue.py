import logging
import time

import discord
from discord import app_commands
from discord.errors import NotFound
from discord.ext import commands

from src.cogs.registry import register_handler
from src.cogs.response import DmResponseTarget, ResponseTarget
from src.cogs.ui import build_error_embed
from src.pipeline.create_issue import IssuePipeline
from src.utils.discord import fetch_messages_with_metadata

logger = logging.getLogger(__name__)


class CreateIssueCog(commands.Cog):
    def __init__(self, bot: commands.Bot, pipeline: IssuePipeline) -> None:
        self.bot = bot
        self.pipeline = pipeline
        
        register_handler(IssuePipeline.CMD_TYPE, pipeline)
        
        self.ctx_menu = app_commands.ContextMenu(
            name="Create Issue",
            callback=self.create_issue_context_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    # ------------------------------------------------------------------
    #  create-issue context menu entrypoint. See CreateIssueModal class below.
    # ------------------------------------------------------------------
    async def create_issue_context_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await interaction.response.send_modal(CreateIssueModal(message, cog=self))

    # ------------------------------------------------------------------
    #  /create-issue slash command entrypoint
    # ------------------------------------------------------------------
    @app_commands.command(
        name="create-issue",
        description="Generate a GitHub issue from recent channel messages",
    )
    @app_commands.describe(
        repo="GitHub repo (owner/repo)",
        focus="Focus or summary for the issue",
        n="Number of messages to fetch (default 20)",
    )
    async def create_issue_command(
        self,
        interaction: discord.Interaction,
        repo: str,
        focus: str,
        n: int = 20,
    ) -> None:
        await self._run(interaction, repo=repo, focus=focus, n=n)

    # ------------------------------------------------------------------
    #  Shared run logic for both entrypoints
    # ------------------------------------------------------------------
    async def _run(
        self,
        interaction: discord.Interaction,
        *,
        repo: str,
        focus: str,
        n: int,
        anchor: discord.Message | None = None,
        target: ResponseTarget | None = None,
    ) -> None:
        """Defer, resolve an anchor message, fetch context around it, and hand off to the pipeline."""
        t0 = time.monotonic()
        logger.info(
            "create-issue invoked: repo=%s focus=%r n=%d anchor=%s",
            repo,
            focus,
            n,
            "supplied" if anchor is not None else "latest",
        )

        try:
            await interaction.response.defer(ephemeral=True)
        except NotFound:
            elapsed = (time.monotonic() - t0) * 1000
            logger.warning("Interaction 404'd. Did it expire? (%.0fms)", elapsed)
            return

        try:
            if anchor is None:
                async for latest in interaction.channel.history(limit=1):
                    anchor = latest
                    break
                if anchor is None:
                    logger.error(
                        "No messages retrieved from channel %s", interaction.channel
                    )
                    await interaction.followup.send(
                        content="Internal error: no messages could be retrieved.",
                        ephemeral=True,
                    )
                    return

            fetch_result = await fetch_messages_with_metadata(
                anchor.channel, limit=n, anchor=anchor
            )
            logger.debug(
                "Fetched %d messages (%.0fms)",
                len(fetch_result.messages),
                (time.monotonic() - t0) * 1000,
            )

            if not fetch_result.messages:
                logger.error("No messages retrieved around anchor %s", anchor.id)
                await interaction.followup.send(
                    content="Internal error: no messages could be retrieved.",
                    ephemeral=True,
                )
                return

            await self.pipeline.run(
                interaction,
                repo=repo,
                focus=focus,
                messages=fetch_result.messages,
                latest_message_link=fetch_result.latest_message_link,
                ephemeral=True,
                target=target,
            )
            logger.info(
                "create-issue complete (%.0fms)", (time.monotonic() - t0) * 1000
            )
        except Exception as exc:
            logger.exception("create-issue failed")
            embed = build_error_embed(exc)
            await interaction.followup.send(embed=embed, ephemeral=True)

# ------------------------------------------------------------------
# Used just in the context menu flow
# ------------------------------------------------------------------
class CreateIssueModal(discord.ui.Modal, title="Create Issue"):
    repo = discord.ui.TextInput(
        label="Repository",
        placeholder="owner/repo",
        style=discord.TextStyle.short,
        required=True,
    )
    focus = discord.ui.TextInput(
        label="Focus",
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
        n = int(self.n.value or "20")
        await self.cog._run(
            interaction,
            repo=self.repo.value,
            focus=self.focus.value,
            n=n,
            anchor=self.target_message,
            target=DmResponseTarget(interaction.user, interaction.channel_id),
        )
