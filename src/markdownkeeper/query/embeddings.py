from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1}


def _hash_embedding(text: str, dimensions: int = 64) -> list[float]:
    vector = [0.0] * dimensions
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:2], "big") % dimensions
        vector[bucket] += 1.0

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def _normalize(vector: Iterable[float]) -> list[float]:
    values = [float(item) for item in vector]
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        return values
    return [value / norm for value in values]


def compute_embedding(text: str, model_name: str = "all-MiniLM-L6-v2") -> tuple[list[float], str]:
    """Compute an embedding using sentence-transformers when available; fallback to hash baseline."""
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception:
        return _hash_embedding(text), "token-hash-v1"

    try:
        model = SentenceTransformer(model_name)
        vector = model.encode(text or "", normalize_embeddings=True)
        return _normalize(vector), model_name
    except Exception:
        return _hash_embedding(text), "token-hash-v1"


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left or not right:
        return 0.0
    return float(sum(a * b for a, b in zip(left, right)))
