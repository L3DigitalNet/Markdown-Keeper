from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from markdownkeeper.query.faiss_index import FaissIndex, is_faiss_available


class FaissIndexTests(unittest.TestCase):
    def test_build_and_search_returns_nearest(self) -> None:
        index = FaissIndex()
        embeddings = [
            (1, [1.0, 0.0, 0.0]),
            (2, [0.0, 1.0, 0.0]),
            (3, [0.9, 0.1, 0.0]),
        ]
        index.build(embeddings)
        results = index.search([1.0, 0.0, 0.0], k=2)
        ids = [doc_id for doc_id, _ in results]
        self.assertIn(1, ids)
        self.assertIn(3, ids)

    def test_search_empty_index_returns_empty(self) -> None:
        index = FaissIndex()
        index.build([])
        results = index.search([1.0, 0.0], k=5)
        self.assertEqual(results, [])

    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.index"
            index = FaissIndex()
            embeddings = [(1, [1.0, 0.0]), (2, [0.0, 1.0])]
            index.build(embeddings)
            index.save(path)

            loaded = FaissIndex()
            loaded.load(path)
            results = loaded.search([1.0, 0.0], k=1)
            self.assertEqual(results[0][0], 1)

    def test_is_faiss_available_returns_bool(self) -> None:
        self.assertIsInstance(is_faiss_available(), bool)

    def test_k_larger_than_index_returns_all(self) -> None:
        index = FaissIndex()
        index.build([(1, [1.0, 0.0]), (2, [0.0, 1.0])])
        results = index.search([1.0, 0.0], k=100)
        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
