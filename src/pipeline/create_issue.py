import logging

import discord

from src.models import CachedCommandData, CachedOutputData, PipelineData
from src.output.github import RepoNotInstalled, append_footer
from src.output.github_client import GitHubClient
from src.transform.transform import Transform
from src.cogs.ui import (
    DeleteView,
    ErrorView,
    OutputErrorView,
    PreviewView,
    build_error_embed,
    cache_pipeline_data,
)

logger = logging.getLogger(__name__)


class IssuePipeline:
    """Orchestrates the full issue-creation workflow.

    Owns both business logic (data construction, transform, GitHub calls)
    and pipeline presentation (loading states, previews, error views).
    Implements the CommandHandler protocol so buttons dispatch directly here.
    """

    CMD_TYPE = "issue"

    def __init__(self, transform: Transform, github: GitHubClient) -> None:
        self.transform = transform
        self.github = github

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def build_pipeline_data(self, focus: str, messages: list[str]) -> PipelineData:
        return PipelineData(input=focus, context={"messages": messages})

    def build_cached_data(
        self,
        pipeline_data: PipelineData,
        *,
        author_username: str,
        latest_message_link: str | None,
        owner: str,
        repo: str,
    ) -> CachedCommandData:
        return CachedCommandData(
            cmd_type=self.CMD_TYPE,
            pipeline_data=pipeline_data,
            extra={
                "author_username": author_username,
                "latest_message_link": latest_message_link,
                "owner": owner,
                "repo": repo,
                "model": self.transform.model,
            },
        )

    async def generate(self, data: PipelineData) -> PipelineData:
        return await self.transform.run(data)

    async def check_repo(self, owner: str, repo: str) -> None:
        await self.github.check_repo_installation(owner, repo)

    async def create_issue(
        self, owner: str, repo: str, title: str, body: str
    ) -> str:
        return await self.github.create_issue(owner, repo, title, body)

    @staticmethod
    def parse_preview(preview_text: str) -> tuple[str, str]:
        lines = preview_text.strip().split("\n", 1)
        title = lines[0].lstrip("# ").strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        return title, body

    @staticmethod
    def build_issue_body(
        body: str,
        author_username: str,
        latest_message_link: str | None,
        model: str | None = None,
    ) -> str:
        return append_footer(body, author_username, latest_message_link, model=model)

    # ------------------------------------------------------------------
    # Pipeline orchestration
    # ------------------------------------------------------------------

    async def run(
        self,
        interaction: discord.Interaction,
        *,
        repo: str,
        focus: str,
        messages: list[str],
        latest_message_link: str | None,
        ephemeral: bool = False,
    ) -> None:
        """Check repo installation, run the LLM transform, and display a preview with confirm/retry/cancel buttons."""
        data = self.build_pipeline_data(focus, messages)

        owner, repo_name = repo.split("/", 1)

        loading_embed = discord.Embed(
            description="Generating issue\N{HORIZONTAL ELLIPSIS}",
            color=discord.Color.blurple(),
        )
        loading_msg = await interaction.followup.send(
            embed=loading_embed, ephemeral=ephemeral, wait=True
        )

        try:
            await self.check_repo(owner, repo_name)
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

        cached = self.build_cached_data(
            data,
            author_username=interaction.user.display_name,
            latest_message_link=latest_message_link,
            owner=owner,
            repo=repo_name,
        )
        retry_key = cache_pipeline_data(cached)

        try:
            result = await self.generate(data)
        except Exception as exc:
            logger.exception("Transform failed")
            embed = build_error_embed(exc)
            view = ErrorView(cmd_type=self.CMD_TYPE, retry_key=retry_key)
            await loading_msg.edit(embed=embed, view=view)
            return

        view = PreviewView(
            cmd_type=self.CMD_TYPE,
            cache_key=retry_key,
            confirm_label="Create",
        )

        embed = discord.Embed(description=result.input)
        await loading_msg.edit(embed=embed, view=view)

    # ------------------------------------------------------------------
    # CommandHandler protocol (dispatched by UI buttons)
    # ------------------------------------------------------------------

    async def on_confirm(
        self, interaction: discord.Interaction, cached: CachedCommandData
    ) -> None:
        """Extract title/body from the preview embed, append a footer, and create the GitHub issue."""
        issue_body = interaction.message.embeds[0].description
        title, body = self.parse_preview(issue_body)

        body = self.build_issue_body(
            body,
            cached.extra["author_username"],
            cached.extra.get("latest_message_link"),
            model=cached.extra.get("model"),
        )

        owner = cached.extra["owner"]
        repo = cached.extra["repo"]

        try:
            url = await self.create_issue(owner, repo, title, body)
        except Exception as exc:
            logger.exception("Failed to create issue on GitHub")
            github_data = CachedOutputData(
                cmd_type=self.CMD_TYPE,
                payload={
                    "title": title,
                    "body": body,
                    "owner": owner,
                    "repo": repo,
                },
            )
            new_key = cache_pipeline_data(github_data)
            embed = build_error_embed(exc)
            view = OutputErrorView(cmd_type=self.CMD_TYPE, retry_key=new_key)
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
        loading_view = PreviewView(cmd_type=self.CMD_TYPE, loading=True)
        await interaction.response.edit_message(view=loading_view)

        new_key = cache_pipeline_data(cached)

        try:
            result = await self.generate(cached.pipeline_data)
        except Exception as exc:
            logger.exception("Transform failed in retry")
            embed = build_error_embed(exc)
            view = ErrorView(cmd_type=self.CMD_TYPE, retry_key=new_key)
            await interaction.edit_original_response(embed=embed, view=view)
            return

        view = PreviewView(
            cmd_type=self.CMD_TYPE,
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
            url = await self.create_issue(owner, repo, title, body)
        except Exception as exc:
            logger.exception("GitHub retry failed")
            new_key = cache_pipeline_data(cached)
            embed = build_error_embed(exc)
            view = OutputErrorView(cmd_type=self.CMD_TYPE, retry_key=new_key)
            await interaction.response.edit_message(embed=embed, view=view)
            return

        await interaction.response.edit_message(
            content=f"Issue created: {url}", embed=None, view=None
        )
        await interaction.channel.send(
            content=f"Issue created: {url}", view=DeleteView()
        )
