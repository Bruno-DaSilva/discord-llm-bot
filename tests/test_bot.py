from unittest.mock import AsyncMock, patch

import discord
import pytest

from src.bot import create_bot
from src.ui import CancelIssueButton, CreateIssueButton, DeleteView, RetryIssueButton

# Write a dummy PEM key to a temp file for tests
from tests.test_github_auth import TEST_PRIVATE_KEY_PEM

_BOT_KWARGS = {}


@pytest.fixture(autouse=True)
def _pem_file(tmp_path):
    pem = tmp_path / "test.pem"
    pem.write_text(TEST_PRIVATE_KEY_PEM)
    _BOT_KWARGS.update(
        gemini_api_key="key",
        github_app_id="12345",
        github_private_key_path=str(pem),
        github_installation_id="67890",
    )


def _create_bot():
    return create_bot(**_BOT_KWARGS)


class TestCreateBot:
    def test_returns_bot_instance(self):
        bot = _create_bot()
        assert isinstance(bot, discord.ext.commands.Bot)

    def test_has_message_content_intent(self):
        bot = _create_bot()
        assert bot.intents.message_content is True

    @pytest.mark.asyncio
    async def test_setup_hook_loads_cog(self):
        bot = _create_bot()
        with (
            patch.object(bot, "add_cog", new_callable=AsyncMock) as mock_add,
            patch.object(bot, "add_view"),
            patch.object(bot, "add_dynamic_items"),
            patch.object(bot.tree, "sync", new_callable=AsyncMock),
        ):
            await bot.setup_hook()
            assert mock_add.await_count == 2

    @pytest.mark.asyncio
    async def test_setup_hook_syncs_tree(self):
        bot = _create_bot()
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
        bot = _create_bot()
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
        bot = _create_bot()
        with (
            patch.object(bot, "add_cog", new_callable=AsyncMock),
            patch.object(bot, "add_view"),
            patch.object(bot, "add_dynamic_items") as mock_add_dynamic,
            patch.object(bot.tree, "sync", new_callable=AsyncMock),
        ):
            await bot.setup_hook()
            mock_add_dynamic.assert_called_once_with(
                CreateIssueButton, CancelIssueButton, RetryIssueButton
            )

    @pytest.mark.asyncio
    async def test_setup_hook_creates_http_client(self):
        bot = _create_bot()
        with (
            patch.object(bot, "add_cog", new_callable=AsyncMock),
            patch.object(bot, "add_view"),
            patch.object(bot, "add_dynamic_items"),
            patch.object(bot.tree, "sync", new_callable=AsyncMock),
        ):
            await bot.setup_hook()
            assert hasattr(bot, "http_client")
            assert hasattr(bot, "github_auth")
