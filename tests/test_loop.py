from kaizen.cli.main import build_agent
from kaizen.core.models import Message, Role


async def test_mock_echo_roundtrip():
    bundle = build_agent()
    reply = await bundle.loop.handle(
        bundle.session, Message(role=Role.USER, content="hello world")
    )
    assert reply.role == Role.ASSISTANT
    assert "hello world" in reply.content


async def test_tool_round_executes_time_tool():
    bundle = build_agent()
    reply = await bundle.loop.handle(
        bundle.session, Message(role=Role.USER, content="what time is it")
    )
    assert "time" in reply.content.lower()
    # the tool result should have been recorded in the session
    assert any(
        m.role == Role.TOOL and m.name == "current_time" for m in bundle.session.messages
    )
