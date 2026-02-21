"""Optional FAISS-backed vector index for accelerated similarity search.

Used by repository.py to rebuild a FAISS index after embedding regeneration.
Falls back to brute-force cosine similarity when faiss-cpu is not installed.
If this module's API changes, update the import in storage/repository.py.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

try:
    import faiss  # type: ignore[import-untyped]
    import numpy as np  # type: ignore[import-untyped]
except ImportError:
    faiss = None
    np = None


def is_faiss_available() -> bool:
    return faiss is not None and np is not None


class FaissIndex:
    """Optional FAISS-backed vector index. Falls back to brute-force when FAISS not installed."""

    def __init__(self) -> None:
        self._index: object | None = None
        self._id_map: list[int] = []
        self._embeddings: list[tuple[int, list[float]]] = []
        self._dimensions: int = 0

    def build(self, embeddings: list[tuple[int, list[float]]]) -> None:
        self._embeddings = list(embeddings)
        if not embeddings:
            self._index = None
            self._id_map = []
            self._dimensions = 0
            return

        self._dimensions = len(embeddings[0][1])
        self._id_map = [doc_id for doc_id, _ in embeddings]

        if is_faiss_available():
            vectors = np.array([vec for _, vec in embeddings], dtype=np.float32)
            faiss.normalize_L2(vectors)
            index = faiss.IndexFlatIP(self._dimensions)
            index.add(vectors)
            self._index = index
        else:
            self._index = None

    def search(self, query_vector: list[float], k: int = 10) -> list[tuple[int, float]]:
        if not self._id_map:
            return []

        k = min(k, len(self._id_map))

        if is_faiss_available() and self._index is not None:
            q = np.array([query_vector], dtype=np.float32)
            faiss.normalize_L2(q)
            distances, indices = self._index.search(q, k)
            results: list[tuple[int, float]] = []
            for i in range(k):
                idx = int(indices[0][i])
                if idx < 0 or idx >= len(self._id_map):
                    continue
                results.append((self._id_map[idx], float(distances[0][i])))
            return results

        # Brute-force fallback
        return self._brute_force_search(query_vector, k)

    def _brute_force_search(self, query_vector: list[float], k: int) -> list[tuple[int, float]]:
        q_norm = self._normalize(query_vector)
        scored: list[tuple[float, int]] = []
        for doc_id, vec in self._embeddings:
            v_norm = self._normalize(vec)
            sim = sum(a * b for a, b in zip(q_norm, v_norm))
            scored.append((sim, doc_id))
        scored.sort(reverse=True)
        return [(doc_id, score) for score, doc_id in scored[:k]]

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if is_faiss_available() and self._index is not None:
            faiss.write_index(self._index, str(path))
            meta_path = path.with_suffix(".meta.json")
            meta_path.write_text(
                json.dumps({"id_map": self._id_map, "dimensions": self._dimensions}),
                encoding="utf-8",
            )
        else:
            # Save as JSON for brute-force fallback
            data = {
                "id_map": self._id_map,
                "dimensions": self._dimensions,
                "embeddings": [[doc_id, vec] for doc_id, vec in self._embeddings],
            }
            path.with_suffix(".json").write_text(json.dumps(data), encoding="utf-8")

    def load(self, path: Path) -> None:
        if is_faiss_available() and path.exists():
            self._index = faiss.read_index(str(path))
            meta_path = path.with_suffix(".meta.json")
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                self._id_map = meta["id_map"]
                self._dimensions = meta["dimensions"]
            return

        # Fallback: load from JSON
        json_path = path.with_suffix(".json")
        if json_path.exists():
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self._id_map = data["id_map"]
            self._dimensions = data["dimensions"]
            self._embeddings = [(e[0], e[1]) for e in data["embeddings"]]
