"""Digest-bound HITL: approve A, mutate args → DENY."""

from __future__ import annotations

import json

from agentic_mcp_gateway.ascp import AscpGateway, Decision, action_digest
from agentic_mcp_gateway.tools import ToolRegistry


def test_digest_stable_under_key_order() -> None:
    a = action_digest(tool="create_transfer", args={"amount": 10, "beneficiary": "A", "originator": "B", "end_to_end_id": "E1"})
    b = action_digest(tool="create_transfer", args={"end_to_end_id": "E1", "originator": "B", "beneficiary": "A", "amount": 10})
    assert a == b


def test_read_tools_allow_without_hitl(settings, store) -> None:
    reg = ToolRegistry(settings=settings, store=store, enforce_ascp=True)
    out = json.loads(reg.call("search_payments", payment_id="PMT-1001"))
    assert out["count"] == 1
    assert "ascp" not in out


def test_write_requires_hitl(settings, store) -> None:
    reg = ToolRegistry(settings=settings, store=store, enforce_ascp=True)
    out = json.loads(
        reg.call(
            "create_transfer",
            originator="Acme",
            beneficiary="Victim",
            amount=100.0,
            end_to_end_id="E-1",
            currency="USD",
        )
    )
    assert out["ascp"]["decision"] == "HITL"
    digest = out["ascp"]["digest"]
    assert len(digest) == 64


def test_approve_then_parameter_swap_denied(settings, store) -> None:
    """Critical paper claim: HITL on digest A must not authorize amount+1."""
    reg = ToolRegistry(settings=settings, store=store, enforce_ascp=True)
    args_ok = {
        "originator": "Acme",
        "beneficiary": "Contoso",
        "amount": 100.0,
        "end_to_end_id": "E-SWAP",
        "currency": "USD",
    }
    digest_a = reg.preview_digest("create_transfer", **args_ok)
    reg.ascp.hitl.approve(digest_a)

    # Mutated amount — different digest, no approval
    swapped = json.loads(reg.call("create_transfer", **{**args_ok, "amount": 101.0}))
    assert swapped["ascp"]["decision"] in {"HITL", "DENY"}
    assert swapped["ascp"]["digest"] != digest_a
    assert "ok" not in swapped

    # Exact args — consumes approval and executes once
    ok = json.loads(reg.call("create_transfer", **args_ok))
    assert ok["ok"] is True
    assert ok["transfer"]["amount"] == 100.0

    # Replay same digest without new approval → HITL again
    again = json.loads(reg.call("create_transfer", **args_ok))
    assert again["ascp"]["decision"] == "HITL"


def test_create_ticket_hitl_digest(settings, store) -> None:
    reg = ToolRegistry(settings=settings, store=store, enforce_ascp=True)
    args = {"title": "Hold", "queue": "kyc", "body": "review", "related_payment_id": "PMT-1002"}
    d = reg.preview_digest("create_ticket", **args)
    reg.ascp.hitl.approve(d)
    out = json.loads(reg.call("create_ticket", **args))
    assert out["ok"] is True
