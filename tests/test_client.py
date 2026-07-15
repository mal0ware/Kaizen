"""Service-client tests: the same HTTP client the CLI and Discord surfaces
use, run in-process against the real ASGI app via httpx's ASGITransport —
end-to-end over the wire format, zero network."""
from __future__ import annotations

import httpx
import pytest

pytest.importorskip("fastapi")

from kaizen.cli.main import handle_remote_command  # noqa: E402
from kaizen.config import Settings  # noqa: E402
from kaizen.service.app import create_app  # noqa: E402
from kaizen.service.client import ServiceClient, connect  # noqa: E402


def _client(app) -> ServiceClient:
    return ServiceClient(
        "http://kaizen.test", transport=httpx.ASGITransport(app=app)
    )


@pytest.fixture()
def app():
    return create_app(settings=Settings())


async def test_client_health_and_session_roundtrip(app):
    client = _client(app)
    health = await client.health()
    assert health["status"] == "ok"

    session = await client.create_session(surface="cli")
    reply = await client.send(session["id"], "hello over http")
    assert reply["role"] == "assistant"
    assert "hello over http" in reply["content"]
    await client.close()


async def test_two_clients_share_one_session(app):
    """Cross-surface continuity: client A starts, client B continues."""
    a, b = _client(app), _client(app)
    session = await a.create_session(surface="cli")
    await a.send(session["id"], "turn from A")
    await b.send(session["id"], "turn from B")

    transcript = await b.get_session(session["id"])
    contents = [m["content"] for m in transcript["messages"]]
    assert any("turn from A" in c for c in contents)
    assert any("turn from B" in c for c in contents)
    await a.close()
    await b.close()


async def test_client_proposal_flow(app):
    client = _client(app)
    session = await client.create_session()
    for _ in range(3):
        await client.send(session["id"], "I prefer terse replies, no preamble")
    pending = await client.proposals()
    assert pending
    decision = await client.approve(pending[0]["id"])
    assert decision["status"] == "approved"
    assert await client.traits()
    await client.close()


async def test_connect_returns_none_when_no_daemon():
    # Nothing listens on this port; the probe must fail fast and quietly.
    assert await connect("http://127.0.0.1:9", timeout=0.2) is None


async def test_remote_command_handling(app):
    """The CLI's slash commands, driven over HTTP."""
    client = _client(app)
    session = await client.create_session()
    for _ in range(3):
        await client.send(session["id"], "please always run ruff before committing")

    out = await handle_remote_command("/proposals", client)
    assert out is not None and "instinct" in out

    pending = await client.proposals()
    prefix = pending[0]["id"][:8]
    out = await handle_remote_command(f"/approve {prefix}", client)
    assert out is not None and "learned trait" in out

    out = await handle_remote_command("/traits", client)
    assert out is not None and "When relevant" in out

    out = await handle_remote_command("/skills", client)
    assert out is not None and "search-first" in out

    assert await handle_remote_command("not a command", client) is None
    await client.close()


async def test_discord_remote_helpers_share_the_daemon_brain(app):
    """The Discord surface's client-mode path: one service session per
    channel, operator commands over HTTP."""
    discord = pytest.importorskip("discord")  # noqa: F841 — needed to import the surface
    from kaizen.surfaces.discord_bot import handle_dm_command_remote, remote_turn

    remote = _client(app)
    session_ids: dict[int, str] = {}

    text = await remote_turn(remote, session_ids, 111, "hello from discord", "42", "Mal")
    assert "hello from discord" in text
    assert 111 in session_ids

    # Same channel reuses the same service session.
    await remote_turn(remote, session_ids, 111, "second turn", "42", "Mal")
    transcript = await remote.get_session(session_ids[111])
    assert sum(1 for m in transcript["messages"] if m["role"] == "user") == 2

    for _ in range(3):
        await remote_turn(remote, session_ids, 111, "I prefer tabs over spaces", "42", "Mal")
    out = await handle_dm_command_remote("!proposals", remote)
    assert out is not None and "instinct" in out

    pending = await remote.proposals()
    out = await handle_dm_command_remote(f"!approve {pending[0]['id'][:8]}", remote)
    assert out is not None and "learned trait" in out

    out = await handle_dm_command_remote("!traits", remote)
    assert out is not None and "tabs" in out
    assert await handle_dm_command_remote("hello", remote) is None
    await remote.close()
