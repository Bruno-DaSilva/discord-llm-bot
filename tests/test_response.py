from unittest.mock import AsyncMock

import discord
import pytest

from src.cogs.response import DmResponseTarget, ResponseTarget


class TestResponseTarget:
    @pytest.mark.asyncio
    async def test_send_preview_edits_loading_message(self):
        target = ResponseTarget()
        loading_msg = AsyncMock()
        embed = discord.Embed(description="preview")
        view = AsyncMock()

        await target.send_preview(loading_msg, embed, view)

        loading_msg.edit.assert_awaited_once_with(embed=embed, view=view)

    @pytest.mark.asyncio
    async def test_send_error_edits_loading_message(self):
        target = ResponseTarget()
        loading_msg = AsyncMock()
        embed = discord.Embed(description="error")
        view = AsyncMock()

        await target.send_error(loading_msg, embed, view)

        loading_msg.edit.assert_awaited_once_with(embed=embed, view=view)

    @pytest.mark.asyncio
    async def test_send_error_without_view(self):
        target = ResponseTarget()
        loading_msg = AsyncMock()
        embed = discord.Embed(description="error")

        await target.send_error(loading_msg, embed)

        loading_msg.edit.assert_awaited_once_with(embed=embed)

    def test_channel_id_is_none(self):
        target = ResponseTarget()
        assert target.channel_id is None


class TestDmResponseTarget:
    def test_channel_id_returns_origin(self):
        user = AsyncMock()
        target = DmResponseTarget(user, origin_channel_id=99999)
        assert target.channel_id == 99999

    @pytest.mark.asyncio
    async def test_send_preview_sends_to_dm_and_edits_stub(self):
        user = AsyncMock()
        target = DmResponseTarget(user, origin_channel_id=12345)
        loading_msg = AsyncMock()
        embed = discord.Embed(description="preview")
        view = AsyncMock()

        await target.send_preview(loading_msg, embed, view)

        user.send.assert_awaited_once_with(embed=embed, view=view)
        loading_msg.edit.assert_awaited_once()
        edit_kwargs = loading_msg.edit.call_args.kwargs
        assert "check your dms" in edit_kwargs["content"].lower()
        assert edit_kwargs["embed"] is None

    @pytest.mark.asyncio
    async def test_send_error_sends_to_dm_and_edits_stub(self):
        user = AsyncMock()
        target = DmResponseTarget(user, origin_channel_id=12345)
        loading_msg = AsyncMock()
        embed = discord.Embed(description="error")
        view = AsyncMock()

        await target.send_error(loading_msg, embed, view)

        user.send.assert_awaited_once_with(embed=embed, view=view)
        loading_msg.edit.assert_awaited_once()
        edit_kwargs = loading_msg.edit.call_args.kwargs
        assert "check your dms" in edit_kwargs["content"].lower()

    @pytest.mark.asyncio
    async def test_send_error_without_view(self):
        user = AsyncMock()
        target = DmResponseTarget(user, origin_channel_id=12345)
        loading_msg = AsyncMock()
        embed = discord.Embed(description="error")

        await target.send_error(loading_msg, embed)

        user.send.assert_awaited_once_with(embed=embed)

    @pytest.mark.asyncio
    async def test_send_preview_forbidden_falls_back(self):
        user = AsyncMock()
        user.send.side_effect = discord.Forbidden(
            AsyncMock(status=403), "Cannot send messages to this user"
        )
        target = DmResponseTarget(user, origin_channel_id=12345)
        loading_msg = AsyncMock()
        embed = discord.Embed(description="preview")
        view = AsyncMock()

        await target.send_preview(loading_msg, embed, view)

        loading_msg.edit.assert_awaited_once()
        edit_kwargs = loading_msg.edit.call_args.kwargs
        assert "dm" in edit_kwargs["content"].lower()
        assert edit_kwargs["embed"] is None

    @pytest.mark.asyncio
    async def test_send_error_forbidden_falls_back(self):
        user = AsyncMock()
        user.send.side_effect = discord.Forbidden(
            AsyncMock(status=403), "Cannot send messages to this user"
        )
        target = DmResponseTarget(user, origin_channel_id=12345)
        loading_msg = AsyncMock()
        embed = discord.Embed(description="error")

        await target.send_error(loading_msg, embed)

        loading_msg.edit.assert_awaited_once()
        edit_kwargs = loading_msg.edit.call_args.kwargs
        assert "dm" in edit_kwargs["content"].lower()
