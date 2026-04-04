from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineData:
    input: str
    context: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class CachedCommandData:
    """Generic cached data for any command's retry flow."""

    cmd_type: str
    pipeline_data: PipelineData
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CachedOutputData:
    """Cached data for retrying a failed output action."""

    cmd_type: str
    payload: dict[str, Any] = field(default_factory=dict)
