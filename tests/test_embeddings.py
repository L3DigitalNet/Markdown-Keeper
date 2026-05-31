from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import math
import unittest
from unittest import mock

from markdownkeeper.query.embeddings import (
    _hash_embedding,
    _normalize,
    _tokenize,
    compute_embedding,
    cosine_similarity,
    is_model_embedding_available,
)


class EmbeddingTests(unittest.TestCase):
    def test_compute_embedding_falls_back_without_sentence_transformers(self) -> None:
        # Clear the model cache too: a warm cache (from another test loading the real
        # model when sentence-transformers is installed) would bypass the import at
        # _load_model and defeat the sys.modules patch.
        from markdownkeeper.query import embeddings

        with mock.patch.dict(embeddings._MODEL_CACHE, {}, clear=True), \
                mock.patch.dict(sys.modules, {"sentence_transformers": None}):
            vector, model = compute_embedding("hello world")
        self.assertEqual(model, "token-hash-v1")
        self.assertGreater(len(vector), 0)

    def test_cosine_similarity_bounds(self) -> None:
        same = cosine_similarity([1.0, 0.0], [1.0, 0.0])
        orth = cosine_similarity([1.0, 0.0], [0.0, 1.0])
        self.assertGreaterEqual(same, 0.99)
        self.assertLessEqual(orth, 0.01)

    def test_cosine_similarity_different_lengths_returns_zero(self) -> None:
        self.assertEqual(cosine_similarity([1.0, 0.0], [1.0]), 0.0)

    def test_cosine_similarity_empty_vectors_returns_zero(self) -> None:
        self.assertEqual(cosine_similarity([], []), 0.0)
        self.assertEqual(cosine_similarity([1.0], []), 0.0)
        self.assertEqual(cosine_similarity([], [1.0]), 0.0)

    def test_tokenize_filters_short_tokens(self) -> None:
        tokens = _tokenize("I am a big fox")
        self.assertNotIn("i", tokens)
        self.assertNotIn("a", tokens)
        self.assertIn("am", tokens)
        self.assertIn("big", tokens)
        self.assertIn("fox", tokens)

    def test_tokenize_lowercases_and_extracts_alphanumeric(self) -> None:
        tokens = _tokenize("Hello-World! Test123")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)
        self.assertIn("test123", tokens)

    def test_hash_embedding_returns_normalized_vector(self) -> None:
        vector = _hash_embedding("hello world", dimensions=64)
        self.assertEqual(len(vector), 64)
        norm = math.sqrt(sum(v * v for v in vector))
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_hash_embedding_empty_text_returns_zero_vector(self) -> None:
        vector = _hash_embedding("", dimensions=64)
        self.assertEqual(len(vector), 64)
        self.assertTrue(all(v == 0.0 for v in vector))

    def test_hash_embedding_deterministic(self) -> None:
        v1 = _hash_embedding("kubernetes cluster")
        v2 = _hash_embedding("kubernetes cluster")
        self.assertEqual(v1, v2)

    def test_normalize_zero_vector_unchanged(self) -> None:
        zero = [0.0, 0.0, 0.0]
        result = _normalize(zero)
        self.assertEqual(result, zero)

    def test_normalize_produces_unit_vector(self) -> None:
        result = _normalize([3.0, 4.0])
        norm = math.sqrt(sum(v * v for v in result))
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_is_model_embedding_available_returns_false_without_library(self) -> None:
        with mock.patch.dict(sys.modules, {"sentence_transformers": None}):
            self.assertFalse(is_model_embedding_available("nonexistent-model"))

    def test_compute_embedding_empty_text_returns_valid_vector(self) -> None:
        # Force the deterministic hash path so this is stable whether or not
        # sentence-transformers is installed (real-model behavior is covered by
        # tests/integration).
        from markdownkeeper.query import embeddings

        with mock.patch.object(embeddings, "_load_model", return_value=None):
            vector, model = compute_embedding("")
        self.assertEqual(model, "token-hash-v1")
        self.assertEqual(len(vector), 64)


if __name__ == "__main__":
    unittest.main()
