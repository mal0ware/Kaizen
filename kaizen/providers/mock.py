"""MockProvider — a deterministic, no-network provider for local development.

Lets the whole loop run with zero infra and zero API keys. It echoes the last
user message, and if the user mentions "time" it emits a tool call to the
`current_time` tool to exercise the tool loop end-to-end.
"""
from __future__ import annotations

from kaizen.core.models import Role, ToolCall
from kaizen.providers.base import CompletionRequest, CompletionResponse, Tier


class MockProvider:
    name = "mock"
    tier = Tier.LOCAL

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        last_user = next(
            (m for m in reversed(request.messages) if m.role == Role.USER), None
        )
        text = last_user.content if last_user else ""
        has_tool_result = any(m.role == Role.TOOL for m in request.messages)

        if "time" in text.lower() and not has_tool_result:
            return CompletionResponse(tool_calls=[ToolCall(name="current_time")], model="mock")

        if has_tool_result:
            tool_msg = next(m for m in reversed(request.messages) if m.role == Role.TOOL)
            return CompletionResponse(
                text=f"(mock) The current time is {tool_msg.content}.", model="mock"
            )

        return CompletionResponse(text=f"(mock) You said: {text}", model="mock")
