import discord
from discord import app_commands
from discord.errors import NotFound
from discord.ext import commands

from src.models import PipelineData
from src.output.discord import fetch_messages
from src.transform.gemini import generate_issue


class CreateIssueCog(commands.Cog):
    def __init__(self, bot: commands.Bot, gemini_client, github_token: str):
        self.bot = bot
        self.gemini_client = gemini_client
        self.github_token = github_token

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
    ):
        await self._do_create_issue(interaction, repo=repo, topic=topic, n=n)

    async def _do_create_issue(
        self,
        interaction: discord.Interaction,
        repo: str,
        topic: str,
        n: int,
    ):
        try:
            await interaction.response.defer()
        except NotFound:
            return

        messages = await fetch_messages(interaction.channel, limit=n)

        data = PipelineData(
            context={"messages": messages},
            input=topic,
        )

        result = await generate_issue(data, client=self.gemini_client)

        owner, repo_name = repo.split("/", 1)
        view = IssuePreviewView(
            owner=owner,
            repo=repo_name,
            issue_body=result.input,
            github_token=self.github_token,
        )

        await interaction.edit_original_response(
            content=result.input, view=view
        )


class IssuePreviewView(discord.ui.View):
    def __init__(
        self, owner: str, repo: str, issue_body: str, github_token: str
    ):
        super().__init__(timeout=900)
        self.owner = owner
        self.repo = repo
        self.issue_body = issue_body
        self.github_token = github_token

    @discord.ui.button(label="Create", style=discord.ButtonStyle.green)
    async def create_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        from src.output.github import create_issue
        import httpx

        async with httpx.AsyncClient() as client:
            lines = self.issue_body.strip().split("\n", 1)
            title = lines[0].lstrip("# ").strip()
            body = lines[1].strip() if len(lines) > 1 else ""

            url = await create_issue(
                client=client,
                owner=self.owner,
                repo=self.repo,
                title=title,
                body=body,
                token=self.github_token,
            )

        await interaction.response.edit_message(
            content=f"Issue created: {url}", view=None
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="Issue creation cancelled.", view=None
        )
