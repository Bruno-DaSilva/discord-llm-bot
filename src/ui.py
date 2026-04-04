import logging
import re
import time
import uuid
from typing import Self

import discord

from src.models import CachedGitHubCreate, CachedIssueData

logger = logging.getLogger(__name__)

_CACHE_TTL = 86400  # 24 hours
_retry_cache: dict[str, tuple[float, CachedIssueData]] = {}


def _evict_expired() -> None:
    now = time.monotonic()
    expired = [k for k, (ts, _) in _retry_cache.items() if now - ts > _CACHE_TTL]
    for k in expired:
        del _retry_cache[k]


def cache_pipeline_data(data: CachedIssueData | CachedGitHubCreate) -> str:
    _evict_expired()
    key = uuid.uuid4().hex[:8]
    _retry_cache[key] = (time.monotonic(), data)
    return key


def get_cached_pipeline_data(
    key: str,
) -> CachedIssueData | CachedGitHubCreate | None:
    entry = _retry_cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _retry_cache[key]
        return None
    return data


def build_error_embed(error: Exception) -> discord.Embed:
    error_type = type(error).__name__
    return discord.Embed(
        title="Something went wrong",
        description=f"**{error_type}**: {error}\n\nYou can retry or cancel.",
        color=discord.Color.red(),
    )


class DeleteButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            style=discord.ButtonStyle.grey,
            emoji="\N{WASTEBASKET}",
            custom_id="delete_issue_msg",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.message.delete()


class DeleteView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(DeleteButton())


class CreateIssueButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"create_issue:(?P<owner>[^/]+)/(?P<repo>[^/]+)/(?P<key>.+)",
):
    def __init__(self, owner: str, repo: str, cache_key: str) -> None:
        self.owner = owner
        self.repo = repo
        self.cache_key = cache_key
        super().__init__(
            discord.ui.Button(
                label="Create",
                style=discord.ButtonStyle.green,
                custom_id=f"create_issue:{owner}/{repo}/{cache_key}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
    ) -> Self:
        return cls(owner=match["owner"], repo=match["repo"], cache_key=match["key"])

    async def callback(self, interaction: discord.Interaction) -> None:
        logger.info("Create button pressed: %s/%s", self.owner, self.repo)

        cached = get_cached_pipeline_data(self.cache_key)
        if cached is None:
            await interaction.response.send_message(
                "Session expired. Please run the command again.",
                ephemeral=True,
            )
            return

        issue_body = interaction.message.embeds[0].description
        lines = issue_body.strip().split("\n", 1)
        title = lines[0].lstrip("# ").strip()
        body = lines[1].strip() if len(lines) > 1 else ""

        from src.output.github import append_footer

        body = append_footer(
            body, cached.metadata.author_username, cached.metadata.latest_message_link
        )

        try:
            url = await interaction.client.github.create_issue(
                self.owner, self.repo, title, body
            )
        except Exception as exc:
            logger.exception("Failed to create issue on GitHub")
            github_data = CachedGitHubCreate(title=title, body=body)
            new_key = cache_pipeline_data(github_data)
            embed = build_error_embed(exc)
            view = GitHubErrorView(owner=self.owner, repo=self.repo, retry_key=new_key)
            await interaction.response.edit_message(embed=embed, view=view)
            return

        await interaction.response.edit_message(
            content=f"Issue created: {url}", view=None
        )
        await interaction.channel.send(
            content=f"Issue created: {url}", view=DeleteView()
        )


class RetryIssueButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"retry_issue:(?P<owner>[^/]+)/(?P<repo>[^/]+)/(?P<key>.+)",
):
    def __init__(self, owner: str, repo: str, retry_key: str) -> None:
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
        match: re.Match[str],
    ) -> Self:
        return cls(
            owner=match["owner"],
            repo=match["repo"],
            retry_key=match["key"],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        data = get_cached_pipeline_data(self.retry_key)
        if data is None:
            await interaction.response.send_message(
                "Session expired. Please run the command again.",
                ephemeral=True,
            )
            return

        from src.cogs.create_issue import IssuePreviewView

        loading_view = IssuePreviewView(owner=self.owner, repo=self.repo, loading=True)
        await interaction.response.edit_message(view=loading_view)

        cog = interaction.client.get_cog("CreateIssueCog")
        new_key = cache_pipeline_data(data)

        try:
            result = await cog.transform.run(data.pipeline_data)
        except Exception as exc:
            logger.exception("Transform failed in retry")
            embed = build_error_embed(exc)
            view = ErrorView(owner=self.owner, repo=self.repo, retry_key=new_key)
            await interaction.edit_original_response(embed=embed, view=view)
            return

        view = IssuePreviewView(owner=self.owner, repo=self.repo, cache_key=new_key)

        embed = discord.Embed(description=result.input)
        await interaction.edit_original_response(embed=embed, view=view)


class CancelIssueButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"cancel_issue:(?P<owner>[^/]+)/(?P<repo>.+)",
):
    def __init__(self, owner: str, repo: str) -> None:
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
        match: re.Match[str],
    ) -> Self:
        return cls(owner=match["owner"], repo=match["repo"])

    async def callback(self, interaction: discord.Interaction) -> None:
        logger.info("Cancel button pressed")
        await interaction.response.edit_message(
            content="Issue creation cancelled.", embed=None, view=None
        )


class RetryGitHubButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"retry_github:(?P<owner>[^/]+)/(?P<repo>[^/]+)/(?P<key>.+)",
):
    def __init__(self, owner: str, repo: str, retry_key: str) -> None:
        self.owner = owner
        self.repo = repo
        self.retry_key = retry_key
        super().__init__(
            discord.ui.Button(
                label="Retry",
                style=discord.ButtonStyle.blurple,
                custom_id=f"retry_github:{owner}/{repo}/{retry_key}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
    ) -> Self:
        return cls(
            owner=match["owner"],
            repo=match["repo"],
            retry_key=match["key"],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        cached = get_cached_pipeline_data(self.retry_key)
        if not isinstance(cached, CachedGitHubCreate):
            await interaction.response.send_message(
                "Session expired. Please run the command again.",
                ephemeral=True,
            )
            return

        try:
            url = await interaction.client.github.create_issue(
                self.owner, self.repo, cached.title, cached.body
            )
        except Exception as exc:
            logger.exception("GitHub retry failed")
            new_data = CachedGitHubCreate(title=cached.title, body=cached.body)
            new_key = cache_pipeline_data(new_data)
            embed = build_error_embed(exc)
            view = GitHubErrorView(owner=self.owner, repo=self.repo, retry_key=new_key)
            await interaction.response.edit_message(embed=embed, view=view)
            return

        await interaction.response.edit_message(
            content=f"Issue created: {url}", embed=None, view=None
        )
        await interaction.channel.send(
            content=f"Issue created: {url}", view=DeleteView()
        )


class GitHubErrorView(discord.ui.View):
    def __init__(self, owner: str, repo: str, retry_key: str) -> None:
        super().__init__(timeout=None)
        self.add_item(RetryGitHubButton(owner=owner, repo=repo, retry_key=retry_key))
        self.add_item(CancelIssueButton(owner=owner, repo=repo))


class ErrorView(discord.ui.View):
    def __init__(self, owner: str, repo: str, retry_key: str) -> None:
        super().__init__(timeout=None)
        self.add_item(RetryIssueButton(owner=owner, repo=repo, retry_key=retry_key))
        self.add_item(CancelIssueButton(owner=owner, repo=repo))
