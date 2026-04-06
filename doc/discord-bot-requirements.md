# Discord Issue Bot -- Requirements

## What It Does

LLM-powered Discord bot that generates GitHub issues from channel conversations. Entry points:

- **Slash commands**: `/create-issue` (any repo) and `/engine-issue` (hardcoded to RecoilEngine)
- **Context menus**: right-click a message → "Create Issue" or "Engine Issue" → modal for focus/options

Flow: fetch recent channel messages → LLM transform (Gemini) → preview embed with Confirm/Cancel/Retry buttons → create GitHub issue on confirm. Users can retry the LLM generation or the GitHub API call independently if either fails.

## Stack

- **Python 3.12+** with **discord.py** -- long-running bot via WebSocket gateway, hosted in Docker
- **`google-genai`** -- Gemini SDK (model: `gemini-3-flash-preview`)
- **`httpx`** -- async HTTP client for GitHub REST API
- **`cryptography`** -- JWT signing for GitHub App authentication
- **In-memory cache** -- process-level dict with 24hr TTL for retry state between interactions (see `doc/STATE.md`). Later versions can use some sort k/v DB store.

## Critical Constraints

- **Deferral**: Long operations (message fetch + LLM call) must `defer()` first, then `edit_original_response()` or `followup.send()`. This is because discord requires an ack within 3s.
- **GitHub App auth**: Bot authenticates as a GitHub App using JWT → installation access token flow. Tokens are cached for 55 minutes. Repo installation is verified before attempting issue creation, or else issue creation would work against any public repo.
- **Retry state**: Button clicks create new Discord interactions with no shared state. Pipeline data is cached in-memory keyed by a UUID stored in the button's `custom_id`. Lost on restart (acceptable for single-process deployment for now until we get a real k/v DB store).
- **MessageContent intent**: Must be enabled in Discord Developer Portal for `channel.history()` to return message content.

## Secrets

Via environment variables (`--env-file .env` in Docker):

| Variable | Required | Description |
|---|---|---|
| `DISCORD_BOT_TOKEN` | Yes | Bot authentication token |
| `DISCORD_APP_ID` | Yes | Discord application ID |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `GITHUB_APP_ID` | Yes | GitHub App ID |
| `GITHUB_APP_PRIVATE_KEY_PATH` | Yes | Path to GitHub App private key PEM file |
| `GITHUB_APP_INSTALLATION_ID` | Yes | GitHub App installation ID |

## Dependencies

```
discord.py>=2.3
google-genai>=1.0
httpx>=0.27
cryptography
```

Do NOT use `py-cord` or `nextcord` (forks -- stick with canonical `discord.py`). Do NOT use `google-generativeai` (deprecated -- use `google-genai`).

## Bot Permissions

`applications.commands` + `bot` with Send Messages, Read Message History.

Enable the **Message Content** privileged intent in the Discord Developer Portal (Bot → Privileged Gateway Intents).

## Key Links

| | |
|---|---|
| discord.py docs | https://discordpy.readthedocs.io/en/stable/ |
| discord.py app_commands | https://discordpy.readthedocs.io/en/stable/interactions/api.html |
| `google-genai` Python SDK | https://pypi.org/project/google-genai/ |
| GitHub Create Issue API | https://docs.github.com/en/rest/issues/issues#create-an-issue |
