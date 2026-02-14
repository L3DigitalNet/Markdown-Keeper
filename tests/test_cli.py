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


    def test_watch_auto_uses_polling_when_watchdog_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            docs = Path(tmp) / "docs"
            docs.mkdir(parents=True, exist_ok=True)
            cfg = Path(tmp) / "markdownkeeper.toml"
            cfg.write_text(f'''[watch]
roots=["{docs.as_posix()}"]
extensions=[".md"]
''', encoding="utf-8")

            with mock.patch("markdownkeeper.cli.main.is_watchdog_available", return_value=False), mock.patch(
                "markdownkeeper.cli.main.watch_loop"
            ) as watch_loop_mock:
                watch_loop_mock.return_value.created = 0
                watch_loop_mock.return_value.modified = 0
                watch_loop_mock.return_value.deleted = 0
                with mock.patch(
                    "sys.argv",
                    ["mdkeeper", "--config", str(cfg), "watch", "--db-path", str(db_path), "--iterations", "1"],
                ):
                    code = main()

            self.assertEqual(code, 0)
            watch_loop_mock.assert_called_once()

    def test_watch_auto_uses_watchdog_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            docs = Path(tmp) / "docs"
            docs.mkdir(parents=True, exist_ok=True)
            cfg = Path(tmp) / "markdownkeeper.toml"
            cfg.write_text(f'''[watch]
roots=["{docs.as_posix()}"]
extensions=[".md"]
''', encoding="utf-8")

            with mock.patch("markdownkeeper.cli.main.is_watchdog_available", return_value=True), mock.patch(
                "markdownkeeper.cli.main.watch_loop_watchdog"
            ) as watch_watchdog_mock:
                watch_watchdog_mock.return_value.created = 0
                watch_watchdog_mock.return_value.modified = 0
                watch_watchdog_mock.return_value.deleted = 0
                with mock.patch(
                    "sys.argv",
                    ["mdkeeper", "--config", str(cfg), "watch", "--db-path", str(db_path), "--duration", "0.1"],
                ):
                    code = main()

            self.assertEqual(code, 0)
            watch_watchdog_mock.assert_called_once()

    def test_query_semantic_mode_outputs_mode_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            md_file = Path(tmp) / "doc.md"
            md_file.write_text("# Semantic Search\ncluster rollout and kubernetes", encoding="utf-8")
            with mock.patch("sys.argv", ["mdkeeper", "scan-file", str(md_file), "--db-path", str(db_path)]):
                main()

            out = io.StringIO()
            with mock.patch(
                "sys.argv",
                [
                    "mdkeeper",
                    "query",
                    "kubernetes",
                    "--db-path",
                    str(db_path),
                    "--format",
                    "json",
                    "--search-mode",
                    "semantic",
                ],
            ):
                with contextlib.redirect_stdout(out):
                    code = main()

            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["search_mode"], "semantic")
            self.assertEqual(payload["count"], 1)


    def test_write_systemd_generates_unit_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "systemd"
            buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                [
                    "mdkeeper",
                    "write-systemd",
                    "--output-dir",
                    str(out_dir),
                    "--exec-path",
                    "/opt/mdkeeper",
                    "--config-path",
                    "/etc/mdk.toml",
                ],
            ):
                with contextlib.redirect_stdout(buf):
                    code = main()

            self.assertEqual(code, 0)
            self.assertTrue((out_dir / "markdownkeeper.service").exists())
            self.assertTrue((out_dir / "markdownkeeper-api.service").exists())
            self.assertIn("Wrote unit:", buf.getvalue())



    def test_embeddings_generate_and_status_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            md_file = Path(tmp) / "emb.md"
            md_file.write_text("# Embeddings\nhello world", encoding="utf-8")

            with mock.patch("sys.argv", ["mdkeeper", "scan-file", str(md_file), "--db-path", str(db_path)]):
                main()

            gen_buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "embeddings-generate", "--db-path", str(db_path)],
            ):
                with contextlib.redirect_stdout(gen_buf):
                    gen_code = main()
            self.assertEqual(gen_code, 0)
            self.assertIn("Generated embeddings", gen_buf.getvalue())

            status_buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "embeddings-status", "--db-path", str(db_path), "--format", "json"],
            ):
                with contextlib.redirect_stdout(status_buf):
                    status_code = main()
            self.assertEqual(status_code, 0)
            payload = json.loads(status_buf.getvalue())
            self.assertEqual(payload["documents"], 1)
            self.assertEqual(payload["missing"], 0)


    def test_embeddings_eval_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            md_file = Path(tmp) / "eval.md"
            md_file.write_text("# Kubernetes Notes\ncluster setup", encoding="utf-8")

            with mock.patch("sys.argv", ["mdkeeper", "scan-file", str(md_file), "--db-path", str(db_path)]):
                main()

            query_buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "query", "kubernetes", "--db-path", str(db_path), "--format", "json"],
            ):
                with contextlib.redirect_stdout(query_buf):
                    main()
            doc_id = int(json.loads(query_buf.getvalue())["documents"][0]["id"])

            cases_file = Path(tmp) / "cases.json"
            cases_file.write_text(
                json.dumps([{"query": "kubernetes", "expected_ids": [doc_id]}]),
                encoding="utf-8",
            )

            out = io.StringIO()
            with mock.patch(
                "sys.argv",
                [
                    "mdkeeper",
                    "embeddings-eval",
                    str(cases_file),
                    "--db-path",
                    str(db_path),
                    "--k",
                    "1",
                    "--format",
                    "json",
                ],
            ):
                with contextlib.redirect_stdout(out):
                    code = main()

            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["cases"], 1)
            self.assertGreaterEqual(float(payload["precision_at_k"]), 1.0)


    def test_semantic_benchmark_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            md_file = Path(tmp) / "bench.md"
            md_file.write_text("# Bench\nsemantic benchmark", encoding="utf-8")
            with mock.patch("sys.argv", ["mdkeeper", "scan-file", str(md_file), "--db-path", str(db_path)]):
                main()

            query_buf = io.StringIO()
            with mock.patch(
                "sys.argv",
                ["mdkeeper", "query", "semantic", "--db-path", str(db_path), "--format", "json"],
            ):
                with contextlib.redirect_stdout(query_buf):
                    main()
            doc_id = int(json.loads(query_buf.getvalue())["documents"][0]["id"])

            cases_file = Path(tmp) / "benchmark-cases.json"
            cases_file.write_text(
                json.dumps([{"query": "semantic", "expected_ids": [doc_id]}]),
                encoding="utf-8",
            )

            out = io.StringIO()
            with mock.patch(
                "sys.argv",
                [
                    "mdkeeper",
                    "semantic-benchmark",
                    str(cases_file),
                    "--db-path",
                    str(db_path),
                    "--k",
                    "1",
                    "--iterations",
                    "2",
                    "--format",
                    "json",
                ],
            ):
                with contextlib.redirect_stdout(out):
                    code = main()
            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["cases"], 1)
            self.assertEqual(payload["iterations"], 2)
            self.assertIn("latency_ms", payload)

    def test_stats_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / ".markdownkeeper" / "index.db"
            md_file = Path(tmp) / "stats.md"
            md_file.write_text("# Stats\nhello", encoding="utf-8")
            with mock.patch("sys.argv", ["mdkeeper", "scan-file", str(md_file), "--db-path", str(db_path)]):
                main()

            out = io.StringIO()
            with mock.patch("sys.argv", ["mdkeeper", "stats", "--db-path", str(db_path), "--format", "json"]):
                with contextlib.redirect_stdout(out):
                    code = main()
            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue())
            self.assertIn("documents", payload)
            self.assertIn("queue", payload)
            self.assertIn("embeddings", payload)

    def test_daemon_commands_use_pid_file_and_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pid_file = Path(tmp) / "watch.pid"
            with mock.patch("markdownkeeper.cli.main.start_background", return_value=1234) as start_mock:
                out = io.StringIO()
                with mock.patch(
                    "sys.argv",
                    ["mdkeeper", "daemon-start", "watch", "--pid-file", str(pid_file)],
                ):
                    with contextlib.redirect_stdout(out):
                        code = main()
                self.assertEqual(code, 0)
                self.assertIn("pid=1234", out.getvalue())
                start_mock.assert_called_once()

            with mock.patch("markdownkeeper.cli.main.status_background", return_value=(True, 1234)):
                out = io.StringIO()
                with mock.patch(
                    "sys.argv",
                    ["mdkeeper", "daemon-status", "watch", "--pid-file", str(pid_file)],
                ):
                    with contextlib.redirect_stdout(out):
                        code = main()
                self.assertEqual(code, 0)
                self.assertIn("running", out.getvalue())

            with mock.patch("markdownkeeper.cli.main.stop_background", return_value=True):
                out = io.StringIO()
                with mock.patch(
                    "sys.argv",
                    ["mdkeeper", "daemon-stop", "watch", "--pid-file", str(pid_file)],
                ):
                    with contextlib.redirect_stdout(out):
                        code = main()
                self.assertEqual(code, 0)
                self.assertIn("Stopped", out.getvalue())

            with mock.patch("markdownkeeper.cli.main.restart_background", return_value=2345) as restart_mock:
                out = io.StringIO()
                with mock.patch(
                    "sys.argv",
                    ["mdkeeper", "daemon-restart", "watch", "--pid-file", str(pid_file)],
                ):
                    with contextlib.redirect_stdout(out):
                        code = main()
                self.assertEqual(code, 0)
                self.assertIn("Restarted", out.getvalue())
                restart_mock.assert_called_once()

            with mock.patch("markdownkeeper.cli.main.reload_background", return_value=True) as reload_mock:
                out = io.StringIO()
                with mock.patch(
                    "sys.argv",
                    ["mdkeeper", "daemon-reload", "watch", "--pid-file", str(pid_file)],
                ):
                    with contextlib.redirect_stdout(out):
                        code = main()
                self.assertEqual(code, 0)
                self.assertIn("Reloaded", out.getvalue())
                reload_mock.assert_called_once()

            with mock.patch("markdownkeeper.cli.main.status_background", return_value=(False, None)):
                with mock.patch(
                    "sys.argv",
                    ["mdkeeper", "daemon-status", "watch", "--pid-file", str(pid_file)],
                ):
                    code = main()
                self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
