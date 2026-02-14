from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import json
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen

from http.server import ThreadingHTTPServer

from markdownkeeper.api.server import build_handler
from markdownkeeper.processor.parser import parse_markdown
from markdownkeeper.storage.repository import upsert_document
from markdownkeeper.storage.schema import initialize_database


class ApiTests(unittest.TestCase):
    def test_query_get_doc_and_find_concept_endpoints(self) -> None:
    def test_query_and_get_doc_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / ".markdownkeeper" / "index.db"
            initialize_database(db)
            doc = root / "doc.md"
            doc.write_text("---\nconcepts: kubernetes\n---\n# API Doc\nhello", encoding="utf-8")
            doc.write_text("# API Doc\nhello", encoding="utf-8")
            doc_id = upsert_document(db, doc, parse_markdown(doc.read_text(encoding="utf-8")))

            server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(db))
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                req1 = Request(
                    f"http://127.0.0.1:{port}/api/v1/query",
                    data=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "semantic_query",
                            "params": {"query": "API", "max_results": 5, "include_content": True, "max_tokens": 20},
                            "params": {"query": "API", "max_results": 5},
                            "id": 1,
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req1, timeout=5) as resp:  # noqa: S310
                    payload = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(payload["result"]["count"], 1)
                self.assertIn("content", payload["result"]["documents"][0])

                req2 = Request(
                    f"http://127.0.0.1:{port}/api/v1/get_doc",
                    data=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "get_document",
                            "params": {"document_id": doc_id, "include_content": True, "max_tokens": 20},
                            "params": {"document_id": doc_id},
                            "id": 2,
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req2, timeout=5) as resp:  # noqa: S310
                    payload2 = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(payload2["result"]["title"], "API Doc")
                self.assertIn("content", payload2["result"])

                req3 = Request(
                    f"http://127.0.0.1:{port}/api/v1/find_concept",
                    data=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "find_by_concept",
                            "params": {"concept": "kubernetes", "max_results": 5},
                            "id": 3,
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req3, timeout=5) as resp:  # noqa: S310
                    payload3 = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(payload3["result"]["count"], 1)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
