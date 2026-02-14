from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import unittest
from unittest import mock

from markdownkeeper.query.embeddings import compute_embedding, cosine_similarity


class EmbeddingTests(unittest.TestCase):
    def test_compute_embedding_falls_back_without_sentence_transformers(self) -> None:
        with mock.patch.dict(sys.modules, {"sentence_transformers": None}):
            vector, model = compute_embedding("hello world")
        self.assertEqual(model, "token-hash-v1")
        self.assertGreater(len(vector), 0)

    def test_cosine_similarity_bounds(self) -> None:
        same = cosine_similarity([1.0, 0.0], [1.0, 0.0])
        orth = cosine_similarity([1.0, 0.0], [0.0, 1.0])
        self.assertGreaterEqual(same, 0.99)
        self.assertLessEqual(orth, 0.01)


if __name__ == "__main__":
    unittest.main()
