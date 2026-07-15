"""HTTP client for the headless core — what every remote surface speaks.

A thin, typed wrapper over ``httpx.AsyncClient`` mirroring the service API
one-for-one. ``connect`` is the attach handshake: probe ``/health`` and hand
back a client if a daemon is listening, ``None`` if not — surfaces use it to
choose between client mode and their embedded fallback.

``httpx`` ships with both the ``local`` and ``service`` extras.
"""
from __future__ import annotations

from typing import Any

import httpx


class ServiceClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=self.base_url, timeout=timeout, transport=transport
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str) -> Any:
        resp = await self._http.get(path)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        resp = await self._http.post(path, json=json if json is not None else {})
        resp.raise_for_status()
        return resp.json()

    # --- API surface ----------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        return await self._get("/health")

    async def create_session(self, surface: str = "api") -> dict[str, Any]:
        return await self._post("/sessions", {"surface": surface})

    async def get_session(self, session_id: str) -> dict[str, Any]:
        return await self._get(f"/sessions/{session_id}")

    async def send(
        self,
        session_id: str,
        content: str,
        author_id: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        return await self._post(
            f"/sessions/{session_id}/messages",
            {"content": content, "author_id": author_id, "name": name},
        )

    async def proposals(self) -> list[dict[str, Any]]:
        return await self._get("/proposals")

    async def approve(self, proposal_id: str) -> dict[str, Any]:
        return await self._post(f"/proposals/{proposal_id}/approve")

    async def reject(self, proposal_id: str) -> dict[str, Any]:
        return await self._post(f"/proposals/{proposal_id}/reject")

    async def traits(self) -> list[str]:
        return list((await self._get("/traits"))["traits"])

    async def skills(self) -> list[dict[str, Any]]:
        return await self._get("/skills")


async def connect(base_url: str, timeout: float = 1.0) -> ServiceClient | None:
    """Probe the daemon; return an attached client, or ``None`` if unreachable.

    Deliberately quiet on failure — "no daemon" is the normal dev case and
    the caller falls back to embedded mode.
    """
    if not base_url:
        return None
    client = ServiceClient(base_url)
    try:
        # Probe with a short per-request timeout; the client itself keeps its
        # generous default for actual turns.
        resp = await client._http.get("/health", timeout=timeout)
        resp.raise_for_status()
        if resp.json().get("status") == "ok":
            return client
    except (httpx.HTTPError, OSError):
        pass
    await client.close()
    return None
