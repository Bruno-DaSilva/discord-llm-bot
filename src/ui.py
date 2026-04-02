import logging
import re
import uuid

import discord

from src.models import PipelineData

logger = logging.getLogger(__name__)

_retry_cache: dict[str, PipelineData] = {}


def cache_pipeline_data(data: PipelineData) -> str:
    key = uuid.uuid4().hex[:8]
    _retry_cache[key] = data
    return key


def get_cached_pipeline_data(key: str) -> PipelineData | None:
    return _retry_cache.get(key)


def build_error_embed(error: Exception) -> discord.Embed:
    error_type = type(error).__name__
    return discord.Embed(
        title="Something went wrong",
        description=f"**{error_type}**: {error}\n\nYou can retry or cancel.",
        color=discord.Color.red(),
    )


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

        issue_body = interaction.message.embeds[0].description
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


class RetryIssueButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"retry_issue:(?P<owner>[^/]+)/(?P<repo>[^/]+)/(?P<key>.+)",
):
    def __init__(self, owner: str, repo: str, retry_key: str):
        self.owner = owner
        self.repo = repo
        self.retry_key = retry_key
        super().__init__(
            discord.ui.Button(
                label="Retry",
                style=discord.ButtonStyle.blurple,
                custom_id=f"retry_issue:{owner}/{repo}/{retry_key}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match,
    ):
        return cls(
            owner=match["owner"],
            repo=match["repo"],
            retry_key=match["key"],
        )

    async def callback(self, interaction: discord.Interaction):
        data = get_cached_pipeline_data(self.retry_key)
        if data is None:
            await interaction.response.send_message(
                "Session expired. Please run the command again.",
                ephemeral=True,
            )
            return

        from src.cogs.create_issue import IssuePreviewView

        loading_view = IssuePreviewView(
            owner=self.owner, repo=self.repo, loading=True
        )
        await interaction.response.edit_message(view=loading_view)

        cog = interaction.client.get_cog("CreateIssueCog")
        new_key = cache_pipeline_data(data)

        try:
            result = await cog.transform.run(data)
        except Exception as exc:
            logger.exception("Transform failed in retry")
            embed = build_error_embed(exc)
            view = ErrorView(owner=self.owner, repo=self.repo, retry_key=new_key)
            await interaction.edit_original_response(embed=embed, view=view)
            return

        view = IssuePreviewView(
            owner=self.owner, repo=self.repo, retry_key=new_key
        )

        embed = discord.Embed(description=result.input)
        await interaction.edit_original_response(embed=embed, view=view)


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
            content="Issue creation cancelled.", embed=None, view=None
        )


class ErrorView(discord.ui.View):
    def __init__(self, owner: str, repo: str, retry_key: str):
        super().__init__(timeout=None)
        self.add_item(RetryIssueButton(owner=owner, repo=repo, retry_key=retry_key))
        self.add_item(CancelIssueButton(owner=owner, repo=repo))
