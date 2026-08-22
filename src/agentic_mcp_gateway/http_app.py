"""Thin FastAPI wrapper for recruiter demos: /health and /chat."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from agentic_mcp_gateway import __version__
from agentic_mcp_gateway.agent import OpsAgent
from agentic_mcp_gateway.config import get_settings
from agentic_mcp_gateway.tools import ToolRegistry

app = FastAPI(
    title="Agentic MCP Gateway",
    version=__version__,
    description="Demo ops agent with MCP-shaped tools. FakeLLM by default.",
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    reply: str
    steps: list[dict[str, Any]]


@lru_cache(maxsize=1)
def _agent() -> OpsAgent:
    settings = get_settings()
    registry = ToolRegistry(settings)
    return OpsAgent(registry=registry, settings=settings)


@app.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "ok": True,
        "version": __version__,
        "llm_provider": settings.llm_provider,
        "tools": _agent().registry.names(),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    trace = _agent().run(req.message)
    return ChatResponse(reply=trace.final, steps=trace.steps)


@app.get("/tools")
def tools() -> dict[str, Any]:
    return {"tools": _agent().registry.openai_tools()}
