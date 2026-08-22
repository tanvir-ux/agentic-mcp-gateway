"""Small ReAct-style agent loop over the shared tool registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentic_mcp_gateway.config import Settings, get_settings
from agentic_mcp_gateway.llm import LLM, LLMTurn, build_llm
from agentic_mcp_gateway.tools import ToolRegistry

SYSTEM_PROMPT = (
    "You are an operations copilot. Use tools to look up payments, retrieve "
    "policy from the knowledge base, and open tickets. Cite tool results. "
    "Never invent settlement. Never bypass KYC."
)


@dataclass
class AgentTrace:
    final: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)


class OpsAgent:
    def __init__(
        self,
        registry: ToolRegistry | None = None,
        llm: LLM | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.registry = registry or ToolRegistry(self.settings)
        self.llm = llm or build_llm(self.settings)

    def run(self, user_message: str) -> AgentTrace:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        steps: list[dict[str, Any]] = []
        tools = self.registry.openai_tools()

        for _ in range(self.settings.max_agent_steps):
            turn: LLMTurn = self.llm.complete(messages, tools)
            if turn.tool_calls:
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": turn.content,
                    "tool_calls": [
                        {"name": c.name, "arguments": c.arguments} for c in turn.tool_calls
                    ],
                }
                messages.append(assistant_msg)
                for call in turn.tool_calls:
                    try:
                        result = self.registry.call(call.name, **call.arguments)
                    except TypeError as exc:
                        result = f"argument error: {exc}"
                    except KeyError as exc:
                        result = f"unknown tool: {exc}"
                    steps.append(
                        {"tool": call.name, "arguments": call.arguments, "result": result}
                    )
                    messages.append(
                        {"role": "tool", "name": call.name, "content": result}
                    )
                continue

            final = (turn.content or "").strip() or "No response."
            steps.append({"final": final})
            messages.append({"role": "assistant", "content": final})
            return AgentTrace(final=final, steps=steps, messages=messages)

        fallback = "Stopped after max steps. Partial trace is in `steps`."
        return AgentTrace(final=fallback, steps=steps, messages=messages)
