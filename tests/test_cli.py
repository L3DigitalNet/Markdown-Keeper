from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import contextlib
import io
import json
import tempfile
import unittest
from unittest import mock

from markdownkeeper.cli.main import main


class CliTests(unittest.TestCase):
    def test_show_config_outputs_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "markdownkeeper.toml"
            cfg.write_text("[api]\nport=9001\n", encoding="utf-8")

            buf = io.StringIO()
            with mock.patch("sys.argv", ["mdkeeper", "--config", str(cfg), "show-config"]):
                with contextlib.redirect_stdout(buf):
                    code = main()

        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["api"]["port"], 9001)

    def test_scan_file_indexes_document_and_outputs_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            md_file = Path(tmp) / "doc.md"
            md_file.write_text("# My Doc\nSee [site](https://example.com)", encoding="utf-8")

            buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                [
                    "mdkeeper",
                    "scan-file",
                    str(md_file),
                    "--db-path",
                    str(db_path),
                    "--format",
                    "json",
                ],
            ):
                with contextlib.redirect_stdout(buf):
                    code = main()

            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["title"], "My Doc")
            self.assertEqual(payload["links"], 1)
            self.assertTrue(db_path.exists())

    def test_scan_file_missing_file_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            md_file = Path(tmp) / "missing.md"
            buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "scan-file", str(md_file), "--db-path", str(db_path)],
            ):
                with contextlib.redirect_stdout(buf):
                    code = main()
            self.assertEqual(code, 1)
            self.assertIn("File not found", buf.getvalue())

    def test_query_and_get_doc_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            md_file = Path(tmp) / "deploy-guide.md"
            md_file.write_text("# Deployment Guide\nUse docker compose.", encoding="utf-8")

            with mock.patch(
                "sys.argv", ["mdkeeper", "scan-file", str(md_file), "--db-path", str(db_path)]
            ):
                main()

            query_buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                [
                    "mdkeeper",
                    "query",
                    "Deployment",
                    "--db-path",
                    str(db_path),
                    "--format",
                    "json",
                ],
            ):
                with contextlib.redirect_stdout(query_buf):
                    query_code = main()

            self.assertEqual(query_code, 0)
            query_payload = json.loads(query_buf.getvalue())
            self.assertEqual(query_payload["count"], 1)
            doc_id = query_payload["documents"][0]["id"]

            get_buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                [
                    "mdkeeper",
                    "get-doc",
                    str(doc_id),
                    "--db-path",
                    str(db_path),
                    "--format",
                    "json",
                ],
            ):
                with contextlib.redirect_stdout(get_buf):
                    get_code = main()

            self.assertEqual(get_code, 0)
            get_payload = json.loads(get_buf.getvalue())
            self.assertEqual(get_payload["title"], "Deployment Guide")

    def test_query_text_format_with_no_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "query", "zzz", "--db-path", str(db_path), "--limit", "0"],
            ):
                with contextlib.redirect_stdout(buf):
                    code = main()
            self.assertEqual(code, 0)
            self.assertIn("No documents matched query", buf.getvalue())

    def test_get_doc_not_found_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "get-doc", "999", "--db-path", str(db_path)],
            ):
                with contextlib.redirect_stdout(buf):
                    code = main()

            self.assertEqual(code, 1)
            self.assertIn("not found", buf.getvalue())


    def test_get_doc_include_content_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            md_file = Path(tmp) / "doc.md"
            md_file.write_text("# Title\n\nParagraph one.\n\nParagraph two.", encoding="utf-8")
            with mock.patch("sys.argv", ["mdkeeper", "scan-file", str(md_file), "--db-path", str(db_path)]):
                main()

            qbuf = io.StringIO()
            with mock.patch("sys.argv", ["mdkeeper", "query", "Title", "--db-path", str(db_path), "--format", "json"]):
                with contextlib.redirect_stdout(qbuf):
                    main()
            doc_id = json.loads(qbuf.getvalue())["documents"][0]["id"]

            out = io.StringIO()
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "get-doc", str(doc_id), "--db-path", str(db_path), "--format", "json", "--include-content", "--max-tokens", "10"],
            ):
                with contextlib.redirect_stdout(out):
                    code = main()
            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue())
            self.assertIn("content", payload)

    def test_get_doc_text_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            md_file = Path(tmp) / "guide.md"
            md_file.write_text("# Guide\nsummary line", encoding="utf-8")
            with mock.patch(
                "sys.argv", ["mdkeeper", "scan-file", str(md_file), "--db-path", str(db_path)]
            ):
                main()

            query_buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "query", "Guide", "--db-path", str(db_path), "--format", "json"],
            ):
                with contextlib.redirect_stdout(query_buf):
                    main()
            doc_id = json.loads(query_buf.getvalue())["documents"][0]["id"]

            get_buf = io.StringIO()
            with mock.patch(
                "sys.argv", ["mdkeeper", "get-doc", str(doc_id), "--db-path", str(db_path), "--format", "text"]
            ):
                with contextlib.redirect_stdout(get_buf):
                    code = main()

            self.assertEqual(code, 0)
            self.assertIn("Summary:", get_buf.getvalue())


    def test_check_links_returns_nonzero_when_broken(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            docs = Path(tmp) / "docs"
            docs.mkdir(parents=True, exist_ok=True)
            md_file = docs / "doc.md"
            md_file.write_text("# Doc\n[bad](./missing.md)", encoding="utf-8")

            with mock.patch(
                "sys.argv", ["mdkeeper", "scan-file", str(md_file), "--db-path", str(db_path)]
            ):
                main()

            buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "check-links", "--db-path", str(db_path), "--format", "json"],
            ):
                with contextlib.redirect_stdout(buf):
                    code = main()

            self.assertEqual(code, 1)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["checked"], 1)
            self.assertEqual(payload["broken"], 1)



    def test_find_concept_returns_indexed_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            md_file = Path(tmp) / "doc.md"
            md_file.write_text("---\nconcepts: kubernetes\n---\n# Concept Doc", encoding="utf-8")
            with mock.patch("sys.argv", ["mdkeeper", "scan-file", str(md_file), "--db-path", str(db_path)]):
                main()

            out = io.StringIO()
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "find-concept", "kubernetes", "--db-path", str(db_path), "--format", "json"],
            ):
                with contextlib.redirect_stdout(out):
                    code = main()

            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["count"], 1)

    def test_build_index_writes_master_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            md_file = Path(tmp) / "doc.md"
            md_file.write_text("# Doc", encoding="utf-8")
            with mock.patch("sys.argv", ["mdkeeper", "scan-file", str(md_file), "--db-path", str(db_path)]):
                main()

            out_dir = Path(tmp) / "_index"
            buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "build-index", "--db-path", str(db_path), "--output-dir", str(out_dir)],
            ):
                with contextlib.redirect_stdout(buf):
                    code = main()

            self.assertEqual(code, 0)
            self.assertTrue((out_dir / "master.md").exists())
            self.assertTrue((out_dir / "by-concept.md").exists())

    def test_watch_one_iteration_indexes_existing_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            docs = Path(tmp) / "docs"
            docs.mkdir(parents=True, exist_ok=True)
            md_file = docs / "doc.md"
            md_file.write_text("# Watched", encoding="utf-8")
            cfg = Path(tmp) / "markdownkeeper.toml"
            cfg.write_text(
                f'[watch]\nroots=["{docs.as_posix()}"]\nextensions=[".md"]\n',
                encoding="utf-8",
            )

            with mock.patch(
                "sys.argv",
                [
                    "mdkeeper",
                    "--config",
                    str(cfg),
                    "watch",
                    "--db-path",
                    str(db_path),
                    "--iterations",
                    "1",
                    "--interval",
                    "0.1",
                ],
            ):
                code = main()

            self.assertEqual(code, 0)
            qbuf = io.StringIO()
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "query", "Watched", "--db-path", str(db_path), "--format", "json"],
            ):
                with contextlib.redirect_stdout(qbuf):
                    main()
            self.assertEqual(json.loads(qbuf.getvalue())["count"], 1)

    def test_init_db_creates_database_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            buf = io.StringIO()
            with mock.patch("sys.argv", ["mdkeeper", "init-db", "--db-path", str(db_path)]):
                with contextlib.redirect_stdout(buf):
                    code = main()

            self.assertEqual(code, 0)
            self.assertTrue(db_path.exists())
            self.assertIn("Initialized database", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
