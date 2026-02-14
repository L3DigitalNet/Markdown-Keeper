from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import json
import sqlite3
import tempfile
import unittest

from markdownkeeper.processor.parser import parse_markdown
from markdownkeeper.storage.repository import (
    find_documents_by_concept,
    get_document,
    search_documents,
    _compute_text_embedding,
    embedding_coverage,
    regenerate_embeddings,
    semantic_search_documents,
    upsert_document,
)
    semantic_search_documents,
    upsert_document,
)
from markdownkeeper.storage.repository import get_document, search_documents, upsert_document
from markdownkeeper.storage.schema import initialize_database


class RepositoryTests(unittest.TestCase):
    def test_upsert_document_inserts_and_replaces_child_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            file_path = Path(tmp) / "docs" / "a.md"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            initialize_database(db_path)

            doc1 = parse_markdown("---\ntags: x\ncategory: guides\n---\n# A\nSee [x](./x.md)")
            doc2 = parse_markdown("---\ntags: y\ncategory: runbooks\n---\n# A2\nSee [y](https://example.com)\n## B")
            doc1 = parse_markdown("# A\nSee [x](./x.md)")
            doc2 = parse_markdown("# A2\nSee [y](https://example.com)\n## B")

            id1 = upsert_document(db_path, file_path, doc1)
            id2 = upsert_document(db_path, file_path, doc2)
            self.assertEqual(id1, id2)

            with sqlite3.connect(db_path) as connection:
                heading_count = connection.execute(
                    "SELECT COUNT(*) FROM headings WHERE document_id=?", (id1,)
                ).fetchone()[0]
                link_count = connection.execute(
                    "SELECT COUNT(*) FROM links WHERE document_id=?", (id1,)
                ).fetchone()[0]
                title = connection.execute(
                    "SELECT title FROM documents WHERE id=?", (id1,)
                ).fetchone()[0]

            self.assertEqual(heading_count, 2)
            self.assertEqual(link_count, 1)
            self.assertEqual(title, "A2")

    def test_search_documents_returns_expected_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "deployment.md"
            parsed = parse_markdown("# Deployment\nContainer rollout guide")
            upsert_document(db_path, file_path, parsed)

            results = search_documents(db_path, "Deploy", limit=5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].title, "Deployment")

    def test_get_document_returns_detail_and_none_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "guide.md"
            parsed = parse_markdown(
                "---\ntags: ops\nconcepts: docker\ncategory: guides\n---\n# Guide\nSee [ext](https://example.com)"
            )
            doc_id = upsert_document(db_path, file_path, parsed)

            detail = get_document(db_path, doc_id, include_content=True, max_tokens=50)
            parsed = parse_markdown("# Guide\nSee [ext](https://example.com)")
            doc_id = upsert_document(db_path, file_path, parsed)

            detail = get_document(db_path, doc_id)
            self.assertIsNotNone(detail)
            assert detail is not None
            self.assertEqual(detail.id, doc_id)
            self.assertEqual(detail.title, "Guide")
            self.assertEqual(detail.category, "guides")
            self.assertIn("ops", detail.tags)
            self.assertIn("docker", detail.concepts)
            self.assertEqual(len(detail.links), 1)
            self.assertTrue(len(detail.content) > 0)
            self.assertEqual(len(detail.links), 1)

            missing = get_document(db_path, 9999)
            self.assertIsNone(missing)


    def test_get_document_content_respects_token_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "budget.md"
            parsed = parse_markdown("# Budget\n\none two three four five six")
            doc_id = upsert_document(db_path, file_path, parsed)

            detail = get_document(db_path, doc_id, include_content=True, max_tokens=3)
            self.assertIsNotNone(detail)
            assert detail is not None
            self.assertEqual(detail.content.split(), ["#", "Budget", "one"])

    def test_find_documents_by_concept(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "k8s.md"
            parsed = parse_markdown("---\nconcepts: kubernetes\n---\n# Cluster")
            upsert_document(db_path, file_path, parsed)

            results = find_documents_by_concept(db_path, "kubernetes", limit=5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].title, "Cluster")


    def test_semantic_search_documents_uses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "semantic.md"
            parsed = parse_markdown("# Kubernetes Operations\nThis guide explains kubernetes cluster rollout.")
            upsert_document(db_path, file_path, parsed)

            first = semantic_search_documents(db_path, "kubernetes rollout", limit=5)
            second = semantic_search_documents(db_path, "kubernetes rollout", limit=5)
            self.assertEqual(len(first), 1)
            self.assertEqual(len(second), 1)

            with sqlite3.connect(db_path) as connection:
                row = connection.execute(
                    "SELECT hit_count FROM query_cache WHERE query_text = ?",
                    ("kubernetes rollout",),
                ).fetchone()
            self.assertIsNotNone(row)
            assert row is not None
            self.assertGreaterEqual(int(row[0]), 1)


    def test_upsert_document_generates_embedding_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "embed.md"
            parsed = parse_markdown("# Embed\nvector metadata test")
            doc_id = upsert_document(db_path, file_path, parsed)

            with sqlite3.connect(db_path) as connection:
                row = connection.execute(
                    "SELECT embedding, model_name FROM embeddings WHERE document_id = ?",
                    (doc_id,),
                ).fetchone()
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(str(row[1]), "token-hash-v1")
            self.assertTrue(len(str(row[0])) > 2)

    def test_semantic_search_can_use_embedding_when_lexical_overlap_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "doc.md"
            parsed = parse_markdown("# Title\nCompletely unrelated text")
            doc_id = upsert_document(db_path, file_path, parsed)

            query = "kubernetes"
            query_embedding = _compute_text_embedding(query)
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    "UPDATE embeddings SET embedding = ? WHERE document_id = ?",
                    (json.dumps(query_embedding), doc_id),
                )
                connection.execute(
                    "UPDATE documents SET title = ?, summary = ?, content = ? WHERE id = ?",
                    ("Alpha", "Beta", "Gamma", doc_id),
                )
                connection.commit()

            results = semantic_search_documents(db_path, query, limit=5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].id, doc_id)


    def test_regenerate_embeddings_and_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "ops.md"
            parsed = parse_markdown("# Ops\nrunbook")
            upsert_document(db_path, file_path, parsed)

            coverage_before = embedding_coverage(db_path)
            self.assertEqual(coverage_before["documents"], 1)
            self.assertEqual(coverage_before["embedded"], 1)

            with sqlite3.connect(db_path) as connection:
                connection.execute("UPDATE embeddings SET embedding = ''")
                connection.commit()

            coverage_missing = embedding_coverage(db_path)
            self.assertEqual(coverage_missing["missing"], 1)

            regenerated = regenerate_embeddings(db_path)
            self.assertEqual(regenerated, 1)
            coverage_after = embedding_coverage(db_path)
            self.assertEqual(coverage_after["missing"], 0)

if __name__ == "__main__":
    unittest.main()
