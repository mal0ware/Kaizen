from kaizen.config import Settings
from kaizen.core.models import Message, Role, ToolCall
from kaizen.providers.anthropic import to_anthropic
from kaizen.providers.base import Tier
from kaizen.providers.claude_code import flatten_prompt
from kaizen.providers.factory import build_router
from kaizen.providers.mock import MockProvider


def test_to_anthropic_system_and_user():
    msgs = [
        Message(role=Role.SYSTEM, content="be nice"),
        Message(role=Role.USER, content="hi"),
    ]
    system, out, _ = to_anthropic(msgs, [])
    assert system == "be nice"
    assert out == [{"role": "user", "content": "hi"}]


def test_to_anthropic_tool_use_and_result_match_by_id():
    call = ToolCall(name="current_time", arguments={}, id="t1")
    msgs = [
        Message(role=Role.ASSISTANT, content="", tool_calls=[call]),
        Message(role=Role.TOOL, name="current_time", content="2026", tool_call_id="t1"),
    ]
    _, out, _ = to_anthropic(msgs, [])
    assert out[0]["content"][0]["type"] == "tool_use" and out[0]["content"][0]["id"] == "t1"
    assert out[1]["content"][0]["type"] == "tool_result"
    assert out[1]["content"][0]["tool_use_id"] == "t1"


def test_flatten_prompt_for_claude_code():
    system, convo = flatten_prompt(
        [Message(role=Role.SYSTEM, content="sys"), Message(role=Role.USER, content="hello")]
    )
    assert system == "sys" and "User: hello" in convo


def test_router_offline_has_only_local():
    router = build_router(Settings(anthropic_api_key=None, use_claude_code_auth=False), MockProvider())
    assert set(router.providers.keys()) == {Tier.LOCAL}


def test_router_with_api_key_fills_cloud_tiers():
    from kaizen.providers.anthropic import AnthropicProvider

    router = build_router(Settings(anthropic_api_key="sk-test", use_claude_code_auth=False), MockProvider())
    assert isinstance(router.providers[Tier.CHEAP], AnthropicProvider)
    assert isinstance(router.providers[Tier.FRONTIER], AnthropicProvider)


def test_router_prefers_subscription_for_frontier():
    from kaizen.providers.claude_code import ClaudeCodeProvider

    router = build_router(Settings(anthropic_api_key="sk-test", use_claude_code_auth=True), MockProvider())
    assert isinstance(router.providers[Tier.FRONTIER], ClaudeCodeProvider)
