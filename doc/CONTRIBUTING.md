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

2. **Write a pipeline** in `pipeline/` that orchestrates business logic (no Discord imports). See `pipeline/create_issue.py` for reference:
   - Build `PipelineData`, run transforms, call outputs
   - Pure functions for data construction and parsing
   - Thin async wrappers for external calls

3. **Write a command handler** implementing three methods (delegates to pipeline for business logic):
   - `on_confirm(interaction, cached: CachedCommandData)` -- what happens when the user clicks Confirm
   - `on_retry(interaction, cached: CachedCommandData)` -- re-run transforms, return new result
   - `on_output_retry(interaction, cached: CachedOutputData)` -- retry a failed output action

4. **Write a Cog** that:
   - Registers the handler: `register_handler("my_cmd", handler)`
   - Defines slash commands / context menus
   - Handles Discord presentation (defer, loading embeds, preview views)
   - Delegates business logic to the pipeline

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
