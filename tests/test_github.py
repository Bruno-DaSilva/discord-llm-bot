from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.output.github import append_footer, create_issue


class TestCreateIssue:
    @pytest.mark.asyncio
    async def test_posts_to_correct_url(self):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "html_url": "https://github.com/owner/repo/issues/1"
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response

        url = await create_issue(
            client=mock_client,
            owner="owner",
            repo="repo",
            title="Bug title",
            body="Bug body",
            token="ghp_test123",
        )

        mock_client.post.assert_called_once_with(
            "https://api.github.com/repos/owner/repo/issues",
            json={"title": "Bug title", "body": "Bug body"},
            headers={
                "Authorization": "Bearer ghp_test123",
                "Accept": "application/vnd.github+json",
            },
        )
        assert url == "https://github.com/owner/repo/issues/1"

    @pytest.mark.asyncio
    async def test_raises_on_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            await create_issue(
                client=mock_client,
                owner="owner",
                repo="repo",
                title="t",
                body="b",
                token="tok",
            )


class TestAppendFooter:
    def test_adds_author(self):
        result = append_footer("Issue body", author="alice", message_link=None)
        assert "Author: alice" in result

    def test_adds_message_link(self):
        result = append_footer(
            "Issue body",
            author="alice",
            message_link="https://discord.com/channels/1/2/3",
        )
        assert "Discord: https://discord.com/channels/1/2/3" in result

    def test_omits_link_when_none(self):
        result = append_footer("Issue body", author="alice", message_link=None)
        assert "Discord:" not in result

    def test_separator_format(self):
        result = append_footer("Issue body", author="alice", message_link=None)
        assert "\n\n------\n" in result

    def test_preserves_original_body(self):
        result = append_footer("Original content here", author="bob", message_link=None)
        assert result.startswith("Original content here")
