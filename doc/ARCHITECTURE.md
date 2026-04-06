# Architecture

This project uses a pipeline architecture with three layers that _mostly_ compose like lego pieces. Each layer has a clear responsibility, a standard interface, and can be swapped or extended independently.

The main goal of this architecture is to make it easy to add new entrypoints (new slash commands, non-discord calls) or swap out implementations (eg. LLM providers) as easily as possible.

## Layers

```
Command (parse + present)
  → Pipeline (orchestrate business logic)
    → Transform (domain logic, in → out)
    → Transform (domain logic, in → out)
      → Output (deliver to external system)
      → Output (deliver to external system)
```

### Command layer

Thin Discord interaction wrappers. Implemented as discord.py Cogs using `@app_commands.command()` and context menus.

Responsibilities:
- Register the pipeline as the `CommandHandler` for button dispatch
- Defer long-running interactions (`interaction.response.defer()`)
- Extract options via app_commands parameter injection (slash commands) or modals (context menus)
- Fetch channel messages
- Hand off to `pipeline.run()` for all orchestration
- Catch top-level errors and send error embeds

Cogs contain no business logic -- they defer, fetch messages, and call the pipeline.

Modules: `bot.py` (composition root), `cogs/create_issue.py`, `cogs/engine_issue.py`, `cogs/registry.py`

### Pipeline layer

Service classes that own the full workflow: data construction, repo validation, transform execution, preview display, confirmation handling, and GitHub output. Each pipeline implements the `CommandHandler` protocol so UI buttons dispatch directly to it.

Pipelines are shared across commands -- `create-issue` and `engine-issue` both use the same `IssuePipeline` instance. Cogs register the pipeline as their handler at init.

Modules: `pipeline/create_issue.py`

### Transform layer

Domain logic that turns inputs into outputs. Each transform receives a `PipelineData` and returns a new `PipelineData`. Transforms chain naturally -- the output of one is the input of the next.

Transforms may perform I/O (e.g., calling an LLM). The defining trait is purpose: a transform's job is to shape data, not to deliver it somewhere.

Because every transform shares the same `PipelineData` in/out contract, they chain naturally. A pipeline can run one transform or many in sequence -- each receives the previous transform's output as its input. When chaining transforms, the command layer handles any data reshaping between steps.

Modules: `transform/gemini.py`, `transform/protocol.py`, `transform/prompts.py`

### Output layer

Modules that deliver results to external systems. Each output handles one external API, receives its own domain-specific arguments, and returns nothing. Outputs are independent -- adding a new one doesn't touch transform logic.

Modules: `output/github.py`, `output/github_auth.py`, `output/github_client.py`, `output/discord.py`

## PipelineData contract

Every transform receives and returns the same shape:

```python
@dataclass
class PipelineData:
    context: dict[str, list[str]]
    input: str
```

- **context** -- accumulated context strings keyed by type (e.g., channel messages, prior transform results).
- **input** -- the current focal input (e.g., focus, generated issue body)

This standard interface is what makes transforms composable. The command layer builds the initial `PipelineData`, pipes it through one or more transforms, then extracts the final result to pass domain-specific arguments to each output.

Outputs do not use `PipelineData` -- they receive their own specific arguments (e.g., `owner, repo, title, body` for GitHub).

### PipelineData Limitation/Concession 
Unfortunately, the PipelineData contract is not quite as much of a panacea as I originally hoped when attacking this problem. This is because transforms, by nature, should not know about each other - yet must infer the right fields to pull from the PipelineData context. For example, a ticket generating LLM step could get context.messages to directly read channel messages, or could get context.summary to read the summarization from a prior transform step.

So, for now, whatever is wiring the transforms together is doing data reshaping; eg. putting context.summary into context.messages so the transform step pulls the summary. That's pretty nasty though, because that means the parent needs to know the underlying implementation of the transforms to know what fields to reshape to.

One idea is just to scrap the pipelinedata all together and use proper function signatures per-transform - this would at least solve the "implementation-hiding" problem. But this is undecided, there may be a better way to handle wiring transforms together. Maybe picking a better PipelineData struct shape (ie. not input/context) may solve this.

## Command handler registry

The UI layer needs to dispatch button clicks (confirm, retry, cancel) to the right command's logic. This is handled by a handler registry in `cogs/registry.py`.

Each command type defines a `CommandHandler` with three methods:
- **`on_confirm`** -- called when the user clicks Confirm (e.g., create the GitHub issue)
- **`on_retry`** -- called when the user clicks Retry (e.g., re-run the LLM transform)
- **`on_output_retry`** -- called when the user clicks Retry after an output failure (e.g., retry the GitHub API call)

Cancel has no handler callback -- `CancelButton` edits the message to "Cancelled.", removes the view, and lets the cache entry expire via TTL. 

Cogs register their handler at init via `register_handler("issue", handler)`. Buttons encode the `cmd_type` in their `custom_id` and look up the handler at click time. This means adding a new command type (e.g., "summarize") only requires writing a new handler and registering it -- the buttons and views are fully generic.b

## UI layer

Interactive components for the preview → confirm/retry/cancel flow. Defined in `ui.py`.

**Buttons** -- four generic `DynamicItem` classes (`ConfirmButton`, `RetryButton`, `CancelButton`, `OutputRetryButton`) that survive bot restarts via `custom_id` encoding. Format: `{action}:{cmd_type}:{cache_key}`. Each button dispatches to the registered handler for its `cmd_type`.

**Views** -- `PreviewView` (confirm + cancel + retry), `ErrorView` (retry + cancel after transform failure), `OutputErrorView` (retry + cancel after output failure). All parameterized by `cmd_type`.

**Cache** -- in-memory dict (`_retry_cache`) with 24-hour TTL, keyed by short UUIDs stored in button `custom_id`s. Stores `CachedCommandData` (for transform retries) and `CachedOutputData` (for output retries). See `doc/STATE.md` for design rationale.

## Pipeline example: create-issue

```
1. Command (Cog): parse /create-issue options, defer interaction, fetch messages

2. Pipeline (IssuePipeline): build_pipeline_data(), check_repo(), generate()
   → Transform (gemini): PipelineData in → PipelineData out
   → builds prompt from context + input, calls LLM
   → returns PipelineData { context: {..., generated: [...]}, input: issue body }

3. Command (Cog): show preview embed with Confirm / Cancel / Retry buttons
   → cache PipelineData for potential retry

4. User clicks Confirm → handler.on_confirm():
   → Pipeline: parse_preview(), build_issue_body(), create_issue()
   → Output (github): create_issue(owner, repo, title, body)
   → Output (discord): post new message with issue URL
```

Both `/create-issue` and `/engine-issue` share the same `IssuePipeline` instance. The only difference is where the repo comes from (user parameter vs. hardcoded constant).

## Module rules

- Each module is a single file with focused exports
- Functions accept explicit config/secrets as parameters (dependency injection) - they do not directly read from `os.environ`. Also no module-level global state.
- Transforms must accept and return `PipelineData`
- Output modules handle one external API each
- Command layer (Cogs) handles orchestration
