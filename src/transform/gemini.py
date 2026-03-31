import logging
import time

from src.models import PipelineData

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a GitHub issue writer. Given channel messages and a topic,
generate a well-structured GitHub issue with a clear title and body.
Format: start with the title on the first line, then the body."""


async def generate_issue(data: PipelineData, client) -> PipelineData:
    messages_text = "\n".join(
        msg for msgs in data.context.values() for msg in msgs
    )
    user_prompt = f"Topic: {data.input}\n\nChannel messages:\n{messages_text}"

    logger.debug("Calling Gemini (model=gemini-2.5-flash, prompt_len=%d)", len(user_prompt))
    t0 = time.monotonic()

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config={
            "system_instruction": SYSTEM_PROMPT,
            "max_output_tokens": 1024,
            "temperature": 0.3,
        },
    )

    elapsed = (time.monotonic() - t0) * 1000
    logger.info("Gemini responded (%.0fms, response_len=%d)", elapsed, len(response.text))

    new_context = dict(data.context)
    new_context["generated"] = [response.text]

    return PipelineData(context=new_context, input=response.text)
