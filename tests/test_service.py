"""Headless-core service tests: one agent behind an ASGI app, exercised with
the FastAPI TestClient and the mock provider — no network, no infra."""
from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from kaizen.bootstrap import build_agent  # noqa: E402
from kaizen.config import Settings  # noqa: E402
from kaizen.service.app import create_app  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(settings=Settings()))


def _post_turn(client: TestClient, session_id: str, content: str) -> dict:
    resp = client.post(f"/sessions/{session_id}/messages", json={"content": content})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_health_reports_wiring(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "mock" in body["brains"].values()
    assert body["memory"] == "in-memory"


def test_create_session_and_fetch_it(client):
    resp = client.post("/sessions", json={"surface": "cli"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["surface"] == "cli"
    fetched = client.get(f"/sessions/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_get_unknown_session_404s(client):
    assert client.get("/sessions/nope").status_code == 404
    assert client.post("/sessions/nope/messages", json={"content": "hi"}).status_code == 404


def test_message_turn_returns_agent_reply(client):
    session_id = client.post("/sessions", json={}).json()["id"]
    reply = _post_turn(client, session_id, "hello kaizen")
    assert reply["role"] == "assistant"
    assert "hello kaizen" in reply["content"]


def test_cross_surface_continuity_two_clients_one_session():
    """Session created via client A, continued via client B: same context."""
    app = create_app(settings=Settings())
    client_a = TestClient(app)
    client_b = TestClient(app)

    session_id = client_a.post("/sessions", json={"surface": "discord"}).json()["id"]
    _post_turn(client_a, session_id, "first turn from A")
    _post_turn(client_b, session_id, "second turn from B")

    transcript = client_b.get(f"/sessions/{session_id}").json()["messages"]
    contents = [m["content"] for m in transcript]
    assert any("first turn from A" in c for c in contents)
    assert any("second turn from B" in c for c in contents)
    # Two user turns + two assistant replies over ONE shared session.
    assert sum(1 for m in transcript if m["role"] == "user") == 2
    assert sum(1 for m in transcript if m["role"] == "assistant") == 2


def test_proposals_listed_and_approved_via_api(tmp_path):
    settings = Settings(state_dir=str(tmp_path))
    app = create_app(settings=settings)
    client = TestClient(app)

    session_id = client.post("/sessions", json={}).json()["id"]
    for _ in range(3):
        _post_turn(client, session_id, "I prefer terse replies, no preamble")

    pending = client.get("/proposals").json()
    assert pending, "expected the curator to have proposed an instinct"
    target = pending[0]
    assert target["kind"] == "instinct"
    assert target["status"] == "pending"

    resp = client.post(f"/proposals/{target['id']}/approve")
    assert resp.status_code == 200
    assert "learned trait" in resp.json()["note"]

    traits = client.get("/traits").json()["traits"]
    assert traits

    # The trait persisted: a fresh agent over the same state dir has it.
    rebuilt = build_agent(Settings(state_dir=str(tmp_path)))
    assert rebuilt.learned_traits == traits


def test_reject_proposal_via_api(client):
    session_id = client.post("/sessions", json={}).json()["id"]
    for _ in range(3):
        _post_turn(client, session_id, "please always run ruff before committing")
    pending = client.get("/proposals").json()
    assert pending
    resp = client.post(f"/proposals/{pending[0]['id']}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    remaining = {p["id"] for p in client.get("/proposals").json()}
    assert pending[0]["id"] not in remaining


def test_unknown_proposal_404s_and_double_decide_409s(client):
    assert client.post("/proposals/nope/approve").status_code == 404
    session_id = client.post("/sessions", json={}).json()["id"]
    for _ in range(3):
        _post_turn(client, session_id, "I prefer tabs over spaces")
    target = client.get("/proposals").json()[0]
    assert client.post(f"/proposals/{target['id']}/approve").status_code == 200
    assert client.post(f"/proposals/{target['id']}/approve").status_code == 409


def test_sessions_snapshot_survives_restart(tmp_path):
    settings = Settings(state_dir=str(tmp_path))
    client = TestClient(create_app(settings=settings))
    session_id = client.post("/sessions", json={}).json()["id"]
    _post_turn(client, session_id, "remember this turn")

    # New app over the same state dir: the session is still there.
    client2 = TestClient(create_app(settings=Settings(state_dir=str(tmp_path))))
    fetched = client2.get(f"/sessions/{session_id}")
    assert fetched.status_code == 200
    assert any("remember this turn" in m["content"] for m in fetched.json()["messages"])


def test_skills_endpoint_lists_active_skills(client):
    skills = client.get("/skills").json()
    names = {s["name"] for s in skills}
    assert "search-first" in names
