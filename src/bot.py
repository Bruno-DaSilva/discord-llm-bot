import logging
import os

import discord
from discord.ext import commands

from src.cogs.create_issue import CreateIssueCog
from src.cogs.test_issue import DebugIssueCog
from src.transform.gemini import IssueGeneratorTransform
from src.ui import CancelIssueButton, CreateIssueButton, DeleteView

logger = logging.getLogger(__name__)


class IssueBot(commands.Bot):
    def __init__(self, gemini_api_key: str, github_token: str, **kwargs):
        self.gemini_api_key = gemini_api_key
        self.github_token = github_token
        super().__init__(**kwargs)

    async def setup_hook(self):
        self.add_view(DeleteView())
        self.add_dynamic_items(CreateIssueButton, CancelIssueButton)

        from google import genai

        gemini_client = genai.Client(api_key=self.gemini_api_key)
        transform = IssueGeneratorTransform(client=gemini_client)

        cog = CreateIssueCog(
            self,
            transform=transform,
            github_token=self.github_token,
        )
        await self.add_cog(cog)
        logger.info("CreateIssueCog loaded")

        debug_cog = DebugIssueCog(
            self,
            transform=transform,
            github_token=self.github_token,
        )
        await self.add_cog(debug_cog)
        logger.info("DebugIssueCog loaded")

        logger.info("Syncing command tree")
        await self.tree.sync()
        logger.info("Command tree synced")


def create_bot(gemini_api_key: str, github_token: str) -> IssueBot:
    intents = discord.Intents.default()
    intents.message_content = True

    return IssueBot(
        gemini_api_key=gemini_api_key,
        github_token=github_token,
        command_prefix="!",
        intents=intents,
    )


if __name__ == "__main__":
    from src.logging_config import setup_logging

    setup_logging()

    bot = create_bot(
        gemini_api_key=os.environ["GEMINI_API_KEY"],
        github_token=os.environ["GITHUB_TOKEN"],
    )
    bot.run(os.environ["DISCORD_BOT_TOKEN"])
