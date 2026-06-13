"""Local provider — talks to Ollama's chat API on the home GPU worker (ADR 0007).

Uses Ollama's native /api/chat. Tool-calling works for models whose template
supports it (e.g. qwen2.5, hermes3); for models that don't (e.g. dolphin3),
Ollama returns 400 when `tools` are sent, so we transparently retry without
tools — the model still chats, it just can't call tools. `httpx` is a lazy
optional dep. The message converter is a pure function (unit-tested without Ollama).
"""
from __future__ import annotations

import json

from kaizen.core.models import Message, Role, ToolCall
from kaizen.providers.base import CompletionRequest, CompletionResponse, Tier


def to_ollama(messages: list[Message], tools: list[dict]) -> tuple[list[dict], list[dict]]:
    """Convert our messages/tools into Ollama /api/chat shape."""
    out: list[dict] = []
    for m in messages:
        if m.role == Role.SYSTEM:
            out.append({"role": "system", "content": m.content})
        elif m.role == Role.USER:
            out.append({"role": "user", "content": m.content})
        elif m.role == Role.ASSISTANT:
            entry: dict = {"role": "assistant", "content": m.content}
            if m.tool_calls:
                entry["tool_calls"] = [
                    {"function": {"name": c.name, "arguments": c.arguments}} for c in m.tool_calls
                ]
            out.append(entry)
        elif m.role == Role.TOOL:
            out.append({"role": "tool", "content": m.content})

    ollama_tools = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in tools
    ]
    return out, ollama_tools


class LocalProvider:
    def __init__(self, model: str, endpoint: str = "http://localhost:11434", tier: Tier = Tier.LOCAL):
        self.name = f"local:{model}"
        self.tier = tier
        self.model = model
        self.endpoint = endpoint.rstrip("/")

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        import httpx  # lazy optional dep

        messages, tools = to_ollama(request.messages, request.tools)

        async def _post(payload: dict[str, object]) -> httpx.Response:
            async with httpx.AsyncClient(timeout=120) as client:
                return await client.post(f"{self.endpoint}/api/chat", json=payload)

        payload: dict = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools

        try:
            resp = await _post(payload)
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Can't reach Ollama at {self.endpoint} — is it installed and running? "
                "(check the tray icon, or run `ollama list`)"
            ) from exc

        # Some models (e.g. dolphin3) don't support tools -> Ollama 400s. Retry plain.
        if resp.status_code == 400 and tools:
            resp = await _post({"model": self.model, "messages": messages, "stream": False})

        if resp.status_code >= 400:
            raise RuntimeError(f"Ollama returned {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        msg = data.get("message", {})
        tool_calls: list[ToolCall] = []
        for tc in msg.get("tool_calls", []) or []:
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            tool_calls.append(ToolCall(name=fn.get("name", ""), arguments=args or {}))

        return CompletionResponse(
            text=msg.get("content", "") or "",
            tool_calls=tool_calls,
            model=self.model,
            input_tokens=data.get("prompt_eval_count", 0) or 0,
            output_tokens=data.get("eval_count", 0) or 0,
        )
