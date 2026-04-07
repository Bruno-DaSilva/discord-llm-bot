# Contributing

## Adding a new command

Use `cogs/create_issue.py` as a reference implementation.

1. **Write a transform** (if your command needs LLM processing). Implement the `Transform` protocol from `transform/protocol.py`:

   ```python
   class MyTransform:
       async def run(self, data: PipelineData) -> PipelineData:
           # process data.input and data.context
           return PipelineData(input=result, context={...})
   ```

2. **Write a pipeline** in `pipeline/` that orchestrates the full workflow. See `pipeline/create_issue.py` for reference. The pipeline:
   - Builds `PipelineData`, runs transforms, calls outputs
   - Implements the `CommandHandler` protocol (`on_confirm`, `on_retry`, `on_output_retry`)
   - Has a `run()` method that handles loading states, previews, and error views
   - Pure functions for data construction and parsing where possible

3. **Write a Cog** that:
   - Registers the pipeline as the handler: `register_handler("my_cmd", pipeline)`
   - Defines slash commands / context menus
   - Defers interactions, fetches messages, and calls `pipeline.run()`
   - Cogs should contain no business logic

4. **Wire tracing** (if your command uses modals). Slash commands and context menus are automatically traced by `SentryCommandTree` -- no action needed. If your command opens a modal from a context menu:

   ```python
   from src.utils.tracing import propagate_trace_to_modal, traced_modal_submit

   # In the context menu handler:
   modal = MyModal(message, cog=self)
   propagate_trace_to_modal(modal, interaction, "my-command")
   await interaction.response.send_modal(modal)

   # On the modal class:
   @traced_modal_submit
   async def on_submit(self, interaction):
       ...
   ```

   The generic buttons (`ConfirmButton`, `RetryButton`, etc.) are already traced via `@traced_callback`. `cache_pipeline_data()` automatically stores trace headers so button clicks continue the same trace. Never import `sentry_sdk` directly -- use `src/utils/tracing.py`.

5. **Load the Cog** in `bot.py`'s `setup_hook()`.

The generic buttons (`ConfirmButton`, `RetryButton`, etc.) handle the rest -- they dispatch to your handler based on `cmd_type`.

## Chaining transforms

Each command writes its own orchestration function. There is no declarative pipeline runner. When chaining multiple transforms, reshape data explicitly between steps:

```python
async def on_retry(self, interaction, cached):
    summary = await self.summarizer.run(cached.pipeline_data)
    reshaped = PipelineData(
        input=cached.pipeline_data.input,
        context={"summary": [summary.input]},
    )
    return await self.generator.run(reshaped)
```

## TDD workflow

Tests come first. See `CLAUDE.md` for the full red-green-refactor cycle. Key points:

- Test files: `tests/test_<module>.py` matching each `src/<module>.py`
- Mock all external APIs (Discord, Gemini, GitHub) using `unittest.mock`
- Use `pytest-asyncio` for async tests
- Run: `.venv/bin/python -m pytest --cov=src`
- Target >80% line coverage

## Project conventions

- **Dependency injection**: No `os.environ` reads outside `bot.py`. Functions accept config/secrets as parameters.
- **Composition root**: `bot.py` reads env vars, creates clients, wires dependencies, loads Cogs.
- **One file per module**: Each file has focused exports. Pipelines go in `pipeline/`, transforms in `transform/`, outputs in `output/`, commands in `cogs/`.
- **No speculative abstractions**: Build for what you need now. Three similar lines of code is better than a premature abstraction.
