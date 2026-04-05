# Discord Issue Bot

Discord bot providing slash commands and context menus to generate GitHub issues from channel messages using Gemini AI. Built with discord.py, hosted in Docker.

## Directory Structure

```
src/                — application source
  bot.py            — composition root (entry point, env reads)
  models.py         — shared data models (PipelineData, cached types)
  ui.py             — generic buttons, views, and retry cache
  logging_config.py — logging setup
  cogs/             — slash commands, context menus, and handler registry
  pipeline/         — pipeline orchestrators (business logic, no Discord imports)
  transform/        — pipeline transform layer (LLM calls, data modifications)
  output/           — pipeline output layer (GitHub, Discord)
tests/              — mirrors src/ as test_<module>.py
doc/                — architecture, requirements, and design docs
```

## TDD Workflow (MANDATORY)

1. **Write the failing test first** -- every new function or behavior starts with a test
2. **Run tests** to confirm the test fails (red)
3. **Write the minimum code** to make the test pass (green)
4. **Refactor** while keeping tests green
5. **Never push code without passing tests**

## Commands

- `uv sync` -- install all dependencies (main + dev group)
- `uv run pytest` -- run tests
- `uv run pytest --cov=src` -- run tests with coverage
- `uv run ruff check src/ tests/` -- lint
- `uv run ruff format src/ tests/` -- auto-format

## Architecture

See `doc/ARCHITECTURE.md` for the full pipeline architecture (Command -> Transform -> Output), the `PipelineData` contract, and the command handler registry. See `doc/CONTRIBUTING.md` for how to add new commands and transforms.

## Testing

- Test files live in `tests/test_<module>.py` matching each `src/<module>.py`
- Use `unittest.mock` / `pytest` fixtures for external API calls (Discord, Gemini, GitHub)
- `pytest-asyncio` for async test functions
- Target >80% line coverage

## Key Constraints

- **Deferral**: Use `interaction.response.defer()` for long-running commands, then `interaction.edit_original_response()` with the result
- **Dependency injection**: Functions accept config/secrets as parameters -- no `os.environ` reads except in `bot.py` (composition root)
- **In-memory cache**: State between interactions (retry data, pipeline data) is stored in a process-level cache with 24hr TTL. See `doc/STATE.md`.
- **Privileged intents**: `MessageContent` intent must be enabled in Discord Developer Portal

## Secrets (via environment variables)

`DISCORD_BOT_TOKEN`, `DISCORD_APP_ID`, `GEMINI_API_KEY`, `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY_PATH`, `GITHUB_APP_INSTALLATION_ID`

See `example.env` for template. Pass via `--env-file .env` when running Docker.
