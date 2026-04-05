import logging
import time

import httpx
import jwt

logger = logging.getLogger(__name__)


def _build_jwt(app_id: str, private_key_pem: str) -> str:
    """Create a short-lived (10 min) RS256 JWT for GitHub App authentication."""
    now = int(time.time())
    payload = {
        "iat": now,
        "exp": now + 600,
        "iss": app_id,
    }
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


class GitHubAppAuth:
    def __init__(
        self,
        app_id: str,
        private_key_pem: str,
        installation_id: str,
        client: httpx.AsyncClient,
    ) -> None:
        self._app_id = app_id
        self._private_key_pem = private_key_pem
        self._installation_id = installation_id
        self._client = client
        self._cached_token: str | None = None
        self._token_expires_at: float = 0

    def get_app_jwt(self) -> str:
        """Return a fresh app-level JWT for endpoints requiring app authentication."""
        return _build_jwt(self._app_id, self._private_key_pem)

    async def get_token(self) -> str:
        """Return a cached installation access token, or fetch a new one if expired or missing."""
        if self._cached_token and time.time() < self._token_expires_at:
            return self._cached_token

        token_jwt = _build_jwt(self._app_id, self._private_key_pem)
        response = await self._client.post(
            f"https://api.github.com/app/installations/{self._installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {token_jwt}",
                "Accept": "application/vnd.github+json",
            },
        )
        response.raise_for_status()

        data = response.json()
        self._cached_token = data["token"]
        # Refresh 5 minutes before actual expiry (tokens last 1 hour)
        self._token_expires_at = time.time() + 3300
        logger.info("Obtained new installation token (expires in ~55min)")
        return self._cached_token
