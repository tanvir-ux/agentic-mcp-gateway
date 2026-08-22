"""In-memory RAG over markdown files using cosine similarity."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from agentic_mcp_gateway.embeddings import Embedder, HashingEmbedder


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    path: str
    text: str
    heading: str


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def _chunk_markdown(path: Path) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8")
    parts: list[tuple[str, list[str]]] = []
    heading = path.stem
    buf: list[str] = []
    for line in raw.splitlines():
        if line.startswith("#"):
            if buf:
                parts.append((heading, buf))
                buf = []
            heading = line.lstrip("#").strip() or path.stem
        else:
            buf.append(line)
    if buf:
        parts.append((heading, buf))

    chunks: list[Chunk] = []
    for i, (head, lines) in enumerate(parts):
        text = "\n".join(lines).strip()
        if len(text) < 40:
            continue
        chunks.append(
            Chunk(
                doc_id=f"{path.stem}:{i}",
                path=str(path),
                text=text,
                heading=head,
            )
        )
    if not chunks and raw.strip():
        chunks.append(Chunk(f"{path.stem}:0", str(path), raw.strip(), path.stem))
    return chunks


class Retriever:
    def __init__(self, kb_dir: Path, embedder: Embedder | None = None, dims: int = 256) -> None:
        self.kb_dir = kb_dir
        self.embedder = embedder or HashingEmbedder(dims=dims)
        self.chunks: list[Chunk] = []
        self._matrix = np.zeros((0, dims), dtype=np.float32)
        self.rebuild()

    def rebuild(self) -> None:
        files = sorted(self.kb_dir.glob("*.md")) if self.kb_dir.exists() else []
        self.chunks = []
        for path in files:
            self.chunks.extend(_chunk_markdown(path))
        if self.chunks:
            self._matrix = self.embedder.embed([f"{c.heading}\n{c.text}" for c in self.chunks])
        else:
            self._matrix = np.zeros((0, getattr(self.embedder, "dims", 256)), dtype=np.float32)

    def search(self, query: str, top_k: int = 3) -> list[Hit]:
        if not self.chunks:
            return []
        q = self.embedder.embed([query])[0]
        scores = self._matrix @ q
        k = min(top_k, len(self.chunks))
        idxs = np.argpartition(-scores, kth=k - 1)[:k]
        idxs = idxs[np.argsort(-scores[idxs])]
        return [Hit(chunk=self.chunks[int(i)], score=float(scores[int(i)])) for i in idxs]
