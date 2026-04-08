import os
from collections.abc import Callable, Coroutine
from typing import Any

from src.transform.gemini import IssueGeneratorTransform

# Type alias for provider call functions
ProviderCallFn = Callable[
    [str, str, str, float, int],
    Coroutine[Any, Any, str],
]


class TestableIssueTransform(IssueGeneratorTransform):
    """Issue transform with a swappable LLM backend.

    Inherits prompt construction from IssueGeneratorTransform.
    Overrides call_llm to delegate to an injectable call function.
    """

    def __init__(self, call_fn: ProviderCallFn) -> None:
        # Intentionally skip GeminiTransform.__init__ — no genai.Client needed
        self._call_fn = call_fn

    async def call_llm(self, system_prompt: str, user_prompt: str) -> str:
        return await self._call_fn(
            self.model,
            system_prompt,
            user_prompt,
            self.temperature,
            self.max_output_tokens,
        )


async def gemini_call(
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_output_tokens: int,
) -> str:
    """Call Gemini API directly. Requires GEMINI_API_KEY env var."""
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = await client.aio.models.generate_content(
        model=model,
        contents=user_prompt,
        config={
            "system_instruction": system_prompt,
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
        },
    )
    return response.text
