import logging
import re

import discord

logger = logging.getLogger(__name__)


class DeleteButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.grey,
            emoji="\N{WASTEBASKET}",
            custom_id="delete_issue_msg",
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.delete()


class DeleteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DeleteButton())


class CreateIssueButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"create_issue:(?P<owner>[^/]+)/(?P<repo>.+)",
):
    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        super().__init__(
            discord.ui.Button(
                label="Create",
                style=discord.ButtonStyle.green,
                custom_id=f"create_issue:{owner}/{repo}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match,
    ):
        return cls(owner=match["owner"], repo=match["repo"])

    async def callback(self, interaction: discord.Interaction):
        logger.info("Create button pressed: %s/%s", self.owner, self.repo)

        issue_body = interaction.message.content
        lines = issue_body.strip().split("\n", 1)
        title = lines[0].lstrip("# ").strip()

        # TODO: replace with real GitHub API call
        url = f"https://github.com/{self.owner}/{self.repo}/issues/NEW"
        logger.info("Mock issue created: %s (title: %s)", url, title)

        await interaction.response.edit_message(
            content=f"Issue created: {url}", view=None
        )
        await interaction.followup.send(
            content=f"Issue created: {url}", view=DeleteView(), ephemeral=False
        )


class CancelIssueButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"cancel_issue:(?P<owner>[^/]+)/(?P<repo>.+)",
):
    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        super().__init__(
            discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.red,
                custom_id=f"cancel_issue:{owner}/{repo}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match,
    ):
        return cls(owner=match["owner"], repo=match["repo"])

    async def callback(self, interaction: discord.Interaction):
        logger.info("Cancel button pressed")
        await interaction.response.edit_message(
            content="Issue creation cancelled.", view=None
        )
