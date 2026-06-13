"""Anthropic provider (metered API key). See ADR 0006 / ADR 0008.

`complete()` maps our messages <-> the Anthropic Messages API, including tool use
(tool_use / tool_result matched by id) and optional extended thinking. The
`anthropic` SDK is an optional dependency, imported lazily, so importing this
module stays light. The message converter is a pure, SDK-free function so it can
be unit-tested without a key.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kaizen.core.models import Message, Role, ToolCall
from kaizen.providers.base import CompletionRequest, CompletionResponse, Tier

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic


def to_anthropic(
    messages: list[Message], tools: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert our messages/tools into (system_text, messages, tools) for the API."""
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []

    for m in messages:
        if m.role == Role.SYSTEM:
            if m.content:
                system_parts.append(m.content)
        elif m.role == Role.USER:
            out.append({"role": "user", "content": m.content})
        elif m.role == Role.ASSISTANT:
            if m.tool_calls:
                blocks: list[dict[str, Any]] = []
                if m.content:
                    blocks.append({"type": "text", "text": m.content})
                for call in m.tool_calls:
                    blocks.append(
                        {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
                    )
                out.append({"role": "assistant", "content": blocks})
            else:
                out.append({"role": "assistant", "content": m.content})
        elif m.role == Role.TOOL:
            out.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}
                    ],
                }
            )

    anthropic_tools = [
        {
            "name": t["name"],
            "description": t.get("description", ""),
            "input_schema": t.get("input_schema", {"type": "object", "properties": {}}),
        }
        for t in tools
    ]
    return "\n\n".join(system_parts), out, anthropic_tools


class AnthropicProvider:
    def __init__(self, model: str, tier: Tier = Tier.FRONTIER, api_key: str | None = None):
        self.name = f"anthropic:{model}"
        self.tier = tier
        self.model = model
        self._api_key = api_key
        self._client: AsyncAnthropic | None = None

    def _client_or_create(self) -> AsyncAnthropic:
        if self._client is None:
            from anthropic import AsyncAnthropic  # lazy optional dep

            # api_key=None lets the SDK fall back to the ANTHROPIC_API_KEY env var.
            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        client = self._client_or_create()
        system, messages, tools = to_anthropic(request.messages, request.tools)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        if request.extended_thinking:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": max(1024, request.max_tokens // 2),
            }

        resp = await client.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCall(name=block.name, arguments=dict(block.input or {}), id=block.id)
                )

        usage = getattr(resp, "usage", None)
        return CompletionResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            model=self.model,
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
        )
