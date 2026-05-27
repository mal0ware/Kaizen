"""Claude Code provider — uses the Max subscription instead of metered API.

This is how Kaizen spends the $200 plan: the `claude` CLI is logged into your
subscription, so calls here draw on the plan, not pay-per-token (ADR 0008).

TEXT ONLY: Claude Code manages its own tools, so this path does not drive our
structured tool loop — it's for the operator's personal reasoning lane. Honest
caveats: the subscription has rate limits and is meant for personal/interactive
use; the autonomous, multi-user bot lane should use the metered API instead.
"""
from __future__ import annotations

import asyncio
import json
import shutil

from kaizen.core.models import Message, Role
from kaizen.providers.base import CompletionRequest, CompletionResponse, Tier


def flatten_prompt(messages: list[Message]) -> tuple[str, str]:
    """(system_text, conversation_text) — Claude Code's `-p` takes a single prompt."""
    system = "\n\n".join(m.content for m in messages if m.role == Role.SYSTEM and m.content)
    lines: list[str] = []
    for m in messages:
        if m.role == Role.USER:
            lines.append(f"User: {m.content}")
        elif m.role == Role.ASSISTANT and m.content:
            lines.append(f"Assistant: {m.content}")
    return system, "\n".join(lines)


class ClaudeCodeProvider:
    def __init__(self, tier: Tier = Tier.FRONTIER, binary: str = "claude"):
        self.name = "claude-code"
        self.tier = tier
        self.binary = binary

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        if shutil.which(self.binary) is None:
            raise RuntimeError(
                f"'{self.binary}' CLI not found. Install Claude Code and log in with your "
                "Max subscription to use the subscription lane (ADR 0008)."
            )

        system, prompt = flatten_prompt(request.messages)
        cmd = [self.binary, "-p", prompt, "--output-format", "json"]
        if system:
            cmd += ["--append-system-prompt", system]

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"claude CLI failed ({proc.returncode}): {stderr.decode()[:300]}")

        raw = stdout.decode().strip()
        text = raw
        try:
            data = json.loads(raw)
            text = data.get("result") or data.get("text") or raw
        except json.JSONDecodeError:
            pass

        return CompletionResponse(text=text, model="claude-code")
