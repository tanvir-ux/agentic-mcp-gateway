"""Shared tool registry used by both the MCP server and the agent loop."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agentic_mcp_gateway.ascp import AscpGateway, AuthzResult, Decision, HitlStore
from agentic_mcp_gateway.config import Settings, get_settings
from agentic_mcp_gateway.rag import Retriever
from agentic_mcp_gateway.store import OpsStore


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., str]


class ToolRegistry:
    def __init__(
        self,
        settings: Settings | None = None,
        store: OpsStore | None = None,
        ascp: AscpGateway | None = None,
        enforce_ascp: bool = True,
    ) -> None:
        self.settings = settings or get_settings()
        self.store = store or OpsStore(self.settings.sqlite_path)
        self.retriever = Retriever(self.settings.kb_dir, dims=self.settings.embedding_dims)
        self.ascp = ascp or AscpGateway()
        self.enforce_ascp = enforce_ascp
        self._tools: dict[str, ToolSpec] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(
            ToolSpec(
                name="retrieve_docs",
                description=(
                    "Semantic search over the local operations knowledge base "
                    "(payments lifecycle, KYC, interbank messaging)."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Natural language question"},
                        "top_k": {"type": "integer", "description": "Number of chunks", "default": 3},
                    },
                    "required": ["query"],
                },
                handler=self.retrieve_docs,
            )
        )
        self.register(
            ToolSpec(
                name="search_payments",
                description="Search the mock payment ledger by id, reference, status, or free text.",
                parameters={
                    "type": "object",
                    "properties": {
                        "payment_id": {"type": "string"},
                        "end_to_end_id": {"type": "string"},
                        "status": {"type": "string"},
                        "q": {"type": "string", "description": "Fuzzy match on parties / scheme ref"},
                    },
                },
                handler=self.search_payments,
            )
        )
        self.register(
            ToolSpec(
                name="create_ticket",
                description="Open an operations ticket (KYC queue, scheme_ops, recalls, repair).",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "queue": {
                            "type": "string",
                            "description": "kyc | scheme_ops | recalls | repair",
                        },
                        "body": {"type": "string"},
                        "related_payment_id": {"type": "string"},
                    },
                    "required": ["title", "queue", "body"],
                },
                handler=self.create_ticket,
            )
        )
        self.register(
            ToolSpec(
                name="create_transfer",
                description=(
                    "Create a mock credit transfer (side effect). HITL-gated by ASCP: "
                    "approval must match the exact action digest of tool+args."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "originator": {"type": "string"},
                        "beneficiary": {"type": "string"},
                        "currency": {"type": "string", "default": "USD"},
                        "amount": {"type": "number"},
                        "end_to_end_id": {"type": "string"},
                    },
                    "required": ["originator", "beneficiary", "amount", "end_to_end_id"],
                },
                handler=self.create_transfer,
            )
        )

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def names(self) -> list[str]:
        return sorted(self._tools)

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name]

    def call(self, name: str, **kwargs: Any) -> str:
        """Execute a tool, optionally through ASCP ALLOW/DENY/HITL."""
        if not self.enforce_ascp:
            return self.get(name).handler(**kwargs)
        result = self.authorize_and_call(name, kwargs)
        if result.output is not None:
            return result.output
        return json.dumps(
            {
                "ascp": {
                    "decision": result.decision.value,
                    "digest": result.digest,
                    "message": result.message,
                }
            }
        )

    def authorize_and_call(self, name: str, args: dict[str, Any]) -> AuthzResult:
        cleaned = {k: v for k, v in args.items() if v is not None}
        authz = self.ascp.evaluate(name, cleaned)
        if authz.decision is Decision.ALLOW:
            out = self.get(name).handler(**cleaned)
            return AuthzResult(
                Decision.ALLOW,
                authz.digest,
                authz.message,
                executed=True,
                output=out,
            )
        if authz.decision is Decision.HITL:
            return AuthzResult(
                Decision.HITL,
                authz.digest,
                authz.message,
                executed=False,
                output=json.dumps(
                    {
                        "ascp": {
                            "decision": "HITL",
                            "digest": authz.digest,
                            "message": authz.message,
                        }
                    }
                ),
            )
        return AuthzResult(
            Decision.DENY,
            authz.digest,
            authz.message,
            executed=False,
            output=json.dumps(
                {
                    "ascp": {
                        "decision": "DENY",
                        "digest": authz.digest,
                        "message": authz.message,
                    }
                }
            ),
        )

    def preview_digest(self, name: str, **kwargs: Any) -> str:
        cleaned = {k: v for k, v in kwargs.items() if v is not None}
        return self.ascp.evaluate(name, cleaned).digest

    def retrieve_docs(self, query: str, top_k: int = 3) -> str:
        hits = self.retriever.search(query, top_k=int(top_k or self.settings.rag_top_k))
        if not hits:
            return json.dumps({"hits": [], "note": "knowledge base empty or no match"})
        payload = [
            {
                "doc_id": h.chunk.doc_id,
                "heading": h.chunk.heading,
                "score": round(h.score, 4),
                "excerpt": h.chunk.text[:600],
            }
            for h in hits
        ]
        return json.dumps({"hits": payload})

    def search_payments(
        self,
        payment_id: str | None = None,
        end_to_end_id: str | None = None,
        status: str | None = None,
        q: str | None = None,
    ) -> str:
        rows = self.store.search_payments(
            payment_id=payment_id or None,
            end_to_end_id=end_to_end_id or None,
            status=status or None,
            q=q or None,
        )
        return json.dumps({"count": len(rows), "payments": rows})

    def create_ticket(
        self,
        title: str,
        queue: str,
        body: str,
        related_payment_id: str | None = None,
    ) -> str:
        allowed = {"kyc", "scheme_ops", "recalls", "repair"}
        if queue not in allowed:
            return json.dumps({"error": f"queue must be one of {sorted(allowed)}"})
        ticket = self.store.create_ticket(
            title=title,
            queue=queue,
            body=body,
            related_payment_id=related_payment_id,
        )
        return json.dumps({"ok": True, "ticket": ticket})

    def create_transfer(
        self,
        originator: str,
        beneficiary: str,
        amount: float,
        end_to_end_id: str,
        currency: str = "USD",
    ) -> str:
        row = self.store.create_transfer(
            originator=originator,
            beneficiary=beneficiary,
            amount=float(amount),
            end_to_end_id=end_to_end_id,
            currency=currency or "USD",
        )
        return json.dumps({"ok": True, "transfer": row})

    def openai_tools(self) -> list[dict[str, Any]]:
        """JSON-schema tool list for chat-completions style APIs."""
        tools = []
        for spec in self._tools.values():
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": spec.parameters,
                    },
                }
            )
        return tools
