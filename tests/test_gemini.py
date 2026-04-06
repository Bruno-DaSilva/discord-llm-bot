from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import PipelineData
from src.transform.gemini import GeminiTransform, IssueGeneratorTransform
from src.transform.transform import Transform


class TestGeminiTransform:
    """Tests for the base class contract."""

    def _make_transform(self, client=None, **overrides):
        attrs = {
            "system_prompt": "You are a test assistant.",
            "model": "gemini-test-model",
            "temperature": 0.5,
            "max_output_tokens": 512,
        }
        attrs.update(overrides)
        SubClass = type("Sub", (GeminiTransform,), attrs)
        mock_client = client or MagicMock()
        if client is None:
            mock_client.aio.models.generate_content = AsyncMock(
                return_value=MagicMock(text="response text")
            )
        return SubClass(client=mock_client), mock_client

    def test_satisfies_transform_protocol(self):
        mock_client = MagicMock()
        assert isinstance(GeminiTransform(client=mock_client), Transform)

    @pytest.mark.asyncio
    async def test_run_raises_on_api_error(self):
        transform, mock_client = self._make_transform()
        mock_client.aio.models.generate_content.side_effect = RuntimeError("API down")
        data = PipelineData(input="focus", context={"messages": ["msg1"]})
        with pytest.raises(RuntimeError, match="API down"):
            await transform.run(data)

    @pytest.mark.asyncio
    async def test_build_user_prompt_default(self):
        transform, _ = self._make_transform()
        data = PipelineData(
            input="login bug",
            context={"messages": ["user1: broken", "user2: same"]},
        )
        prompt = transform.build_user_prompt(data)
        assert "login bug" in prompt
        assert "user1: broken" in prompt
        assert "user2: same" in prompt

    def test_build_system_prompt_returns_class_attribute(self):
        transform, _ = self._make_transform(system_prompt="Static prompt")
        data = PipelineData(input="focus", context={})
        assert transform.build_system_prompt(data) == "Static prompt"


class TestIssueGeneratorTransform:
    """Tests for the concrete issue-generation subclass."""

    def test_satisfies_transform_protocol(self):
        mock_client = MagicMock()
        assert isinstance(IssueGeneratorTransform(client=mock_client), Transform)

    def test_build_user_prompt_returns_empty(self):
        transform = IssueGeneratorTransform(client=MagicMock())
        data = PipelineData(input="focus", context={"messages": ["msg"]})
        assert transform.build_user_prompt(data) == ""

    @pytest.mark.asyncio
    async def test_full_round_trip(self):
        mock_response = MagicMock()
        mock_response.text = "## Title\nLogin broken\n## Body\nUsers can't log in."
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        transform = IssueGeneratorTransform(client=mock_client)
        data = PipelineData(
            context={"messages": ["user1: login is broken", "user2: same here"]},
            input="login bug",
        )
        result = await transform.run(data)
        assert result.input == mock_response.text
        assert result.context["generated"] == [mock_response.text]
        assert result.context["messages"] == [
            "user1: login is broken",
            "user2: same here",
        ]
