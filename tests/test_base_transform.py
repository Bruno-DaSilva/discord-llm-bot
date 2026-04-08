"""Tests for BaseLLMTransform ABC."""

from unittest.mock import AsyncMock

import pytest

from src.models import PipelineData
from src.transform.base import BaseLLMTransform
from src.transform.transform import Transform


class StubTransform(BaseLLMTransform):
    """Concrete stub for testing the ABC."""

    model = "stub-model"
    system_prompt = "You are a stub."

    async def call_llm(self, system_prompt: str, user_prompt: str) -> str:
        return "stub response"


class TestBaseLLMTransform:
    def test_satisfies_transform_protocol(self):
        assert isinstance(StubTransform(), Transform)

    @pytest.mark.asyncio
    async def test_run_delegates_to_call_llm(self):
        t = StubTransform()
        t.call_llm = AsyncMock(return_value="mocked response")
        data = PipelineData(input="topic", context={"messages": ["msg1"]})

        await t.run(data)

        t.call_llm.assert_awaited_once()
        args = t.call_llm.call_args
        system_prompt, user_prompt = args[0]
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)

    @pytest.mark.asyncio
    async def test_run_wraps_result_in_pipeline_data(self):
        t = StubTransform()
        data = PipelineData(input="topic", context={"messages": ["msg1"]})

        result = await t.run(data)

        assert isinstance(result, PipelineData)
        assert result.input == "stub response"
        assert result.context["generated"] == ["stub response"]

    @pytest.mark.asyncio
    async def test_run_preserves_existing_context(self):
        t = StubTransform()
        data = PipelineData(input="topic", context={"messages": ["msg1"]})

        result = await t.run(data)

        assert result.context["messages"] == ["msg1"]

    def test_build_system_prompt_returns_class_attribute(self):
        t = StubTransform()
        data = PipelineData(input="topic", context={})
        assert t.build_system_prompt(data) == "You are a stub."

    def test_build_user_prompt_includes_input_and_messages(self):
        t = StubTransform()
        data = PipelineData(
            input="login bug",
            context={"messages": ["user1: broken", "user2: same"]},
        )
        prompt = t.build_user_prompt(data)
        assert "login bug" in prompt
        assert "user1: broken" in prompt
        assert "user2: same" in prompt

    def test_build_user_prompt_excludes_amendments(self):
        t = StubTransform()
        data = PipelineData(
            input="topic",
            context={"messages": ["msg1"], "amendments": ["do X"]},
        )
        prompt = t.build_user_prompt(data)
        assert "do X" not in prompt

    def test_cannot_instantiate_without_call_llm(self):
        """ABC should prevent instantiation without implementing call_llm."""

        class Incomplete(BaseLLMTransform):
            model = "test"

        with pytest.raises(TypeError):
            Incomplete()
