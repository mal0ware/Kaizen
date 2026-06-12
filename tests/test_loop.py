from kaizen.cli.main import build_agent
from kaizen.config import Settings
from kaizen.core.models import Message, Role


def mock_settings() -> Settings:
    """Pin the provider stack to the deterministic mock path.

    These tests cover the loop contract (route -> complete -> tool round ->
    reply recorded), so they must not inherit whatever model a developer's
    .env wires in.
    """
    return Settings(use_local_model=False, anthropic_api_key=None, use_claude_code_auth=False)


async def test_mock_echo_roundtrip():
    bundle = build_agent(mock_settings())
    reply = await bundle.loop.handle(
        bundle.session, Message(role=Role.USER, content="hello world")
    )
    assert reply.role == Role.ASSISTANT
    # Mock provider contract: the reply reflects the user's content back.
    assert "hello world" in reply.content
    # The exchange is recorded on the session, reply last.
    assert bundle.session.messages[-1] is reply


async def test_tool_round_executes_time_tool():
    bundle = build_agent(mock_settings())
    reply = await bundle.loop.handle(
        bundle.session, Message(role=Role.USER, content="what time is it")
    )
    # The tool result must have been recorded in the session...
    tool_messages = [
        m for m in bundle.session.messages if m.role == Role.TOOL and m.name == "current_time"
    ]
    assert tool_messages
    # ...and the reply must carry the tool's actual output (substance over
    # phrasing, so the persona/voice layer can evolve without breaking this).
    assert tool_messages[-1].content in reply.content
