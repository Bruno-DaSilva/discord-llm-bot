from unittest.mock import AsyncMock, patch

import discord
import pytest

from src.bot import create_bot
from src.ui import CancelIssueButton, CreateIssueButton, DeleteView


class TestCreateBot:
    def test_returns_bot_instance(self):
        bot = create_bot(gemini_api_key="key", github_token="tok")
        assert isinstance(bot, discord.ext.commands.Bot)

    def test_has_message_content_intent(self):
        bot = create_bot(gemini_api_key="key", github_token="tok")
        assert bot.intents.message_content is True

    @pytest.mark.asyncio
    async def test_setup_hook_loads_cog(self):
        bot = create_bot(gemini_api_key="key", github_token="tok")
        with (
            patch.object(bot, "add_cog", new_callable=AsyncMock) as mock_add,
            patch.object(bot, "add_view"),
            patch.object(bot, "add_dynamic_items"),
            patch.object(bot.tree, "sync", new_callable=AsyncMock),
        ):
            await bot.setup_hook()
            mock_add.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_setup_hook_syncs_tree(self):
        bot = create_bot(gemini_api_key="key", github_token="tok")
        with (
            patch.object(bot, "add_cog", new_callable=AsyncMock),
            patch.object(bot, "add_view"),
            patch.object(bot, "add_dynamic_items"),
            patch.object(bot.tree, "sync", new_callable=AsyncMock) as mock_sync,
        ):
            await bot.setup_hook()
            mock_sync.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_setup_hook_registers_delete_view(self):
        bot = create_bot(gemini_api_key="key", github_token="tok")
        with (
            patch.object(bot, "add_cog", new_callable=AsyncMock),
            patch.object(bot, "add_view") as mock_add_view,
            patch.object(bot, "add_dynamic_items"),
            patch.object(bot.tree, "sync", new_callable=AsyncMock),
        ):
            await bot.setup_hook()
            mock_add_view.assert_called_once()
            assert isinstance(mock_add_view.call_args.args[0], DeleteView)

    @pytest.mark.asyncio
    async def test_setup_hook_registers_dynamic_items(self):
        bot = create_bot(gemini_api_key="key", github_token="tok")
        with (
            patch.object(bot, "add_cog", new_callable=AsyncMock),
            patch.object(bot, "add_view"),
            patch.object(bot, "add_dynamic_items") as mock_add_dynamic,
            patch.object(bot.tree, "sync", new_callable=AsyncMock),
        ):
            await bot.setup_hook()
            mock_add_dynamic.assert_called_once_with(
                CreateIssueButton, CancelIssueButton
            )
