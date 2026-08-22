from __future__ import annotations

from pathlib import Path

import pytest

from agentic_mcp_gateway.config import Settings
from agentic_mcp_gateway.store import OpsStore
from agentic_mcp_gateway.tools import ToolRegistry


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path: Path, repo_root: Path) -> Settings:
    return Settings(
        llm_provider="fake",
        openai_api_key="",
        kb_dir=repo_root / "docs" / "kb",
        data_dir=tmp_path / "data",
        max_agent_steps=6,
    )


@pytest.fixture
def store() -> OpsStore:
    return OpsStore(":memory:")


@pytest.fixture
def registry(settings: Settings, store: OpsStore) -> ToolRegistry:
    return ToolRegistry(settings=settings, store=store)
