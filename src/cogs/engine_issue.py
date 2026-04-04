import logging
import time

import discord
from discord import app_commands
from discord.errors import NotFound
from discord.ext import commands

from src.cogs.create_issue import run_pipeline
from src.output.discord import fetch_messages_with_metadata, resolve_mentions
from src.transform.protocol import Transform
from src.ui import build_error_embed

logger = logging.getLogger(__name__)

REPO = "beyond-all-reason/recoilengine"


class EngineIssueCog(commands.Cog):
    def __init__(self, bot: commands.Bot, transform: Transform) -> None:
        self.bot = bot
        self.transform = transform
        self.ctx_menu = app_commands.ContextMenu(
            name="Engine Issue",
            callback=self.engine_issue_context_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def engine_issue_context_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await interaction.response.send_modal(EngineIssueModal(message, cog=self))

    @app_commands.command(
        name="engine-issue",
        description="Generate a GitHub issue for RecoilEngine from recent channel messages",
    )
    @app_commands.describe(
        topic="Topic or summary for the issue",
        n="Number of messages to fetch (default 20)",
    )
    async def engine_issue_command(
        self,
        interaction: discord.Interaction,
        topic: str,
        n: int = 20,
    ) -> None:
        await self._do_engine_issue(interaction, topic=topic, n=n)

    async def _do_engine_issue(
        self,
        interaction: discord.Interaction,
        topic: str,
        n: int = 20,
    ) -> None:
        t0 = time.monotonic()
        logger.info("engine-issue invoked: topic=%r n=%d", topic, n)

        try:
            await interaction.response.defer(ephemeral=True)
        except NotFound:
            elapsed = (time.monotonic() - t0) * 1000
            logger.warning("Interaction 404'd. Did it expire? (%.0fms)", elapsed)
            return

        try:
            fetch_result = await fetch_messages_with_metadata(interaction.channel, limit=n)

            if not fetch_result.messages:
                logger.error("No messages retrieved from channel %s", interaction.channel)
                await interaction.followup.send(
                    content="Internal error: no messages could be retrieved.",
                    ephemeral=True,
                )
                return

            await run_pipeline(
                interaction,
                transform=self.transform,
                repo=REPO,
                topic=topic,
                messages=fetch_result.messages,
                latest_message_link=fetch_result.latest_message_link,
                ephemeral=True,
            )
            logger.info("engine-issue complete (%.0fms)", (time.monotonic() - t0) * 1000)
        except Exception as exc:
            logger.exception("engine-issue failed")
            embed = build_error_embed(exc)
            await interaction.followup.send(embed=embed, ephemeral=True)


class EngineIssueModal(discord.ui.Modal, title="Engine Issue"):
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

    def __init__(self, message: discord.Message, *, cog: "EngineIssueCog") -> None:
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
        resolved_content = resolve_mentions(
            self.target_message.content,
            self.target_message.mentions,
            self.target_message.role_mentions,
            self.target_message.channel_mentions,
        )
        target_formatted = f"{self.target_message.author.display_name}: {resolved_content}"

        fetch_result = await fetch_messages_with_metadata(
            self.target_message.channel, limit=n - 1, before=self.target_message
        )
        messages = [target_formatted] + fetch_result.messages

        guild = self.target_message.guild
        if guild is not None:
            link = f"https://discord.com/channels/{guild.id}/{self.target_message.channel.id}/{self.target_message.id}"
        else:
            link = None

        await run_pipeline(
            interaction,
            transform=self.cog.transform,
            repo=REPO,
            topic=self.topic.value,
            messages=messages,
            latest_message_link=link,
            ephemeral=True,
        )
