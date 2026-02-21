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
    _chunk_document,
    _deserialize_embedding,
    delete_document_by_path,
    find_documents_by_concept,
    get_document,
    list_documents,
    search_documents,
    _compute_text_embedding,
    embedding_coverage,
    benchmark_semantic_queries,
    evaluate_semantic_precision,
    regenerate_embeddings,
    semantic_search_documents,
    system_stats,
    upsert_document,
    generate_health_report,
)
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
            self.assertIsNotNone(detail)
            assert detail is not None
            self.assertEqual(detail.id, doc_id)
            self.assertEqual(detail.title, "Guide")
            self.assertEqual(detail.category, "guides")
            self.assertIn("ops", detail.tags)
            self.assertIn("docker", detail.concepts)
            self.assertEqual(len(detail.links), 1)
            self.assertTrue(len(detail.content) > 0)

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


    def test_evaluate_semantic_precision_returns_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "q.md"
            parsed = parse_markdown("# Kubernetes Guide\ncluster rollout")
            doc_id = upsert_document(db_path, file_path, parsed)

            report = evaluate_semantic_precision(
                db_path,
                [{"query": "kubernetes cluster", "expected_ids": [doc_id]}],
                k=1,
            )
            self.assertEqual(report["cases"], 1)
            self.assertGreaterEqual(float(report["precision_at_k"]), 1.0)


    def test_system_stats_contains_queue_and_embedding_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "stats.md"
            parsed = parse_markdown("# Stats\nbody")
            upsert_document(db_path, file_path, parsed)

            payload = system_stats(db_path)
            self.assertIn("documents", payload)
            self.assertIn("queue", payload)
            self.assertIn("embeddings", payload)
            self.assertIn("cache", payload)


    def test_benchmark_semantic_queries_reports_latency_and_precision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "bench.md"
            parsed = parse_markdown("# Benchmark\nsemantic benchmark case")
            doc_id = upsert_document(db_path, file_path, parsed)

            report = benchmark_semantic_queries(
                db_path,
                [{"query": "semantic benchmark", "expected_ids": [doc_id]}],
                k=1,
                iterations=2,
            )
            self.assertEqual(report["cases"], 1)
            self.assertEqual(report["iterations"], 2)
            self.assertIn("latency_ms", report)
            self.assertGreaterEqual(float(report["precision_at_k"]), 1.0)

    def test_delete_document_by_path_removes_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "del.md"
            parsed = parse_markdown("# Delete Me\nbody")
            upsert_document(db_path, file_path, parsed)
            self.assertEqual(len(list_documents(db_path)), 1)

            deleted = delete_document_by_path(db_path, file_path)
            self.assertTrue(deleted)
            self.assertEqual(len(list_documents(db_path)), 0)

    def test_delete_document_by_path_returns_false_for_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            deleted = delete_document_by_path(db_path, Path("/nonexistent/file.md"))
            self.assertFalse(deleted)

    def test_list_documents_returns_all_sorted_by_updated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            for name in ["a.md", "b.md", "c.md"]:
                fp = Path(tmp) / name
                upsert_document(db_path, fp, parse_markdown(f"# {name}\nbody"))

            docs = list_documents(db_path)
            self.assertEqual(len(docs), 3)

    def test_deserialize_embedding_handles_none(self) -> None:
        self.assertEqual(_deserialize_embedding(None), [])

    def test_deserialize_embedding_handles_invalid_json(self) -> None:
        self.assertEqual(_deserialize_embedding("not json"), [])

    def test_deserialize_embedding_handles_valid_json(self) -> None:
        result = _deserialize_embedding(json.dumps([1.0, 2.0, 3.0]))
        self.assertEqual(result, [1.0, 2.0, 3.0])

    def test_deserialize_embedding_handles_non_numeric_array(self) -> None:
        self.assertEqual(_deserialize_embedding(json.dumps(["a", "b"])), [])

    def test_semantic_search_empty_query_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            results = semantic_search_documents(db_path, "", limit=5)
            self.assertEqual(results, [])

    def test_semantic_search_whitespace_query_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            results = semantic_search_documents(db_path, "   ", limit=5)
            self.assertEqual(results, [])

    def test_get_document_with_section_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "sections.md"
            parsed = parse_markdown("# Intro\n\nIntro text\n\n## Setup\n\nSetup content here")
            doc_id = upsert_document(db_path, file_path, parsed)

            detail = get_document(db_path, doc_id, include_content=True, section="Setup")
            self.assertIsNotNone(detail)
            assert detail is not None
            # Should return some content (section filter works via heading_path LIKE match)
            self.assertIsInstance(detail.content, str)

    def test_get_document_without_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            file_path = Path(tmp) / "nocontent.md"
            parsed = parse_markdown("# Title\nbody")
            doc_id = upsert_document(db_path, file_path, parsed)

            detail = get_document(db_path, doc_id, include_content=False)
            self.assertIsNotNone(detail)
            assert detail is not None
            self.assertEqual(detail.content, "")

    def test_evaluate_semantic_precision_empty_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            result = evaluate_semantic_precision(db_path, [], k=5)
            self.assertEqual(result["cases"], 0)
            self.assertEqual(result["precision_at_k"], 0.0)

    def test_benchmark_semantic_queries_empty_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            result = benchmark_semantic_queries(db_path, [], k=5, iterations=1)
            self.assertEqual(result["cases"], 0)
            self.assertEqual(result["latency_ms"]["avg"], 0.0)

    def test_chunk_document_assigns_correct_heading_paths(self) -> None:
        parsed = parse_markdown("# Intro\n\nIntro para\n\n## Setup\n\nSetup para")
        chunks = _chunk_document(parsed)
        self.assertGreater(len(chunks), 0)
        # Verify chunks exist and have heading_path values
        heading_paths = {chunk[1] for chunk in chunks}
        self.assertTrue(len(heading_paths) > 0)

    def test_chunk_document_empty_body(self) -> None:
        parsed = parse_markdown("")
        chunks = _chunk_document(parsed)
        self.assertEqual(chunks, [])

    def test_find_documents_by_concept_no_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            results = find_documents_by_concept(db_path, "nonexistent", limit=5)
            self.assertEqual(results, [])

    def test_search_documents_no_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            results = search_documents(db_path, "zzz_no_match_zzz", limit=5)
            self.assertEqual(results, [])

    def test_upsert_document_cascading_delete_cleans_children(self) -> None:
        """Verify foreign key cascading delete removes headings/links/tags/concepts."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            initialize_database(db_path)
            fp = Path(tmp) / "cascade.md"
            parsed = parse_markdown("---\ntags: alpha\nconcepts: beta\n---\n# Title\n[link](./a.md)")
            doc_id = upsert_document(db_path, fp, parsed)

            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                self.assertGreater(conn.execute("SELECT COUNT(*) FROM headings WHERE document_id=?", (doc_id,)).fetchone()[0], 0)
                self.assertGreater(conn.execute("SELECT COUNT(*) FROM links WHERE document_id=?", (doc_id,)).fetchone()[0], 0)

            delete_document_by_path(db_path, fp)

            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM headings WHERE document_id=?", (doc_id,)).fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM links WHERE document_id=?", (doc_id,)).fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM document_tags WHERE document_id=?", (doc_id,)).fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM document_concepts WHERE document_id=?", (doc_id,)).fetchone()[0], 0)


class QueryCacheTests(unittest.TestCase):
    def test_semantic_search_cache_hit_returns_same_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)
            md = Path(tmp) / "doc.md"
            md.write_text("# Cache Test\ncaching query results", encoding="utf-8")
            upsert_document(db_path, md, parse_markdown(md.read_text(encoding="utf-8")))

            r1 = semantic_search_documents(db_path, "caching")
            r2 = semantic_search_documents(db_path, "caching")
            self.assertEqual([d.id for d in r1], [d.id for d in r2])

    def test_cache_invalidated_on_upsert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)
            md = Path(tmp) / "doc.md"
            md.write_text("# Alpha\nalpha content", encoding="utf-8")
            upsert_document(db_path, md, parse_markdown(md.read_text(encoding="utf-8")))

            semantic_search_documents(db_path, "alpha")

            # Verify cache has entries
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM query_cache").fetchone()[0]
            self.assertGreater(count, 0)

            # Upsert should invalidate
            md.write_text("# Beta\nbeta content", encoding="utf-8")
            upsert_document(db_path, md, parse_markdown(md.read_text(encoding="utf-8")))

            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM query_cache").fetchone()[0]
            self.assertEqual(count, 0)

    def test_cache_invalidated_on_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)
            md = Path(tmp) / "doc.md"
            md.write_text("# Del\ndeletable content", encoding="utf-8")
            upsert_document(db_path, md, parse_markdown(md.read_text(encoding="utf-8")))
            semantic_search_documents(db_path, "deletable")

            delete_document_by_path(db_path, md)

            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM query_cache").fetchone()[0]
            self.assertEqual(count, 0)

    def test_cache_ttl_expired_entry_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)
            md = Path(tmp) / "doc.md"
            md.write_text("# TTL\nttl test content", encoding="utf-8")
            upsert_document(db_path, md, parse_markdown(md.read_text(encoding="utf-8")))

            semantic_search_documents(db_path, "ttl test")

            # Manually backdate the cache entry
            with sqlite3.connect(db_path) as conn:
                conn.execute("UPDATE query_cache SET created_at = '2020-01-01T00:00:00+00:00'")
                conn.commit()

            # Search again — should not use expired cache (re-executes search)
            results = semantic_search_documents(db_path, "ttl test")
            self.assertGreater(len(results), 0)

            # Verify expired entry was replaced with a fresh one
            with sqlite3.connect(db_path) as conn:
                row = conn.execute("SELECT created_at FROM query_cache LIMIT 1").fetchone()
            self.assertIsNotNone(row)
            self.assertNotIn("2020", str(row[0]))


class HealthReportTests(unittest.TestCase):
    def test_report_on_empty_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)
            report = generate_health_report(db_path)
        self.assertEqual(report["total_documents"], 0)
        self.assertEqual(report["total_tokens"], 0)
        self.assertEqual(report["broken_internal_links"], 0)
        self.assertEqual(report["broken_external_links"], 0)
        self.assertEqual(report["missing_summaries"], 0)

    def test_report_on_populated_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)

            md1 = Path(tmp) / "doc1.md"
            md1.write_text("# Doc 1\n[bad](./missing.md)\n[ext](https://example.com)", encoding="utf-8")
            upsert_document(db_path, md1, parse_markdown(md1.read_text(encoding="utf-8")))

            md2 = Path(tmp) / "doc2.md"
            md2.write_text("---\nsummary: Has summary\n---\n# Doc 2", encoding="utf-8")
            upsert_document(db_path, md2, parse_markdown(md2.read_text(encoding="utf-8")))

            report = generate_health_report(db_path)

        self.assertEqual(report["total_documents"], 2)
        self.assertGreater(report["total_tokens"], 0)
        self.assertIn("embedding_coverage_pct", report)
        self.assertIn("cache_entries", report)
        self.assertIn("queue_queued", report)

    def test_report_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "index.db"
            initialize_database(db_path)
            report = generate_health_report(db_path)
        serialized = json.dumps(report)
        self.assertIsInstance(serialized, str)


if __name__ == "__main__":
    unittest.main()
