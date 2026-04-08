def normalize_repo(repo: str) -> str:
    """Lowercase and strip leading/trailing slashes from an owner/repo string."""
    return repo.lower().strip("/")
