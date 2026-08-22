"""Demo embeddings: hashed character n-grams + L2-normalized numpy vectors.

This is intentionally not a production encoder. Swap HashingEmbedder for a
sentence-transformer or vendor API; Retriever only depends on Embedder.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import numpy as np


class Embedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return shape (n, dims) float32, L2-normalized rows."""


class HashingEmbedder(Embedder):
    """Feature-hashing of character 3-grams. Deterministic, no model download."""

    def __init__(self, dims: int = 256) -> None:
        if dims < 32:
            raise ValueError("dims must be >= 32")
        self.dims = dims

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dims), dtype=np.float32)
        for i, text in enumerate(texts):
            out[i] = self._vector(text)
        return out

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dims, dtype=np.float32)
        blob = f" {text.lower()} "
        for n in (2, 3, 4):
            for j in range(max(0, len(blob) - n + 1)):
                gram = blob[j : j + n]
                h = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(h[:4], "little") % self.dims
                sign = 1.0 if h[4] % 2 == 0 else -1.0
                vec[idx] += sign
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec
