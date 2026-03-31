# Discord Issue Bot

Discord bot providing `/create-issue` slash command to generate GitHub issues from channel messages using Gemini AI. Built with discord.py, hosted in Docker.

## TDD Workflow (MANDATORY)

1. **Write the failing test first** -- every new function or behavior starts with a test
2. **Run tests** to confirm the test fails (red)
3. **Write the minimum code** to make the test pass (green)
4. **Refactor** while keeping tests green
5. **Never push code without passing tests**

## Commands

- `pip install -r requirements.txt -r requirements-dev.txt` -- install all dependencies
- `.venv/bin/python -m pytest` -- run tests
- `.venv/bin/python -m pytest --cov=src` -- run tests with coverage
- `.venv/bin/ruff check src/ tests/` -- lint
- `.venv/bin/ruff format src/ tests/` -- auto-format

## Architecture

See `doc/ARCHITECTURE.md` for the full pipeline architecture (three layers: Command -> Transform -> Output) and the `PipelineData` contract.

## Testing

- Test files live in `tests/test_<module>.py` matching each `src/<module>.py`
- Use `unittest.mock` / `pytest` fixtures for external API calls (Discord, Gemini, GitHub)
- `pytest-asyncio` for async test functions
- Target >80% line coverage

## Key Constraints

- **Deferral**: Use `interaction.response.defer()` for long-running commands, then `interaction.edit_original_response()` with the result
- **Dependency injection**: Functions accept config/secrets as parameters -- no `os.environ` reads except in `bot.py` (composition root)
- **Stateless**: Lean on `discord.ui.View` instance attributes for state between interactions
- **Privileged intents**: `MessageContent` intent must be enabled in Discord Developer Portal

## Secrets (via environment variables)

`DISCORD_BOT_TOKEN`, `DISCORD_APP_ID`, `GEMINI_API_KEY`, `GITHUB_TOKEN`

See `example.env` for template. Pass via `--env-file .env` when running Docker.
