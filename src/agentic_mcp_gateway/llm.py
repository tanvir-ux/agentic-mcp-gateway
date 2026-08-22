"""LLM backends. FakeLLM is the default so recruiters never need a vendor key."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from agentic_mcp_gateway.config import Settings


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMTurn:
    content: str | None
    tool_calls: list[ToolCall]


class LLM(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMTurn: ...


class FakeLLM:
    """Deterministic planner for demos and pytest.

    Heuristics:
    - payment ids like PMT-#### → search_payments
    - words ticket/hold/stuck/kyc after a payment observation → create_ticket
    - policy / SLA / SWIFT / KYC questions → retrieve_docs
    - otherwise a short final answer
    """

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMTurn:
        user_text = _last_user(messages)
        tool_names_used = _tool_names_from_messages(messages)

        payment_id = _find_payment_id(user_text) or _find_payment_id(_all_text(messages))

        if payment_id and "search_payments" not in tool_names_used:
            return LLMTurn(
                content=None,
                tool_calls=[
                    ToolCall("search_payments", {"payment_id": payment_id}),
                ],
            )

        if _wants_docs(user_text) and "retrieve_docs" not in tool_names_used:
            return LLMTurn(
                content=None,
                tool_calls=[ToolCall("retrieve_docs", {"query": user_text, "top_k": 3})],
            )

        if (
            payment_id
            and _wants_ticket(user_text, messages)
            and "create_ticket" not in tool_names_used
        ):
            queue = "kyc" if "kyc" in user_text.lower() or "kyc_review" in _all_text(messages).lower() else "scheme_ops"
            return LLMTurn(
                content=None,
                tool_calls=[
                    ToolCall(
                        "create_ticket",
                        {
                            "title": f"Investigate {payment_id}",
                            "queue": queue,
                            "body": f"Auto-opened from agent session for {payment_id}.",
                            "related_payment_id": payment_id,
                        },
                    )
                ],
            )

        summary = _summarize(messages, user_text)
        return LLMTurn(content=summary, tool_calls=[])


def _last_user(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return str(m.get("content") or "")
    return ""


def _all_text(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for m in messages:
        c = m.get("content")
        if c:
            parts.append(str(c))
    return "\n".join(parts)


def _tool_names_from_messages(messages: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for m in messages:
        if m.get("role") == "tool" and m.get("name"):
            names.add(str(m["name"]))
        for tc in m.get("tool_calls") or []:
            names.add(str(tc.get("name") or tc.get("function", {}).get("name") or ""))
    names.discard("")
    return names


def _find_payment_id(text: str) -> str | None:
    m = re.search(r"\bPMT-\d+\b", text, re.I)
    return m.group(0).upper() if m else None


def _wants_docs(text: str) -> bool:
    keys = ("policy", "kyc", "swift", "sla", "message", "lifecycle", "what is", "explain")
    t = text.lower()
    return any(k in t for k in keys)


def _wants_ticket(user_text: str, messages: list[dict[str, Any]]) -> bool:
    blob = (user_text + "\n" + _all_text(messages)).lower()
    if any(w in blob for w in ("ticket", "stuck", "held", "hold", "investigate", "open a case")):
        return True
    return "kyc_review" in blob or '"status": "held"' in blob or '"status": "in_flight"' in blob


def _summarize(messages: list[dict[str, Any]], user_text: str) -> str:
    observations: list[str] = []
    for m in messages:
        if m.get("role") == "tool":
            observations.append(f"{m.get('name')}: {m.get('content')}")
    if observations:
        return (
            "Completed the ops workflow.\n\n"
            + "\n".join(observations[-3:])
            + "\n\nThis answer was produced by FakeLLM (no vendor key)."
        )
    return (
        f"I can search payments, retrieve ops docs, and open tickets. "
        f"Ask about a payment id (e.g. PMT-1002) or a policy topic. Query was: {user_text}"
    )


class OpenAILLM:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMTurn:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("httpx required for LLM_PROVIDER=llm") from exc

        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is empty; use LLM_PROVIDER=fake")

        body = {
            "model": self.settings.openai_model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
            json=body,
            timeout=60.0,
        )
        resp.raise_for_status()
        choice = resp.json()["choices"][0]["message"]
        calls: list[ToolCall] = []
        for tc in choice.get("tool_calls") or []:
            fn = tc["function"]
            args = fn.get("arguments") or "{}"
            if isinstance(args, str):
                args = json.loads(args or "{}")
            calls.append(ToolCall(name=fn["name"], arguments=args))
        return LLMTurn(content=choice.get("content"), tool_calls=calls)


def build_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "llm":
        return OpenAILLM(settings)
    return FakeLLM()
