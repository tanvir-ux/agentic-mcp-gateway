from __future__ import annotations

from agentic_mcp_gateway.agent import OpsAgent
from agentic_mcp_gateway.llm import FakeLLM, ToolCall
from agentic_mcp_gateway.tools import ToolRegistry


def test_mocked_agent_turn(registry: ToolRegistry, settings) -> None:
    class OneShot:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                from agentic_mcp_gateway.llm import LLMTurn

                return LLMTurn(
                    content=None,
                    tool_calls=[ToolCall("search_payments", {"payment_id": "PMT-1001"})],
                )
            from agentic_mcp_gateway.llm import LLMTurn

            return LLMTurn(content="PMT-1001 settled USD 12500.", tool_calls=[])

    llm = OneShot()
    agent = OpsAgent(registry=registry, llm=llm, settings=settings)
    trace = agent.run("Where is PMT-1001?")
    assert llm.calls == 2
    assert trace.steps[0]["tool"] == "search_payments"
    assert "PMT-1001" in trace.steps[0]["result"]
    assert "settled" in trace.final.lower()


def test_fake_llm_full_loop_opens_ticket(registry: ToolRegistry, settings) -> None:
    agent = OpsAgent(registry=registry, llm=FakeLLM(), settings=settings)
    trace = agent.run("Find payment PMT-1002 and open a ticket if it is stuck on KYC")
    tools_used = [s.get("tool") for s in trace.steps if "tool" in s]
    assert "search_payments" in tools_used
    assert "create_ticket" in tools_used
    assert "TCK-" in trace.final or "TCK-" in str(trace.steps)
