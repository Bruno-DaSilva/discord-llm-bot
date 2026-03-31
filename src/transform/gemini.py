from src.models import PipelineData

SYSTEM_PROMPT = """You are a GitHub issue writer. Given channel messages and a topic,
generate a well-structured GitHub issue with a clear title and body.
Format: start with the title on the first line, then the body."""


async def generate_issue(data: PipelineData, client) -> PipelineData:
    messages_text = "\n".join(
        msg for msgs in data.context.values() for msg in msgs
    )
    user_prompt = f"Topic: {data.input}\n\nChannel messages:\n{messages_text}"

    response = await client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config={
            "system_instruction": SYSTEM_PROMPT,
            "max_output_tokens": 1024,
            "temperature": 0.3,
        },
    )

    new_context = dict(data.context)
    new_context["generated"] = [response.text]

    return PipelineData(context=new_context, input=response.text)
