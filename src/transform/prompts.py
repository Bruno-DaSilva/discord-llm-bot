ISSUE_GENERATOR_PROMPT = """
<instructions>
You are to take the contextual information provided to create a ticket title and description for our jira-like ticketing system.

Focus on the topic provided in `ticket_focus`.

the `thread_contextual_messages` block is provided with all the messages in the thread for extra context. Ignore any unrelated tangents in the messages.

If a user provides a replay file for reproducing an issue, make sure to include the link.
</instructions>

<title_format>
A SHORT single sentence acting as a summary of the work to be completed in the ticket. No ending period.
</title_format>

<description_format>
The description is written in markdown, with three sections:

A 'Task' section, containing a short sentence or two that describe the work that needs to be completed and what it's intended to accomplish.

A `Context` section containing background information and, critically, the *why* of the change. Usually just a few paragraphs at most with external links to more detailed references.

An `Acceptance Criteria` section with a bullet pointed list of criteria that need to be met for the ticket to be considered complete.
</description_format>

<example>
Investigate desync safety of Lua userdata types in synced LuaRules

### Task

Investigate and document whether Lua userdata types can be safely used in synced LuaRules without causing desync, and identify which operations with userdata are safe versus which must be forbidden or guarded against.

### Context

Userdata types have historically been forbidden in synced LuaRules, presumably to prevent desync between players. Userdata enables cleaner, more ergonomic Lua APIs (e.g. object-oriented interfaces with metatables), and [PR #2343](https://github.com/beyond-all-reason/RecoilEngine/pull/2343) is introducing the first userdata type (`Image`) into the synced environment. Before wider adoption, the actual desync risks need to be concretely understood rather than assumed.

The engine already has some safeguards relevant to this area. The `SyncedNext` function in [`LuaHandleSynced.cpp`](https://github.com/beyond-all-reason/RecoilEngine/blob/82fb8cbcc9531e0d3e0b61532ae5c149bebb24b9/rts/Lua/LuaHandleSynced.cpp#L1940-L1985) whitelists key types allowed during iteration in synced context (`string`, `number`, `boolean`, `nil`, `thread`) and will log a warning if userdata keys are encountered. The `SYNCED` proxy table only copies basic types (numbers, strings, bools, tables) and explicitly excludes functions and metatables. `SendToUnsynced` similarly restricts argument types to `nil`, `boolean`, `number`, `string`, and `table`. However, none of these safeguards have been audited specifically for the case where userdata *values* (not keys) are present in tables or interact with Lua standard library functions.

Key risk areas include: nondeterministic ordering when userdata is used as a table key and then iterated or sorted; address-based string representations leaking via `tostring` or `string.format`; and more subtle vectors like GC finalizer ordering, weak table cleanup, metamethod dispatch, and cross-environment access patterns (`SYNCED.foo`, `Script.LuaUI.bar`, etc.).

### Acceptance Criteria

*   Deterministic ordering is tested: verify whether `table.sort` and `for ... in pairs` produce consistent results across clients when tables use userdata as keys.
*   String coercion is tested: confirm whether `tostring(userdata)` or `string.format("%s", userdata)` can produce nondeterministic, address-based output in synced context, and document whether this needs to be blocked or overridden.
*   GC-related behaviors are tested: investigate whether GC hooks, weak-key table cleanup ordering, and `__gc` metamethods on userdata can introduce nondeterminism.
*   Cross-environment interactions are tested: verify behavior of userdata when accessed via `SYNCED` proxy tables, passed through `SendToUnsynced`, or referenced through cross-env calls like `Script.LuaRules` / `Script.LuaUI`.
*   Findings are documented with clear recommendations on which userdata operations are safe in synced context and which must remain forbidden.
</example>


<ticket_focus>
{{ context.ticket_focus }}
</ticket_focus>

<thread_contextual_messages>
{{ context.messages }}
</thread_contextual_messages>
        """


def render_issue_prompt(
    focus: str, messages: str, *, amendments: list[str] = ()
) -> str:
    prompt = ISSUE_GENERATOR_PROMPT.replace(
        "{{ context.ticket_focus }}", focus
    ).replace("{{ context.messages }}", messages)

    if amendments:
        lines = "\n".join(f"- {a}" for a in amendments)
        prompt += f"\n<extra_instructions>\n{lines}\n</extra_instructions>\n"

    return prompt
