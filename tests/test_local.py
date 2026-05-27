from kaizen.config import Settings
from kaizen.core.models import Message, Role, ToolCall
from kaizen.providers.base import Tier
from kaizen.providers.factory import build_router
from kaizen.providers.local import to_ollama
from kaizen.providers.mock import MockProvider


def test_to_ollama_basic_roles():
    out, tools = to_ollama(
        [Message(role=Role.SYSTEM, content="s"), Message(role=Role.USER, content="u")], []
    )
    assert out == [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    assert tools == []


def test_to_ollama_tool_calls_and_results():
    call = ToolCall(name="t", arguments={"a": 1}, id="x")
    out, _ = to_ollama(
        [
            Message(role=Role.ASSISTANT, content="", tool_calls=[call]),
            Message(role=Role.TOOL, name="t", content="r", tool_call_id="x"),
        ],
        [],
    )
    assert out[0]["tool_calls"][0]["function"]["name"] == "t"
    assert out[1] == {"role": "tool", "content": "r"}


def test_to_ollama_tool_schema():
    _, tools = to_ollama([], [{"name": "current_time", "description": "d"}])
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "current_time"


def test_router_uses_local_when_enabled():
    from kaizen.providers.local import LocalProvider

    router = build_router(
        Settings(use_local_model=True, anthropic_api_key=None, use_claude_code_auth=False),
        MockProvider(),
    )
    assert isinstance(router.providers[Tier.LOCAL], LocalProvider)


def test_router_uses_mock_when_local_disabled():
    router = build_router(
        Settings(use_local_model=False, anthropic_api_key=None, use_claude_code_auth=False),
        MockProvider(),
    )
    assert isinstance(router.providers[Tier.LOCAL], MockProvider)
