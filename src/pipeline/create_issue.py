from src.models import CachedCommandData, PipelineData
from src.output.github import append_footer
from src.output.github_client import GitHubClient
from src.transform.transform import Transform


class IssuePipeline:
    """Pure business-logic orchestrator for issue creation.

    No Discord imports — cogs handle all presentation concerns.
    """

    CMD_TYPE = "issue"

    def __init__(self, transform: Transform, github: GitHubClient) -> None:
        self.transform = transform
        self.github = github

    def build_pipeline_data(self, topic: str, messages: list[str]) -> PipelineData:
        return PipelineData(input=topic, context={"messages": messages})

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
        body: str, author_username: str, latest_message_link: str | None
    ) -> str:
        return append_footer(body, author_username, latest_message_link)
