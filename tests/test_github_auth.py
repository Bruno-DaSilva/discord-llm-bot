import time
from unittest.mock import AsyncMock, MagicMock

import httpx
import jwt
import pytest

from src.output.github_auth import GitHubAppAuth, _build_jwt

from tests.conftest import TEST_PRIVATE_KEY_PEM, test_private_key as _private_key


class TestBuildJwt:
    def test_contains_required_claims(self):
        token = _build_jwt(app_id="12345", private_key_pem=TEST_PRIVATE_KEY_PEM)
        payload = jwt.decode(token, _private_key.public_key(), algorithms=["RS256"])
        assert payload["iss"] == "12345"
        assert "iat" in payload
        assert "exp" in payload

    def test_exp_is_10_minutes_after_iat(self):
        token = _build_jwt(app_id="12345", private_key_pem=TEST_PRIVATE_KEY_PEM)
        payload = jwt.decode(token, _private_key.public_key(), algorithms=["RS256"])
        assert payload["exp"] - payload["iat"] == 600

    def test_uses_rs256(self):
        token = _build_jwt(app_id="12345", private_key_pem=TEST_PRIVATE_KEY_PEM)
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "RS256"


class TestGitHubAppAuth:
    def _make_auth(self, client=None):
        if client is None:
            client = AsyncMock(spec=httpx.AsyncClient)
        return GitHubAppAuth(
            app_id="12345",
            private_key_pem=TEST_PRIVATE_KEY_PEM,
            installation_id="67890",
            client=client,
        )

    def _mock_client_with_token(self, token="ghs_abc123", expires_at="2099-01-01T00:00:00Z"):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "token": token,
            "expires_at": expires_at,
        }
        mock_response.raise_for_status = MagicMock()
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = mock_response
        return client

    @pytest.mark.asyncio
    async def test_posts_to_correct_url(self):
        client = self._mock_client_with_token()
        auth = self._make_auth(client)

        await auth.get_token()

        call_args = client.post.call_args
        assert call_args.args[0] == "https://api.github.com/app/installations/67890/access_tokens"

    @pytest.mark.asyncio
    async def test_sends_jwt_bearer_header(self):
        client = self._mock_client_with_token()
        auth = self._make_auth(client)

        await auth.get_token()

        headers = client.post.call_args.kwargs["headers"]
        assert headers["Authorization"].startswith("Bearer ")
        assert headers["Accept"] == "application/vnd.github+json"

    @pytest.mark.asyncio
    async def test_returns_token_string(self):
        client = self._mock_client_with_token(token="ghs_realtoken")
        auth = self._make_auth(client)

        token = await auth.get_token()
        assert token == "ghs_realtoken"

    @pytest.mark.asyncio
    async def test_caches_token(self):
        client = self._mock_client_with_token()
        auth = self._make_auth(client)

        await auth.get_token()
        await auth.get_token()

        assert client.post.await_count == 1

    @pytest.mark.asyncio
    async def test_refreshes_expired_token(self):
        client = self._mock_client_with_token()
        auth = self._make_auth(client)

        await auth.get_token()

        # Force expiry
        auth._token_expires_at = time.time() - 1

        await auth.get_token()
        assert client.post.await_count == 2

    def test_get_app_jwt_returns_valid_jwt(self):
        auth = self._make_auth()
        token = auth.get_app_jwt()
        payload = jwt.decode(
            token, _private_key.public_key(), algorithms=["RS256"]
        )
        assert payload["iss"] == "12345"
        assert "exp" in payload

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock_response
        )
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = mock_response
        auth = self._make_auth(client)

        with pytest.raises(httpx.HTTPStatusError):
            await auth.get_token()
