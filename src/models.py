from dataclasses import dataclass, field


@dataclass
class PipelineData:
    input: str
    context: dict[str, list[str]] = field(default_factory=dict)
