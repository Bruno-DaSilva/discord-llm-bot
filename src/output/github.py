import logging

import httpx

from src.output.github_auth import GitHubAppAuth

logger = logging.getLogger(__name__)


class RepoNotInstalled(Exception):
    """Raised when the GitHub App is not installed on the target repository."""

    def __init__(self, owner: str, repo: str) -> None:
        self.owner = owner
        self.repo = repo
        super().__init__(f"GitHub App is not installed on {owner}/{repo}")


async def check_repo_installation(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    app_jwt: str,
) -> None:
    """Verify the GitHub App is installed on owner/repo. Raises RepoNotInstalled if not."""
    response = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}/installation",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
    )
    if response.status_code == 404:
        raise RepoNotInstalled(owner, repo)
    response.raise_for_status()


async def create_issue(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    title: str,
    body: str,
    token: str,
) -> str:
    logger.info("Creating issue on %s/%s", owner, repo)
    response = await client.post(
        f"https://api.github.com/repos/{owner}/{repo}/issues",
        json={"title": title, "body": body},
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    response.raise_for_status()
    url = response.json()["html_url"]
    logger.info("Issue created: %s", url)
    return url


class GitHubService:
    """Wraps GitHub API operations behind a single interface."""

    def __init__(self, auth: GitHubAppAuth, client: httpx.AsyncClient) -> None:
        self._auth = auth
        self._client = client

    async def create_issue(self, owner: str, repo: str, title: str, body: str) -> str:
        token = await self._auth.get_token()
        return await create_issue(self._client, owner, repo, title, body, token)

    async def check_repo_installation(self, owner: str, repo: str) -> None:
        app_jwt = self._auth.get_app_jwt()
        await check_repo_installation(self._client, owner, repo, app_jwt)


def append_footer(body: str, author: str, message_link: str | None) -> str:
    footer = f"\n\n------\nAuthor: {author}"
    if message_link:
        footer += f"\nDiscord: {message_link}"
    return body + footer
