from unittest.mock import AsyncMock

import discord
import pytest

from src.ui import DeleteButton, DeleteView


class TestDeleteButton:
    def test_button_has_trash_emoji(self):
        button = DeleteButton()
        assert str(button.emoji) == "\N{WASTEBASKET}"

    def test_button_style_is_grey(self):
        button = DeleteButton()
        assert button.style == discord.ButtonStyle.grey

    def test_button_has_no_text_label(self):
        button = DeleteButton()
        assert button.label is None

    @pytest.mark.asyncio
    async def test_callback_deletes_message(self):
        button = DeleteButton()
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.message = AsyncMock()

        await button.callback(interaction)

        interaction.response.defer.assert_awaited_once()
        interaction.message.delete.assert_awaited_once()


class TestDeleteView:
    def test_view_contains_one_child(self):
        view = DeleteView()
        assert len(view.children) == 1

    def test_view_child_is_delete_button(self):
        view = DeleteView()
        assert isinstance(view.children[0], DeleteButton)

    def test_view_has_no_timeout(self):
        view = DeleteView()
        assert view.timeout is None
