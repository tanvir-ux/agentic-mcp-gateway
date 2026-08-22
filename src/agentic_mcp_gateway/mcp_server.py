"""MCP stdio server exposing the same tools as the HTTP agent.

Uses the official MCP Python SDK 2.x (`MCPServer`, FastMCP-style). Run:

    PYTHONPATH=src python -m agentic_mcp_gateway.mcp_server
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from agentic_mcp_gateway.tools import ToolRegistry


def build_mcp_server(registry: ToolRegistry | None = None) -> MCPServer:
    """Register retrieve_docs / search_payments / create_ticket on an MCP server."""
    registry = registry or ToolRegistry()
    mcp = MCPServer(
        name="agentic-mcp-gateway",
        version="0.1.0",
        instructions=(
            "Ops copilot tools: retrieve policy docs, search a mock payment ledger, "
            "and open investigation tickets. Shared with the HTTP /chat agent."
        ),
    )

    @mcp.tool(description=registry.get("retrieve_docs").description)
    def retrieve_docs(query: str, top_k: int = 3) -> str:
        return registry.retrieve_docs(query=query, top_k=top_k)

    @mcp.tool(description=registry.get("search_payments").description)
    def search_payments(
        payment_id: str | None = None,
        end_to_end_id: str | None = None,
        status: str | None = None,
        q: str | None = None,
    ) -> str:
        return registry.search_payments(
            payment_id=payment_id,
            end_to_end_id=end_to_end_id,
            status=status,
            q=q,
        )

    @mcp.tool(description=registry.get("create_ticket").description)
    def create_ticket(
        title: str,
        queue: str,
        body: str,
        related_payment_id: str | None = None,
    ) -> str:
        return registry.create_ticket(
            title=title,
            queue=queue,
            body=body,
            related_payment_id=related_payment_id,
        )

    return mcp


mcp = build_mcp_server()


async def list_tools():
    """Used by tests: MCP-advertised tool list."""
    return await mcp.list_tools()


def main() -> None:
    import asyncio

    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
