from typing import Protocol, runtime_checkable

from src.models import PipelineData


@runtime_checkable
class Transform(Protocol):
    model: str
    async def run(self, data: PipelineData) -> PipelineData: ...
