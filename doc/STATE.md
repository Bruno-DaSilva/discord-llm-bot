# State Between Interactions

## Why state is needed

The retry button needs the same `PipelineData` (channel messages + topic) that the original `/create-issue` command collected. Discord creates a **new `Interaction` object** for every button click — there is no built-in way to carry data from the original command interaction to the retry interaction.

## Discord state options considered

| Mechanism | Persists across restarts? | Hidden from users? | Capacity |
|---|---|---|---|
| `button.custom_id` | Yes | Yes | 100 chars |
| `Interaction.extras` | No (single interaction only) | Yes | Unlimited |
| Embed fields / footer | Yes | No | ~25k chars |
| Message content | Yes | No | 2000 chars |

**`button.custom_id`** — The only data that survives from one interaction to the next is what's encoded in the button's `custom_id`. At 100 characters, this is too small to hold channel message history. It currently stores `retry_issue:{owner}/{repo}/{cache_key}`.

**`Interaction.extras`** — A free-use dict on each `Interaction`, but it only lives for the duration of that single interaction callback. When the user clicks retry, a completely new `Interaction` is constructed — the original's `extras` are gone. This is the same whether the bot uses the gateway (websocket) or HTTP webhooks; Discord simply doesn't persist arbitrary bot-side state.

**Embed fields / message content** — These persist on the message, but are visible to users and have size constraints. Not suitable for storing raw pipeline data.

## Current approach: in-memory cache

We cache `PipelineData` in a process-level dict (`_retry_cache` in `src/ui.py`), keyed by a short UUID stored in the button's `custom_id`.

**Why this approach:**
- Simple — no external dependencies, no database to host
- Sufficient for a single-process bot
- Fast lookups

**Tradeoff:** Data is lost on bot restart. Users see "Session expired. Please run the command again." This is acceptable given our deployment model (single long-running container).

## Future: GitHub OAuth

Currently the plan is to create issues using a single bot token and attribute the author by name in the issue description. A better approach would be GitHub OAuth so the bot acts **on behalf of the user** — issues appear under their GitHub account. This would require persisting OAuth tokens per Discord user, which strengthens the case for a real data store (SQLite, Redis, etc.) over the in-memory cache.
