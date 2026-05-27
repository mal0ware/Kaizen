"""The agent loop: assemble context -> route -> complete -> run tools -> repeat.

After producing a reply it kicks off the scribe (if configured) as a background
task, so ambient learning never adds latency to the response.
"""
from __future__ import annotations

import asyncio

from kaizen.core.context import ContextEngine
from kaizen.core.models import Message, Role, Session
from kaizen.orchestration.router import Router, triage
from kaizen.providers.base import CompletionRequest
from kaizen.tools.base import ToolRegistry


class AgentLoop:
    def __init__(
        self,
        router: Router,
        context: ContextEngine,
        tools: ToolRegistry,
        scribe=None,
        max_tool_rounds: int = 3,
    ):
        self.router = router
        self.context = context
        self.tools = tools
        self.scribe = scribe
        self.max_tool_rounds = max_tool_rounds

    def _maybe_scribe(self, session: Session) -> None:
        if self.scribe is None:
            return
        try:
            asyncio.create_task(self.scribe.observe(session))
        except RuntimeError:
            pass  # no running event loop (e.g. called synchronously) — skip

    async def handle(self, session: Session, user_message: Message) -> Message:
        session.add(user_message)
        provider = self.router.choose(triage(user_message))

        for _ in range(self.max_tool_rounds):
            messages = await self.context.build(session)
            request = CompletionRequest(messages=messages, tools=self.tools.specs())
            response = await provider.complete(request)

            if response.tool_calls:
                session.add(
                    Message(
                        role=Role.ASSISTANT,
                        content=response.text,
                        name=provider.name,
                        tool_calls=response.tool_calls,
                    )
                )
                for call in response.tool_calls:
                    tool = self.tools.get(call.name)
                    result = (
                        await tool.run(**call.arguments)
                        if tool is not None
                        else f"[tool '{call.name}' not found]"
                    )
                    session.add(
                        Message(
                            role=Role.TOOL,
                            name=call.name,
                            content=str(result),
                            tool_call_id=call.id,
                        )
                    )
                continue

            assistant = session.add(
                Message(role=Role.ASSISTANT, content=response.text, name=provider.name)
            )
            self._maybe_scribe(session)
            return assistant

        assistant = session.add(
            Message(role=Role.ASSISTANT, content="(stopped: tool-round limit)", name=provider.name)
        )
        self._maybe_scribe(session)
        return assistant
