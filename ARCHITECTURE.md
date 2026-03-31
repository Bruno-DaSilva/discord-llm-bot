# Architecture

This project uses a pipeline architecture with three layers that compose like lego pieces. Each layer has a clear responsibility, a standard interface, and can be swapped or extended independently.

## Layers

```
Command (parse + orchestrate)
  → Transform (domain logic, in → out)
  → Transform (domain logic, in → out)
    → Output (deliver to external system)
    → Output (deliver to external system)
```

### Command layer

Entry points that receive interactions, parse options, and orchestrate the pipeline. Implemented as discord.py Cogs using `@app_commands.command()`.

Responsibilities:
- Defer long-running interactions (`interaction.response.defer()`)
- Extract options via app_commands parameter injection
- Build the initial `PipelineData`
- Wire transforms and outputs together

Modules: `bot.py` (entry point, Cog loading), `cogs/create_issue.py`

### Transform layer

Domain logic that turns inputs into outputs. Each transform receives a `PipelineData` and returns a new `PipelineData`. Transforms chain naturally -- the output of one is the input of the next.

Transforms may perform I/O (e.g., calling an LLM). The defining trait is not purity but purpose: a transform's job is to shape data, not to deliver it somewhere.

Because every transform shares the same `PipelineData` in/out contract, they chain naturally. A pipeline can run one transform or many in sequence -- each receives the previous transform's output as its input.

Modules: `transform/gemini.py`

### Output layer

Modules that deliver results to external systems. Each output handles one external API, receives its own domain-specific arguments, and returns nothing. Outputs are independent -- adding a new one (e.g., post to Slack) doesn't touch transform logic.

Modules: `output/github.py`, `output/discord.py`, `output/stdout.py`

## PipelineData contract

Every transform receives and returns the same shape:

```python
@dataclass
class PipelineData:
    context: dict[list[str]]
    input: str
```

- **context** -- accumulated context strings keyed by type (e.g., channel messages, prior transform results).
- **input** -- the current focal input (e.g., topic, generated issue body)

This standard interface is what makes transforms composable. The command layer builds the initial `PipelineData`, pipes it through one or more transforms, then extracts the final result to pass domain-specific arguments to each output.

Outputs do not use `PipelineData` -- they receive their own specific arguments (e.g., `owner, repo, title, body, token` for GitHub).

## Pipeline example: create-issue

```
1. Command (Cog): parse /create-issue options from interaction
   → build PipelineData { context: [channel messages], input: topic }

2. Transform (gemini): PipelineData in → PipelineData out
   → builds prompt from context + input, calls LLM
   → returns PipelineData { context: [..., generated issue], input: issue body }

3. Output (github): create_issue(owner, repo, title, body, token)
   Output (discord): interaction.edit_original_response(...)
```

Transforms chain. A more complex pipeline might look like:

```
Command → Transform A → Transform B → Transform C → Outputs
```

Transforms can also orchestrate other transforms, as a way to package more complex sub-workflows into reusable parts:
```
Command → Transform A(Transform B → logic → Transform C) → Transform D → Outputs
```

Each transform receives the previous one's `PipelineData` and returns a new one. The command layer controls the chain order.

Swapping the LLM (Gemini → Claude) means replacing one transform. Adding a new output (e.g., log to analytics) means adding one module. Inserting a new transform (e.g., summarize messages before the LLM call) means adding it to the chain. None of these changes touch the other layers.

## Module rules

- Each module is a single file with focused exports
- Functions accept explicit config/secrets as parameters (dependency injection) - they do not directly read from `os.environ`. Also no module-level global state.
- Transforms must accept and return `PipelineData`
- Output modules handle one external API each
- Command layer (Cogs) handles orchestration
