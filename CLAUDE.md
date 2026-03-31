# Discord Issue Bot

TODO short description

## TDD Workflow (MANDATORY)

1. **Write the failing test first** -- every new function or behavior starts with a test
2. **Run tests** to confirm the test fails (red)
3. **Write the minimum code** to make the test pass (green)
4. **Refactor** while keeping tests green
5. **Never push code without passing tests**

## Commands

- TODO


## Architecture

See `doc/ARCHITECTURE.md` for the full pipeline architecture (three layers: Command → Transform → Output) and the `PipelineData` contract.

## Testing
- TODO

## Key Constraints

- **3-second rule**: Slash commands must return type 5 (DEFERRED) immediately; do real work in `ctx.waitUntil()`
- TODO

## Secrets
- TODO

