import logging

import httpx

logger = logging.getLogger(__name__)


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


def append_footer(body: str, author: str, message_link: str | None) -> str:
    footer = f"\n\n------\nAuthor: {author}"
    if message_link:
        footer += f"\nDiscord: {message_link}"
    return body + footer
