from __future__ import annotations

import pytest
import json

from agentic_mcp_gateway.mcp_server import list_tools
from agentic_mcp_gateway.tools import ToolRegistry


def test_tool_registration_names(registry: ToolRegistry) -> None:
    names = registry.names()
    assert names == ["create_ticket", "retrieve_docs", "search_payments"]


def test_openai_schema_has_functions(registry: ToolRegistry) -> None:
    tools = registry.openai_tools()
    assert {t["function"]["name"] for t in tools} == set(registry.names())
    retrieve = next(t for t in tools if t["function"]["name"] == "retrieve_docs")
    assert "query" in retrieve["function"]["parameters"]["properties"]


def test_search_and_ticket_roundtrip(registry: ToolRegistry) -> None:
    found = json.loads(registry.call("search_payments", payment_id="PMT-1002"))
    assert found["count"] == 1
    assert found["payments"][0]["status"] == "held"

    created = json.loads(
        registry.call(
            "create_ticket",
            title="KYC hold on PMT-1002",
            queue="kyc",
            body="Name mismatch review",
            related_payment_id="PMT-1002",
        )
    )
    assert created["ok"] is True
    assert created["ticket"]["ticket_id"].startswith("TCK-")


def test_create_ticket_rejects_unknown_queue(registry: ToolRegistry) -> None:
    out = json.loads(
        registry.call("create_ticket", title="x", queue="executive_bypass", body="nope")
    )
    assert "error" in out


@pytest.mark.asyncio
async def test_mcp_list_tools_matches_registry() -> None:
    tools = await list_tools()
    assert {t.name for t in tools} == {"retrieve_docs", "search_payments", "create_ticket"}
