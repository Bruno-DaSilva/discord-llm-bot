def normalize_repo(repo: str) -> str:
    """Lowercase and strip trailing slashes from an owner/repo string."""
    return repo.lower().strip("/")
