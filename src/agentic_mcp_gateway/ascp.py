"""Action-bound authorization (ALLOW / DENY / HITL) for MCP tool calls.

Research spike for: digest-locked HITL — approving digest A must not authorize
mutated args (parameter swap). Request-side gate; response policy can layer later.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any


POLICY_VERSION = "ascp-v1"


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    HITL = "HITL"


# Read / search tools execute without HITL. Side-effect tools need digest approval.
DEFAULT_POLICY: dict[str, Decision] = {
    "retrieve_docs": Decision.ALLOW,
    "search_payments": Decision.ALLOW,
    "create_ticket": Decision.HITL,
    "create_transfer": Decision.HITL,
}


def canonical_json(obj: Any) -> str:
    """Stable JSON for hashing (sorted keys, no whitespace ambiguity)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def action_digest(
    *,
    tool: str,
    args: dict[str, Any],
    agent_id: str = "default",
    policy_version: str = POLICY_VERSION,
) -> str:
    payload = {
        "agent_id": agent_id,
        "tool": tool,
        "args": args,
        "policy_version": policy_version,
    }
    raw = canonical_json(payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass
class AuthzResult:
    decision: Decision
    digest: str
    message: str
    executed: bool = False
    output: str | None = None


class HitlStore:
    """In-memory one-shot approvals keyed by action digest."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._approved: set[str] = set()
        self._denied: set[str] = set()

    def approve(self, digest: str) -> None:
        with self._lock:
            self._denied.discard(digest)
            self._approved.add(digest)

    def deny(self, digest: str) -> None:
        with self._lock:
            self._approved.discard(digest)
            self._denied.add(digest)

    def consume_approval(self, digest: str) -> bool:
        """Return True once if digest was approved; consume so it cannot be reused."""
        with self._lock:
            if digest in self._denied:
                return False
            if digest in self._approved:
                self._approved.discard(digest)
                return True
            return False

    def is_denied(self, digest: str) -> bool:
        with self._lock:
            return digest in self._denied


class AscpGateway:
    def __init__(
        self,
        policy: dict[str, Decision] | None = None,
        hitl: HitlStore | None = None,
        agent_id: str = "default",
    ) -> None:
        self.policy = dict(policy or DEFAULT_POLICY)
        self.hitl = hitl or HitlStore()
        self.agent_id = agent_id

    def classify(self, tool: str) -> Decision:
        return self.policy.get(tool, Decision.DENY)

    def evaluate(self, tool: str, args: dict[str, Any]) -> AuthzResult:
        digest = action_digest(tool=tool, args=args, agent_id=self.agent_id)
        decision = self.classify(tool)
        if decision is Decision.ALLOW:
            return AuthzResult(Decision.ALLOW, digest, "policy allow")
        if decision is Decision.DENY:
            return AuthzResult(Decision.DENY, digest, "policy deny")
        # HITL
        if self.hitl.is_denied(digest):
            return AuthzResult(Decision.DENY, digest, "HITL explicitly denied this digest")
        if self.hitl.consume_approval(digest):
            return AuthzResult(Decision.ALLOW, digest, "HITL approved exact digest")
        return AuthzResult(
            Decision.HITL,
            digest,
            "HITL required: approve this digest before the tool may run",
        )
