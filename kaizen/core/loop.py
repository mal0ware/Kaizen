"""The agent loop: assemble context -> route -> complete -> run tools -> repeat.

Bounded by a tool-round limit (stand-in for the iteration budget, ADR 0001/0005).
"""
from __future__ import annotations

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
        max_tool_rounds: int = 3,
    ):
        self.router = router
        self.context = context
        self.tools = tools
        self.max_tool_rounds = max_tool_rounds

    async def handle(self, session: Session, user_message: Message) -> Message:
        session.add(user_message)
        provider = self.router.choose(triage(user_message))

        for _ in range(self.max_tool_rounds):
            messages = await self.context.build(session)
            request = CompletionRequest(messages=messages, tools=self.tools.specs())
            response = await provider.complete(request)

            if response.tool_calls:
                for call in response.tool_calls:
                    tool = self.tools.get(call.name)
                    result = (
                        await tool.run(**call.arguments)
                        if tool is not None
                        else f"[tool '{call.name}' not found]"
                    )
                    session.add(Message(role=Role.TOOL, name=call.name, content=str(result)))
                continue  # feed the tool result back to the model

            assistant = Message(role=Role.ASSISTANT, content=response.text, name=provider.name)
            return session.add(assistant)

        return session.add(
            Message(role=Role.ASSISTANT, content="(stopped: tool-round limit)", name=provider.name)
        )
