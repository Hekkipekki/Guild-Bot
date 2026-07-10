from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import aiohttp


TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
CLASSIC_GRAPHQL_URL = "https://classic.warcraftlogs.com/api/v2/client"
TOKEN_EXPIRY_SAFETY_SECONDS = 60


class WarcraftLogsError(RuntimeError):
    """Base error for Warcraft Logs API operations."""


class WarcraftLogsConfigurationError(WarcraftLogsError):
    """Raised when application credentials are missing."""


class WarcraftLogsAuthenticationError(WarcraftLogsError):
    """Raised when OAuth authentication fails."""


class WarcraftLogsRequestError(WarcraftLogsError):
    """Raised for HTTP or GraphQL request failures."""


@dataclass(frozen=True)
class AccessToken:
    value: str
    expires_at: float

    def is_valid(self, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        return bool(self.value) and current < self.expires_at


class WarcraftLogsClient:
    """Application-level OAuth client for the Warcraft Logs v2 GraphQL API."""

    def __init__(
        self,
        client_id: str | None,
        client_secret: str | None,
        *,
        token_url: str = TOKEN_URL,
        graphql_url: str = CLASSIC_GRAPHQL_URL,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.client_id = str(client_id or "").strip()
        self.client_secret = str(client_secret or "").strip()
        self.token_url = token_url
        self.graphql_url = graphql_url
        self._session = session
        self._owns_session = session is None
        self._token: AccessToken | None = None
        self._token_lock = asyncio.Lock()

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def query(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not str(query).strip():
            raise ValueError("A GraphQL query is required.")

        token = await self._get_access_token()
        session = await self._get_session()

        try:
            async with session.post(
                self.graphql_url,
                json={"query": query, "variables": variables or {}},
                headers={"Authorization": f"Bearer {token}"},
            ) as response:
                payload = await self._read_json(response)
        except aiohttp.ClientError as exc:
            raise WarcraftLogsRequestError(
                f"Warcraft Logs request failed: {exc}"
            ) from exc

        if response.status >= 400:
            raise WarcraftLogsRequestError(
                f"Warcraft Logs returned HTTP {response.status}."
            )

        errors = payload.get("errors")
        if errors:
            messages = [
                str(item.get("message", "Unknown GraphQL error"))
                for item in errors
                if isinstance(item, dict)
            ]
            raise WarcraftLogsRequestError("; ".join(messages) or "GraphQL request failed.")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise WarcraftLogsRequestError("Warcraft Logs returned no GraphQL data.")
        return data

    async def _get_access_token(self) -> str:
        if not self.is_configured:
            raise WarcraftLogsConfigurationError(
                "WARCRAFTLOGS_CLIENT_ID and WARCRAFTLOGS_CLIENT_SECRET are required."
            )

        if self._token and self._token.is_valid():
            return self._token.value

        async with self._token_lock:
            if self._token and self._token.is_valid():
                return self._token.value
            self._token = await self._request_access_token()
            return self._token.value

    async def _request_access_token(self) -> AccessToken:
        session = await self._get_session()
        auth = aiohttp.BasicAuth(self.client_id, self.client_secret)

        try:
            async with session.post(
                self.token_url,
                data={"grant_type": "client_credentials"},
                auth=auth,
            ) as response:
                payload = await self._read_json(response)
        except aiohttp.ClientError as exc:
            raise WarcraftLogsAuthenticationError(
                f"Warcraft Logs authentication failed: {exc}"
            ) from exc

        if response.status >= 400:
            raise WarcraftLogsAuthenticationError(
                f"Warcraft Logs authentication returned HTTP {response.status}."
            )

        token = str(payload.get("access_token", "")).strip()
        try:
            expires_in = max(int(payload.get("expires_in", 0)), 0)
        except (TypeError, ValueError):
            expires_in = 0

        if not token:
            raise WarcraftLogsAuthenticationError(
                "Warcraft Logs did not return an access token."
            )

        usable_lifetime = max(expires_in - TOKEN_EXPIRY_SAFETY_SECONDS, 1)
        return AccessToken(
            value=token,
            expires_at=time.monotonic() + usable_lifetime,
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
            self._owns_session = True
        return self._session

    @staticmethod
    async def _read_json(response: aiohttp.ClientResponse) -> dict[str, Any]:
        try:
            payload = await response.json(content_type=None)
        except (aiohttp.ContentTypeError, ValueError) as exc:
            raise WarcraftLogsRequestError(
                "Warcraft Logs returned an invalid JSON response."
            ) from exc
        if not isinstance(payload, dict):
            raise WarcraftLogsRequestError(
                "Warcraft Logs returned an unexpected response shape."
            )
        return payload
