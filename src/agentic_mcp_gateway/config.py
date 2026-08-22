"""Runtime settings. Defaults keep the demo key-free."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    # src/agentic_mcp_gateway/config.py -> repo root
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    llm_provider: str = "fake"  # fake | llm
    openai_model: str = "gpt-4o-mini"
    host: str = "0.0.0.0"
    port: int = 8080
    kb_dir: Path = _repo_root() / "docs" / "kb"
    data_dir: Path = _repo_root() / "data"
    max_agent_steps: int = 6
    rag_top_k: int = 3
    embedding_dims: int = 256

    @property
    def sqlite_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "ops.sqlite"


def get_settings() -> Settings:
    return Settings()
