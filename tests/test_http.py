from __future__ import annotations

from fastapi.testclient import TestClient

from agentic_mcp_gateway.http_app import app


def test_health() -> None:
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "retrieve_docs" in body["tools"]
