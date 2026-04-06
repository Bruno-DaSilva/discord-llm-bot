import logging
import time

from google import genai

from src.models import PipelineData
from src.transform.prompts import ISSUE_GENERATOR_PROMPT, render_issue_prompt

logger = logging.getLogger(__name__)


def _flatten_context_messages(data: PipelineData) -> str:
    return "\n".join(msg for msgs in data.context.values() for msg in msgs)


class GeminiTransform:
    """Base class for Gemini-powered pipeline transforms.

    Subclasses override class attributes to customize behavior:
        system_prompt   -- the system instruction sent to the model
        model           -- the Gemini model name
        temperature     -- sampling temperature
        max_output_tokens -- response length cap
    """

    system_prompt: str = ""
    model: str = "gemini-2.5-flash"
    temperature: float = 0.3
    max_output_tokens: int = 1024

    def __init__(self, client: genai.Client) -> None:
        self.client = client

    def build_system_prompt(self, data: PipelineData) -> str:
        return self.system_prompt

    def build_user_prompt(self, data: PipelineData) -> str:
        messages_text = _flatten_context_messages(data)
        return f"Focus: {data.input}\n\nChannel messages:\n{messages_text}"

    async def run(self, data: PipelineData) -> PipelineData:
        """Call the Gemini API and return new PipelineData with the response stored under the 'generated' context key."""
        system_prompt = self.build_system_prompt(data)
        user_prompt = self.build_user_prompt(data)

        logger.debug(
            "Calling Gemini (model=%s, prompt_len=%d)", self.model, len(user_prompt)
        )
        t0 = time.monotonic()

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config={
                "system_instruction": system_prompt,
                "max_output_tokens": self.max_output_tokens,
                "temperature": self.temperature,
            },
        )

        elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            "Gemini responded (%.0fms, response_len=%d)", elapsed, len(response.text)
        )

        new_context = dict(data.context)
        new_context["generated"] = [response.text]

        return PipelineData(context=new_context, input=response.text)


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
