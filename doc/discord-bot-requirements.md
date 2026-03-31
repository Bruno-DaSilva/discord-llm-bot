# Discord Issue Bot — Requirements

## What It Does

Slash command `/create-issue repo=<owner/repo> N=<number of msgs> <topic>` → fetches last N channel messages (default 20) → sends to Gemini with issue template + examples → previews result with Create/Edit/Cancel buttons → creates GitHub issue on confirm.

## Stack

- **Python 3.12+ with discord.py** — long-running bot connected via WebSocket gateway, hosted in a Docker container
- **`google-genai`** — Gemini 2.5 Flash SDK (Python; NOT `google-generativeai`, which is deprecated)
- **`discord.py` ≥ 2.3** — bot framework with gateway connection, slash commands (`app_commands`), Views/Buttons
- **In-memory state** — store generated issue between slash command and button click using a dict with TTL (long-running process, no external store needed). Alternatively, carry state directly on `discord.ui.View` instances.
- **`httpx`** — async HTTP client for GitHub REST API
- **Docker** — containerized runtime

## Critical Constraints

**Deferral for long operations:** Use `await interaction.response.defer()` to send a "thinking…" indicator immediately. Do the real work (fetch messages, call Gemini), then call `await interaction.edit_original_response(content=...)` with the result. discord.py handles this natively — no manual HTTP calls needed.

**Gateway authentication:** discord.py authenticates via the bot token over WebSocket. No signature verification or PING/PONG handshake to implement — the library handles it.

**State between interactions:** The slash command and button click are separate events. Ideally, try and remain stateless - otherwise, `discord.ui.View` instances can carry state directly via instance attributes, which may eliminate the need for a separate store. Try to lean on this first.

**Privileged intents:** The bot needs the `MessageContent` privileged intent to read message content via `channel.history()`. This must be enabled in the Discord Developer Portal under Bot settings.

## Responding to Interactions

discord.py abstracts away raw interaction response types. The key methods:

- `interaction.response.defer()` — acknowledge with "thinking…" indicator
- `interaction.response.send_message(content)` — immediate reply
- `interaction.edit_original_response(content=...)` — update a deferred response
- `interaction.followup.send(content)` — send additional messages (valid 15 min)
- `discord.ui.View` + `discord.ui.Button` — interactive components for preview UI

## Gemini Setup

Get a free API key at https://aistudio.google.com/ (no credit card). Free tier: ~10 RPM / ~250–500 RPD for Flash.

```python
import os
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=user_prompt,
    config=genai.types.GenerateContentConfig(
        system_instruction=system_prompt,
        max_output_tokens=1024,
        temperature=0.3,
    ),
)
```

## Secrets (via environment variables)

Pass secrets via `--env-file .env` when running the Docker container. Keep `.env` in `.gitignore` and check in an `example.env` with placeholder values.

`DISCORD_BOT_TOKEN`, `DISCORD_APP_ID`, `GEMINI_API_KEY`, `GITHUB_TOKEN`

Note: `DISCORD_PUBLIC_KEY` is not needed — gateway bots authenticate with the bot token, not signature verification.

## Dependencies

```
discord.py>=2.3
google-genai>=1.0
httpx>=0.27
```

Do NOT use `py-cord` or `nextcord` (forks — stick with the canonical `discord.py`). Do NOT use `google-generativeai` (deprecated — use `google-genai`).

## Bot Permissions

`applications.commands` + `bot` with Send Messages, Read Message History, Use Slash Commands.

Additionally, enable the **Message Content** privileged intent in the Discord Developer Portal (Bot → Privileged Gateway Intents).

## Key Links

| | |
|---|---|
| discord.py docs | https://discordpy.readthedocs.io/en/stable/ |
| discord.py app_commands | https://discordpy.readthedocs.io/en/stable/interactions/api.html |
| discord.py examples | https://github.com/Rapptz/discord.py/tree/master/examples |
| `google-genai` Python SDK | https://pypi.org/project/google-genai/ |
| Gemini pricing/free tier | https://ai.google.dev/gemini-api/docs/pricing |
| Discord Developer Portal | https://discord.com/developers/applications |
| GitHub Create Issue API | https://docs.github.com/en/rest/issues/issues#create-an-issue |

## Docker

Build and run locally:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

```bash
docker build -t discord-issue-bot .
docker run --env-file .env discord-issue-bot
```

No ports need to be exposed — the bot connects outbound to Discord's WebSocket gateway.
