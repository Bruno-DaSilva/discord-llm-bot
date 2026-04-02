from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import PipelineData
from src.transform.gemini import GeminiTransform, IssueGeneratorTransform


class TestGeminiTransform:
    """Tests for the base class mechanics."""

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

    @pytest.mark.asyncio
    async def test_run_returns_pipeline_data(self):
        transform, _ = self._make_transform()
        data = PipelineData(input="topic", context={"messages": ["msg1"]})
        result = await transform.run(data)
        assert isinstance(result, PipelineData)

    @pytest.mark.asyncio
    async def test_run_sets_generated_context(self):
        transform, mock_client = self._make_transform()
        mock_client.aio.models.generate_content.return_value.text = "generated"
        data = PipelineData(input="topic", context={"messages": ["msg1"]})
        result = await transform.run(data)
        assert result.context["generated"] == ["generated"]
        assert result.input == "generated"

    @pytest.mark.asyncio
    async def test_run_preserves_existing_context(self):
        transform, _ = self._make_transform()
        data = PipelineData(input="topic", context={"messages": ["msg1"]})
        result = await transform.run(data)
        assert result.context["messages"] == ["msg1"]

    @pytest.mark.asyncio
    async def test_run_calls_api_with_configured_model(self):
        transform, mock_client = self._make_transform(model="gemini-custom")
        data = PipelineData(input="topic", context={"messages": ["msg1"]})
        await transform.run(data)
        call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-custom"

    @pytest.mark.asyncio
    async def test_run_calls_api_with_configured_system_prompt(self):
        transform, mock_client = self._make_transform(
            system_prompt="Custom prompt"
        )
        data = PipelineData(input="topic", context={"messages": ["msg1"]})
        await transform.run(data)
        call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
        assert call_kwargs["config"]["system_instruction"] == "Custom prompt"

    @pytest.mark.asyncio
    async def test_run_calls_api_with_configured_temperature(self):
        transform, mock_client = self._make_transform(temperature=0.9)
        data = PipelineData(input="topic", context={"messages": ["msg1"]})
        await transform.run(data)
        call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
        assert call_kwargs["config"]["temperature"] == 0.9

    @pytest.mark.asyncio
    async def test_run_calls_api_with_configured_max_tokens(self):
        transform, mock_client = self._make_transform(max_output_tokens=2048)
        data = PipelineData(input="topic", context={"messages": ["msg1"]})
        await transform.run(data)
        call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
        assert call_kwargs["config"]["max_output_tokens"] == 2048

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
        data = PipelineData(input="topic", context={})
        assert transform.build_system_prompt(data) == "Static prompt"

    @pytest.mark.asyncio
    async def test_run_passes_built_system_prompt_to_api(self):
        transform, mock_client = self._make_transform(
            system_prompt="Template {{ data }}"
        )
        data = PipelineData(input="topic", context={"messages": ["msg1"]})
        await transform.run(data)
        call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
        assert call_kwargs["config"]["system_instruction"] == "Template {{ data }}"


class TestIssueGeneratorTransform:
    """Tests for the concrete issue-generation subclass."""

    def test_has_correct_model(self):
        assert IssueGeneratorTransform.model == "gemini-2.5-flash"

    def test_has_correct_temperature(self):
        assert IssueGeneratorTransform.temperature == 0.3

    def test_has_correct_max_tokens(self):
        assert IssueGeneratorTransform.max_output_tokens == 8096

    def test_system_prompt_mentions_ticket(self):
        assert "ticket" in IssueGeneratorTransform.system_prompt.lower()

    def test_build_system_prompt_interpolates_topic(self):
        transform = IssueGeneratorTransform(client=MagicMock())
        data = PipelineData(input="login bug", context={"messages": ["msg"]})
        rendered = transform.build_system_prompt(data)
        assert "login bug" in rendered
        assert "{{ context.ticket_topic }}" not in rendered

    def test_build_system_prompt_interpolates_messages(self):
        transform = IssueGeneratorTransform(client=MagicMock())
        data = PipelineData(
            input="topic",
            context={"messages": ["user1: broken", "user2: same"]},
        )
        rendered = transform.build_system_prompt(data)
        assert "user1: broken" in rendered
        assert "user2: same" in rendered
        assert '{{ context.messages.join("\\n") }}' not in rendered

    def test_build_user_prompt_returns_empty(self):
        transform = IssueGeneratorTransform(client=MagicMock())
        data = PipelineData(input="topic", context={"messages": ["msg"]})
        assert transform.build_user_prompt(data) == ""

    @pytest.mark.asyncio
    async def test_full_round_trip(self):
        mock_response = MagicMock()
        mock_response.text = "## Title\nLogin broken\n## Body\nUsers can't log in."
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )
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
