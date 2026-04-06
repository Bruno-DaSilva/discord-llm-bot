# State Between Interactions

## Why state is needed

Retry and confirm buttons need data from the original command (e.g., `PipelineData` with channel messages + focus, or the extracted title/body for a GitHub retry). Discord creates a **new `Interaction` object** for every button click -- there is no built-in way to carry data from the original command interaction to the button interaction.

## Options considered

**`Interaction.extras`** -- A free-use dict on each `Interaction`, but it only lives for the duration of that single interaction callback. When the user clicks a button, a completely new `Interaction` is constructed -- the original's `extras` are gone. So this is not suitable for us.

**K/V database** (Redis, Postgres, etc.) -- Ideal solution -- purpose-built for this exact use case. However, the bot is hosted on a single OVH VM and we prefer to stay stateless with no external dependencies for now.

**Local SQLite DB** -- Could work if we guarantee a single replica and the same OVH VM disk is always reused across deployments, so we can just mount the sqlite db into the container on every restart. Neither constraint is currently in place, so data durability isn't assured.

**`button.custom_id`** -- The only data that survives from one interaction to the next is what's encoded in the button's `custom_id`. At 100 characters, this is too small to hold channel message history. In combination with the next option, it stores `{action}:{cmd_type}:{cache_key}` -- e.g., `confirm:issue:a1b2c3d4` or `retry:issue:a1b2c3d4`.

**In-memory cache** -- Process-level dict keyed by a short UUID stored in the button's `custom_id`. Simple, no external dependencies, fast lookups. Data is lost on bot restart, but acceptable for a single long-running container. **This is the current approach** (see below).

## Current approach: in-memory cache

We cache data in a process-level dict (`_retry_cache` in `src/ui.py`), keyed by a short UUID stored in the button's `custom_id`.

Two generic cache types support any command:

- **`CachedCommandData`** -- stores `cmd_type`, `pipeline_data` (for transform retries), and `extra` (command-specific metadata like author name, repo owner). Used by `RetryButton` and `ConfirmButton`.
- **`CachedOutputData`** -- stores `cmd_type` and `payload` (e.g., extracted title/body for a GitHub API retry). Used by `OutputRetryButton`.

The `cmd_type` field routes button clicks to the correct `CommandHandler` via the registry in `cogs/registry.py`. This means the cache infrastructure is shared across all command types -- adding a new command doesn't require changes to the caching layer.

**Why this approach:**
- Simple -- no external dependencies, no database to host
- Sufficient for a single-process bot
- Fast lookups
- Generic -- works for any command type

**Tradeoff:** Data is lost on bot restart. Users see "Session expired. Please run the command again." This is acceptable given our deployment model (single long-running container). Entries auto-expire after 24 hours.

## Future uses of storage

### GitHub OAuth

Currently the plan is to create issues using a GitHub App and attribute the author by name in the issue description. A better approach would be GitHub OAuth so the bot acts **on behalf of the user** -- issues appear under their GitHub account. This would require persisting OAuth tokens per Discord user, which strengthens the case for a real data store (SQLite, Redis, etc.) over the in-memory cache.

### Per-channel configuration

Right now command parameters like target repo are provided on every invocation. A persistent store would allow guild admins to set per-channel defaults (e.g., default repo, prompt amendments) via a slash command, so users don't have to specify them each time.

### Permissions

Commands are currently open to anyone who can see the channel, and rely on discord admins to lock them down to specific users or roles. A persistent store would allow configuring permissions per channel -- e.g., restricting commands for engine repo to specific users -- managed via slash commands rather than hardcoded checks.
