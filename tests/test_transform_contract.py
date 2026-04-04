"""Contract tests for the Transform protocol.

Any Transform implementation must satisfy these invariants. Add new
implementations to the ``transform`` fixture's parametrize list.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import PipelineData
from src.transform.gemini import GeminiTransform
from tests.conftest import FakeTransform


def _make_gemini_transform():
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        return_value=MagicMock(text="generated output")
    )
    SubClass = type(
        "TestGemini",
        (GeminiTransform,),
        {"system_prompt": "test", "model": "test-model"},
    )
    return SubClass(client=mock_client)


@pytest.fixture(
    params=["fake", "gemini"],
)
def transform(request):
    if request.param == "fake":
        return FakeTransform()
    return _make_gemini_transform()


class TestTransformContract:
    @pytest.mark.asyncio
    async def test_run_returns_pipeline_data(self, transform):
        data = PipelineData(input="topic", context={"messages": ["msg1"]})
        result = await transform.run(data)
        assert isinstance(result, PipelineData)

    @pytest.mark.asyncio
    async def test_run_sets_generated_context(self, transform):
        data = PipelineData(input="topic", context={"messages": ["msg1"]})
        result = await transform.run(data)
        assert "generated" in result.context
        assert isinstance(result.context["generated"], list)
        assert len(result.context["generated"]) >= 1

    @pytest.mark.asyncio
    async def test_run_sets_non_empty_input(self, transform):
        data = PipelineData(input="topic", context={"messages": ["msg1"]})
        result = await transform.run(data)
        assert isinstance(result.input, str)
        assert len(result.input) > 0

    @pytest.mark.asyncio
    async def test_run_preserves_existing_context(self, transform):
        data = PipelineData(input="topic", context={"messages": ["msg1"]})
        result = await transform.run(data)
        assert result.context["messages"] == ["msg1"]
