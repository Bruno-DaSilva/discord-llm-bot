from google import genai

from src.models import PipelineData
from src.transform.base import BaseLLMTransform, _flatten_context_messages
from src.transform.prompts import ISSUE_GENERATOR_PROMPT, render_issue_prompt


class GeminiTransform(BaseLLMTransform):
    """Gemini-powered pipeline transform.

    Subclasses override class attributes to customize behavior.
    """

    model: str = "gemini-2.5-flash"

    def __init__(self, client: genai.Client) -> None:
        self.client = client

    async def call_llm(self, system_prompt: str, user_prompt: str) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config={
                "system_instruction": system_prompt,
                "max_output_tokens": self.max_output_tokens,
                "temperature": self.temperature,
            },
        )
        return response.text


class IssueGeneratorTransform(GeminiTransform):
    system_prompt = ISSUE_GENERATOR_PROMPT
    model = "gemini-3-flash-preview"
    temperature = 0.3
    max_output_tokens = 8096

    def build_system_prompt(self, data: PipelineData) -> str:
        messages_text = _flatten_context_messages(data)
        return render_issue_prompt(data.input, messages_text)

    def build_user_prompt(self, data: PipelineData) -> str:
        return ""
