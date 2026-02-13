from __future__ import annotations

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any

from markdownkeeper.storage.repository import get_document, search_documents


def _rpc_success(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "result": result, "id": request_id}


def _rpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": request_id}


def build_handler(database_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def _write_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._write_json(200, {"status": "ok"})
                return
            self._write_json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                req = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._write_json(400, _rpc_error(None, -32700, "invalid json"))
                return

            request_id = req.get("id")
            method = req.get("method")
            params = req.get("params") or {}

            if self.path == "/api/v1/query" and method == "semantic_query":
                query = str(params.get("query", "")).strip()
                max_results = int(params.get("max_results", 10))
                docs = search_documents(database_path, query, limit=max(1, max_results))
                self._write_json(
                    200,
                    _rpc_success(
                        request_id,
                        {
                            "query": query,
                            "documents": [asdict(item) for item in docs],
                            "count": len(docs),
                        },
                    ),
                )
                return

            if self.path == "/api/v1/get_doc" and method == "get_document":
                document_id = int(params.get("document_id", 0))
                doc = get_document(database_path, document_id)
                if doc is None:
                    self._write_json(404, _rpc_error(request_id, -32004, "document not found"))
                else:
                    self._write_json(200, _rpc_success(request_id, asdict(doc)))
                return

            if self.path == "/api/v1/find_concept" and method == "find_by_concept":
                concept = str(params.get("concept", "")).strip()
                max_results = int(params.get("max_results", 10))
                docs = find_documents_by_concept(database_path, concept, limit=max(1, max_results))
                self._write_json(
                    200,
                    _rpc_success(
                        request_id,
                        {
                            "concept": concept,
                            "documents": [asdict(item) for item in docs],
                            "count": len(docs),
                        },
                    ),
                )
                return

            self._write_json(404, _rpc_error(request_id, -32601, "method not found"))

        def log_message(self, fmt: str, *args: Any) -> None:  # silence tests
            return

    return Handler


def run_api_server(host: str, port: int, database_path: Path) -> None:
    server = ThreadingHTTPServer((host, port), build_handler(database_path))
    server.serve_forever()
