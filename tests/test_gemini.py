from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import PipelineData
from src.transform.gemini import generate_issue


class TestGenerateIssue:
    @pytest.mark.asyncio
    async def test_returns_pipeline_data_with_generated_issue(self):
        mock_response = MagicMock()
        mock_response.text = "## Title\nLogin broken\n## Body\nUsers can't log in."

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        input_data = PipelineData(
            context={"messages": ["user1: login is broken", "user2: same here"]},
            input="login bug",
        )

        result = await generate_issue(input_data, client=mock_client)

        assert isinstance(result, PipelineData)
        assert result.input == mock_response.text
        assert "generated" in result.context
        assert mock_response.text in result.context["generated"]

    @pytest.mark.asyncio
    async def test_preserves_existing_context(self):
        mock_response = MagicMock()
        mock_response.text = "generated content"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        input_data = PipelineData(
            context={"messages": ["msg1"]},
            input="topic",
        )

        result = await generate_issue(input_data, client=mock_client)

        assert "messages" in result.context
        assert result.context["messages"] == ["msg1"]

    @pytest.mark.asyncio
    async def test_calls_gemini_with_prompt(self):
        mock_response = MagicMock()
        mock_response.text = "output"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        input_data = PipelineData(
            context={"messages": ["hello"]},
            input="topic",
        )

        await generate_issue(input_data, client=mock_client)

        mock_client.aio.models.generate_content.assert_called_once()
        call_kwargs = mock_client.aio.models.generate_content.call_args
        assert "gemini" in call_kwargs.kwargs.get("model", "").lower()
