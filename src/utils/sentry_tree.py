from discord import Interaction
from discord.app_commands import CommandTree

from src.utils.tracing import get_trace_headers, start_trace


class SentryCommandTree(CommandTree):
    """CommandTree subclass that wraps every app command invocation in a Sentry transaction.

    After the transaction is started, the trace propagation headers (sentry-trace, baggage)
    are stored on ``interaction.extras["sentry_trace_headers"]`` so that downstream handlers
    (e.g. modals) can continue the same trace.
    """

    async def _call(self, interaction: Interaction) -> None:
        cmd_name = interaction.data.get("name", "unknown") if interaction.data else "unknown"
        username = getattr(interaction.user, "name", "unknown")
        async with start_trace(
            "discord.command",
            f"{username} {cmd_name}",
            data={"gen_ai.agent.name": cmd_name},
        ):
            interaction.extras["sentry_trace_headers"] = get_trace_headers()
            await super()._call(interaction)
