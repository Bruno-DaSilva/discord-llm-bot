from typing import Protocol

from src.models import PipelineData


class Transform(Protocol):
    async def run(self, data: PipelineData) -> PipelineData: ...
