import re
from dataclasses import dataclass
from typing import Callable


def check_unwanted_keywords(text: str, patterns: list[str]) -> list[str]:
    """Return patterns that match in text (case-insensitive regex)."""
    return [p for p in patterns if re.search(p, text, re.IGNORECASE)]


def check_required_keywords(text: str, patterns: list[str]) -> list[str]:
    """Return patterns that do NOT match in text (case-insensitive regex)."""
    return [p for p in patterns if not re.search(p, text, re.IGNORECASE)]


@dataclass
class Check:
    """A named validation that returns a list of violations (empty = pass)."""

    name: str
    evaluate: Callable[[str], list[str]]
    description: str = ""


def unwanted(*patterns: str, name: str = "unwanted_keywords", description: str = "") -> Check:
    """Check that none of the patterns appear in the output."""
    pat_list = list(patterns)
    return Check(
        name=name,
        evaluate=lambda text: check_unwanted_keywords(text, pat_list),
        description=description,
    )


def required(*patterns: str, name: str = "required_keywords", description: str = "") -> Check:
    """Check that all of the patterns appear in the output."""
    pat_list = list(patterns)
    return Check(
        name=name,
        evaluate=lambda text: check_required_keywords(text, pat_list),
        description=description,
    )
