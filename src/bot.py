import logging
import os
from pathlib import Path
from typing import Any

import discord
import httpx
from discord.ext import commands

from src.cogs.create_issue import CreateIssueCog
from src.cogs.test_issue import DebugIssueCog
from src.output.github_auth import GitHubAppAuth
from src.transform.gemini import IssueGeneratorTransform
from src.ui import CancelIssueButton, CreateIssueButton, DeleteView, RetryIssueButton

logger = logging.getLogger(__name__)


class IssueBot(commands.Bot):
    def __init__(
        self,
        gemini_api_key: str,
        github_app_id: str,
        github_private_key_path: str,
        github_installation_id: str,
        **kwargs: Any,
    ) -> None:
        self.gemini_api_key = gemini_api_key
        self._github_app_id = github_app_id
        self._github_private_key_path = github_private_key_path
        self._github_installation_id = github_installation_id
        super().__init__(**kwargs)

    async def setup_hook(self) -> None:
        self.add_view(DeleteView())
        self.add_dynamic_items(CreateIssueButton, CancelIssueButton, RetryIssueButton)

        self.http_client = httpx.AsyncClient()
        private_key_pem = Path(self._github_private_key_path).read_text()
        self.github_auth = GitHubAppAuth(
            app_id=self._github_app_id,
            private_key_pem=private_key_pem,
            installation_id=self._github_installation_id,
            client=self.http_client,
        )

        from google import genai

        gemini_client = genai.Client(api_key=self.gemini_api_key)
        transform = IssueGeneratorTransform(client=gemini_client)

        cog = CreateIssueCog(
            self,
            transform=transform,
        )
        await self.add_cog(cog)
        logger.info("CreateIssueCog loaded")

        debug_cog = DebugIssueCog(
            self,
            transform=transform,
        )
        await self.add_cog(debug_cog)
        logger.info("DebugIssueCog loaded")

        logger.info("Syncing command tree")
        await self.tree.sync()
        logger.info("Command tree synced")


def create_bot(
    gemini_api_key: str,
    github_app_id: str,
    github_private_key_path: str,
    github_installation_id: str,
) -> IssueBot:
    intents = discord.Intents.default()
    intents.message_content = True

    return IssueBot(
        gemini_api_key=gemini_api_key,
        github_app_id=github_app_id,
        github_private_key_path=github_private_key_path,
        github_installation_id=github_installation_id,
        command_prefix="!",
        intents=intents,
    )


if __name__ == "__main__":
    from src.logging_config import setup_logging

    setup_logging()

    bot = create_bot(
        gemini_api_key=os.environ["GEMINI_API_KEY"],
        github_app_id=os.environ["GITHUB_APP_ID"],
        github_private_key_path=os.environ["GITHUB_APP_PRIVATE_KEY_PATH"],
        github_installation_id=os.environ["GITHUB_APP_INSTALLATION_ID"],
    )
    bot.run(os.environ["DISCORD_BOT_TOKEN"])
