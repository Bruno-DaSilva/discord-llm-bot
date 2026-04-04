from dataclasses import dataclass, field


@dataclass
class PipelineData:
    input: str
    context: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class IssueMetadata:
    author_username: str
    latest_message_link: str | None


@dataclass
class CachedIssueData:
    pipeline_data: PipelineData
    metadata: IssueMetadata


@dataclass
class CachedGitHubCreate:
    title: str
    body: str
