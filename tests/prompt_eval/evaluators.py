import re


def check_unwanted_keywords(text: str, patterns: list[str]) -> list[str]:
    """Return patterns that match in text (case-insensitive regex)."""
    return [p for p in patterns if re.search(p, text, re.IGNORECASE)]


def check_required_keywords(text: str, patterns: list[str]) -> list[str]:
    """Return patterns that do NOT match in text (case-insensitive regex)."""
    return [p for p in patterns if not re.search(p, text, re.IGNORECASE)]
