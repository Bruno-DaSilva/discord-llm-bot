from unittest.mock import AsyncMock, patch

import discord
import pytest

from src.bot import create_bot, _read_required_env
from src.cogs.ui import DeleteView
from src.utils.sentry_tree import SentryCommandTree

from tests.conftest import TEST_PRIVATE_KEY_PEM


@pytest.fixture
def bot_kwargs(tmp_path):
    pem = tmp_path / "test.pem"
    pem.write_text(TEST_PRIVATE_KEY_PEM)
    return {
        "gemini_api_key": "key",
        "github_app_id": "12345",
        "github_private_key_path": str(pem),
        "github_installation_id": "67890",
    }


class TestReadRequiredEnv:
    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello")
        assert _read_required_env("TEST_VAR") == "hello"

    def test_exits_when_missing(self):
        with pytest.raises(
            SystemExit, match="Missing required environment variable: NONEXISTENT_VAR"
        ):
            _read_required_env("NONEXISTENT_VAR")

    def test_exits_when_empty(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "")
        with pytest.raises(
            SystemExit, match="Missing required environment variable: TEST_VAR"
        ):
            _read_required_env("TEST_VAR")


class TestCreateBot:
    def test_returns_bot_instance(self, bot_kwargs):
        bot = create_bot(**bot_kwargs)
        assert isinstance(bot, discord.ext.commands.Bot)

    def test_has_message_content_intent(self, bot_kwargs):
        bot = create_bot(**bot_kwargs)
        assert bot.intents.message_content is True

    def test_uses_sentry_command_tree(self, bot_kwargs):
        bot = create_bot(**bot_kwargs)
        assert isinstance(bot.tree, SentryCommandTree)

    @pytest.mark.asyncio
    async def test_setup_hook_loads_cog(self, bot_kwargs):
        bot = create_bot(**bot_kwargs)
        with (
            patch.object(bot, "add_cog", new_callable=AsyncMock) as mock_add,
            patch.object(bot, "add_view"),
            patch.object(bot, "add_dynamic_items"),
            patch.object(bot.tree, "sync", new_callable=AsyncMock),
        ):
            await bot.setup_hook()
            assert mock_add.await_count >= 1

    @pytest.mark.asyncio
    async def test_setup_hook_syncs_tree(self, bot_kwargs):
        bot = create_bot(**bot_kwargs)
        with (
            patch.object(bot, "add_cog", new_callable=AsyncMock),
            patch.object(bot, "add_view"),
            patch.object(bot, "add_dynamic_items"),
            patch.object(bot.tree, "sync", new_callable=AsyncMock) as mock_sync,
        ):
            await bot.setup_hook()
            mock_sync.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_setup_hook_registers_delete_view(self, bot_kwargs):
        bot = create_bot(**bot_kwargs)
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
    async def test_setup_hook_registers_dynamic_items(self, bot_kwargs):
        bot = create_bot(**bot_kwargs)
        with (
            patch.object(bot, "add_cog", new_callable=AsyncMock),
            patch.object(bot, "add_view"),
            patch.object(bot, "add_dynamic_items") as mock_add_dynamic,
            patch.object(bot.tree, "sync", new_callable=AsyncMock),
        ):
            await bot.setup_hook()
            mock_add_dynamic.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_hook_creates_http_client(self, bot_kwargs):
        bot = create_bot(**bot_kwargs)
        with (
            patch.object(bot, "add_cog", new_callable=AsyncMock),
            patch.object(bot, "add_view"),
            patch.object(bot, "add_dynamic_items"),
            patch.object(bot.tree, "sync", new_callable=AsyncMock),
        ):
            await bot.setup_hook()
            assert hasattr(bot, "http_client")
            assert hasattr(bot, "github_auth")
            assert hasattr(bot, "github")
