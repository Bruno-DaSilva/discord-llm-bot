import re
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.ui import (
    CancelIssueButton,
    CreateIssueButton,
    DeleteButton,
    DeleteView,
)


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

    def test_button_has_persistent_custom_id(self):
        button = DeleteButton()
        assert button.custom_id == "delete_issue_msg"

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

    def test_view_is_persistent(self):
        view = DeleteView()
        assert view.is_persistent()


class TestCreateIssueButton:
    def test_custom_id_encodes_owner_and_repo(self):
        btn = CreateIssueButton(owner="myorg", repo="myrepo")
        assert btn.custom_id == "create_issue:myorg/myrepo"

    def test_button_label_is_create(self):
        btn = CreateIssueButton(owner="o", repo="r")
        assert btn.item.label == "Create"

    def test_button_style_is_green(self):
        btn = CreateIssueButton(owner="o", repo="r")
        assert btn.item.style == discord.ButtonStyle.green

    @pytest.mark.asyncio
    async def test_from_custom_id_extracts_owner_repo(self):
        match = re.match(
            r"create_issue:(?P<owner>[^/]+)/(?P<repo>.+)",
            "create_issue:myorg/myrepo",
        )
        interaction = AsyncMock()
        item = MagicMock()
        btn = await CreateIssueButton.from_custom_id(interaction, item, match)
        assert btn.owner == "myorg"
        assert btn.repo == "myrepo"

    @pytest.mark.asyncio
    async def test_callback_creates_issue_and_sends_delete_view(self):
        btn = CreateIssueButton(owner="o", repo="r")
        interaction = AsyncMock()
        interaction.message = MagicMock()
        interaction.message.content = "# Title\nBody text"
        interaction.client = MagicMock()
        interaction.client.github_token = "ghp_test"
        interaction.response = AsyncMock()

        await btn.callback(interaction)

        interaction.response.edit_message.assert_awaited_once()
        edit_kwargs = interaction.response.edit_message.call_args.kwargs
        assert edit_kwargs["view"] is None
        assert "https://github.com/o/r/issues" in edit_kwargs["content"]

        interaction.followup.send.assert_awaited_once()
        followup_kwargs = interaction.followup.send.call_args.kwargs
        assert isinstance(followup_kwargs["view"], DeleteView)
        assert followup_kwargs["ephemeral"] is False


class TestCancelIssueButton:
    def test_custom_id_encodes_owner_and_repo(self):
        btn = CancelIssueButton(owner="myorg", repo="myrepo")
        assert btn.custom_id == "cancel_issue:myorg/myrepo"

    def test_button_label_is_cancel(self):
        btn = CancelIssueButton(owner="o", repo="r")
        assert btn.item.label == "Cancel"

    def test_button_style_is_red(self):
        btn = CancelIssueButton(owner="o", repo="r")
        assert btn.item.style == discord.ButtonStyle.red

    @pytest.mark.asyncio
    async def test_from_custom_id_extracts_owner_repo(self):
        match = re.match(
            r"cancel_issue:(?P<owner>[^/]+)/(?P<repo>.+)",
            "cancel_issue:myorg/myrepo",
        )
        interaction = AsyncMock()
        item = MagicMock()
        btn = await CancelIssueButton.from_custom_id(interaction, item, match)
        assert btn.owner == "myorg"
        assert btn.repo == "myrepo"

    @pytest.mark.asyncio
    async def test_callback_cancels_and_removes_view(self):
        btn = CancelIssueButton(owner="o", repo="r")
        interaction = AsyncMock()
        interaction.response = AsyncMock()

        await btn.callback(interaction)

        call_kwargs = interaction.response.edit_message.call_args.kwargs
        assert call_kwargs["view"] is None
        assert "cancelled" in call_kwargs["content"].lower()
