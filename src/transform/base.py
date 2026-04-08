import logging
import time
from abc import ABC, abstractmethod

from src.models import PipelineData

logger = logging.getLogger(__name__)


_EXCLUDED_CONTEXT_KEYS = frozenset({"amendments"})


def _flatten_context_messages(data: PipelineData) -> str:
    return "\n".join(
        msg
        for key, msgs in data.context.items()
        if key not in _EXCLUDED_CONTEXT_KEYS
        for msg in msgs
    )


class BaseLLMTransform(ABC):
    """Abstract base for LLM-powered pipeline transforms.

    Subclasses must implement ``call_llm``.  Everything else (prompt
    building, run-loop, context management) is handled here.
    """

    system_prompt: str = ""
    model: str = ""
    temperature: float = 0.3
    max_output_tokens: int = 1024

    def build_system_prompt(self, data: PipelineData) -> str:
        return self.system_prompt

    def build_user_prompt(self, data: PipelineData) -> str:
        messages_text = _flatten_context_messages(data)
        return f"Focus: {data.input}\n\nChannel messages:\n{messages_text}"

    @abstractmethod
    async def call_llm(self, system_prompt: str, user_prompt: str) -> str: ...

    async def run(self, data: PipelineData) -> PipelineData:
        """Build prompts, call the LLM, and return new PipelineData."""
        system_prompt = self.build_system_prompt(data)
        user_prompt = self.build_user_prompt(data)

        logger.debug(
            "Calling LLM (model=%s, prompt_len=%d)", self.model, len(user_prompt)
        )
        t0 = time.monotonic()

        text = await self.call_llm(system_prompt, user_prompt)

        elapsed = (time.monotonic() - t0) * 1000
        logger.info("LLM responded (%.0fms, response_len=%d)", elapsed, len(text))

        new_context = dict(data.context)
        new_context["generated"] = [text]

        return PipelineData(context=new_context, input=text)
