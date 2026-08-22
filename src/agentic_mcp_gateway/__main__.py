"""python -m agentic_mcp_gateway  → HTTP app."""

from agentic_mcp_gateway.config import get_settings
from agentic_mcp_gateway.http_app import app


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
