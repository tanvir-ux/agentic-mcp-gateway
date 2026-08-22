from __future__ import annotations

import json
from pathlib import Path

from agentic_mcp_gateway.embeddings import HashingEmbedder
from agentic_mcp_gateway.rag import Retriever
from agentic_mcp_gateway.tools import ToolRegistry


def test_hashing_embedder_normalized() -> None:
    emb = HashingEmbedder(dims=64)
    vecs = emb.embed(["kyc review", "kyc review", "swift status request"])
    assert vecs.shape == (3, 64)
    # identical inputs → identical vectors
    assert abs(float((vecs[0] * vecs[1]).sum()) - 1.0) < 1e-5
    # related-ish queries should not be orthogonal in this toy space
    assert float((vecs[0] * vecs[2]).sum()) < 0.99


def test_retriever_finds_kyc_chunk(repo_root: Path) -> None:
    retriever = Retriever(repo_root / "docs" / "kb", dims=256)
    hits = retriever.search("when a payment is held for kyc review", top_k=3)
    assert hits
    blob = " ".join(h.chunk.text.lower() + h.chunk.heading.lower() for h in hits)
    assert "kyc" in blob


def test_retrieve_docs_tool(registry: ToolRegistry) -> None:
    raw = registry.call("retrieve_docs", query="interbank status request UETR", top_k=2)
    payload = json.loads(raw)
    assert payload["hits"]
    assert "doc_id" in payload["hits"][0]
