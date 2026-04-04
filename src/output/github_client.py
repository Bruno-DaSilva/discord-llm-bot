from typing import Protocol, runtime_checkable


@runtime_checkable
class GitHubClient(Protocol):
    async def create_issue(
        self, owner: str, repo: str, title: str, body: str
    ) -> str: ...

    async def check_repo_installation(self, owner: str, repo: str) -> None: ...
