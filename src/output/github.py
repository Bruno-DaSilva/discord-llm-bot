import httpx


async def create_issue(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    title: str,
    body: str,
    token: str,
) -> str:
    response = await client.post(
        f"https://api.github.com/repos/{owner}/{repo}/issues",
        json={"title": title, "body": body},
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    response.raise_for_status()
    return response.json()["html_url"]
