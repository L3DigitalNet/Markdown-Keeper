from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from markdownkeeper.api.server import run_api_server
from markdownkeeper.config import DEFAULT_CONFIG_PATH, load_config
from markdownkeeper.indexer.generator import generate_all_indexes
from markdownkeeper.links.validator import validate_links
from markdownkeeper.processor.parser import parse_markdown
from markdownkeeper.storage.repository import find_documents_by_concept, get_document, search_documents, semantic_search_documents, upsert_document
from markdownkeeper.storage.schema import initialize_database
from markdownkeeper.watcher.service import is_watchdog_available, watch_loop, watch_loop_watchdog
from markdownkeeper.storage.repository import find_documents_by_concept, get_document, search_documents, upsert_document
from markdownkeeper.storage.schema import initialize_database
from markdownkeeper.watcher.service import watch_loop
from markdownkeeper.config import DEFAULT_CONFIG_PATH, load_config
from markdownkeeper.processor.parser import parse_markdown
from markdownkeeper.storage.repository import get_document, search_documents, upsert_document
from markdownkeeper.storage.schema import initialize_database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mdkeeper", description="MarkdownKeeper CLI")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to markdownkeeper TOML config",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db", help="Initialize SQLite database")
    init_db.add_argument("--db-path", type=Path, default=None, help="Override DB path")

    subparsers.add_parser("show-config", help="Print resolved configuration as JSON")

    scan_file = subparsers.add_parser("scan-file", help="Parse and index a markdown file")
    scan_file.add_argument("file", type=Path, help="Markdown file to scan")
    scan_file.add_argument("--db-path", type=Path, default=None, help="Override DB path")
    scan_file.add_argument("--format", choices=["text", "json"], default="text")

    query = subparsers.add_parser("query", help="Search indexed documents")
    query.add_argument("query", type=str, help="Search phrase")
    query.add_argument("--db-path", type=Path, default=None, help="Override DB path")
    query.add_argument("--limit", type=int, default=10, help="Max results")
    query.add_argument("--format", choices=["text", "json"], default="text")
    query.add_argument("--include-content", action="store_true")
    query.add_argument("--max-tokens", type=int, default=200)
    query.add_argument("--search-mode", choices=["semantic", "lexical"], default="semantic")

    get_doc = subparsers.add_parser("get-doc", help="Retrieve document metadata by id")
    get_doc.add_argument("id", type=int, help="Document id")
    get_doc.add_argument("--db-path", type=Path, default=None, help="Override DB path")
    get_doc.add_argument("--format", choices=["text", "json"], default="json")
    get_doc.add_argument("--include-content", action="store_true")
    get_doc.add_argument("--max-tokens", type=int, default=None)
    get_doc.add_argument("--section", type=str, default=None)

    check_links = subparsers.add_parser("check-links", help="Validate indexed links")
    check_links.add_argument("--db-path", type=Path, default=None, help="Override DB path")
    check_links.add_argument("--format", choices=["text", "json"], default="text")


    find_concept = subparsers.add_parser("find-concept", help="Find docs by concept")
    find_concept.add_argument("concept", type=str)
    find_concept.add_argument("--db-path", type=Path, default=None, help="Override DB path")
    find_concept.add_argument("--limit", type=int, default=10)
    find_concept.add_argument("--format", choices=["text", "json"], default="json")

    build_index = subparsers.add_parser("build-index", help="Generate markdown index files")
    build_index.add_argument("--db-path", type=Path, default=None, help="Override DB path")
    build_index.add_argument("--output-dir", type=Path, default=Path("_index"))

    watch = subparsers.add_parser("watch", help="Watch docs and auto-index changes")
    watch.add_argument("--db-path", type=Path, default=None, help="Override DB path")
    watch.add_argument("--interval", type=float, default=1.0)
    watch.add_argument("--iterations", type=int, default=None)
    watch.add_argument("--mode", choices=["auto", "polling", "watchdog"], default="auto")
    watch.add_argument("--duration", type=float, default=None, help="Max seconds to run in watchdog mode")

    api = subparsers.add_parser("serve-api", help="Run JSON-RPC API server")
    api.add_argument("--db-path", type=Path, default=None, help="Override DB path")
    api.add_argument("--host", type=str, default=None)
    api.add_argument("--port", type=int, default=None)

    return parser


def _resolve_db_path(config_path: Path, db_path_override: Path | None) -> Path:
    config = load_config(config_path)
    return db_path_override or Path(config.storage.database_path)


def _handle_init_db(args: argparse.Namespace) -> int:
    db_path = _resolve_db_path(args.config, args.db_path)
    initialize_database(db_path)
    print(f"Initialized database at {db_path}")
    return 0


def _handle_show_config(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    payload = {
        "watch": {
            "roots": config.watch.roots,
            "extensions": config.watch.extensions,
            "debounce_ms": config.watch.debounce_ms,
        },
        "storage": {"database_path": config.storage.database_path},
        "api": {"host": config.api.host, "port": config.api.port},
    }
    print(json.dumps(payload, indent=2))
    return 0


def _handle_scan_file(args: argparse.Namespace) -> int:
    if not args.file.exists() or not args.file.is_file():
        print(f"File not found: {args.file}")
        return 1

    db_path = _resolve_db_path(args.config, args.db_path)
    initialize_database(db_path)

    content = args.file.read_text(encoding="utf-8")
    parsed = parse_markdown(content)
    document_id = upsert_document(db_path, args.file.resolve(), parsed)
    document_id = upsert_document(db_path, args.file, parsed)

    if args.format == "json":
        print(
            json.dumps(
                {
                    "document_id": document_id,
                    "path": str(args.file),
                    "title": parsed.title,
                    "headings": len(parsed.headings),
                    "links": len(parsed.links),
                    "token_estimate": parsed.token_estimate,
                },
                indent=2,
            )
        )
    else:
        print(
            f"Indexed {args.file} as id={document_id} title={parsed.title!r} "
            f"headings={len(parsed.headings)} links={len(parsed.links)}"
        )

    return 0


def _handle_query(args: argparse.Namespace) -> int:
    db_path = _resolve_db_path(args.config, args.db_path)
    initialize_database(db_path)
    if args.search_mode == "semantic":
        results = semantic_search_documents(db_path, args.query, limit=max(1, args.limit))
    else:
        results = search_documents(db_path, args.query, limit=max(1, args.limit))

    docs_payload: list[dict[str, object]] = []
    for result in results:
        payload = asdict(result)
        if args.include_content:
            detail = get_document(
                db_path,
                result.id,
                include_content=True,
                max_tokens=max(1, int(args.max_tokens or 200)),
            )
            payload["content"] = detail.content if detail else ""
        docs_payload.append(payload)

    if args.format == "json":
        print(json.dumps({"query": args.query, "search_mode": args.search_mode, "count": len(results), "documents": docs_payload}, indent=2))
    results = search_documents(db_path, args.query, limit=max(1, args.limit))

    if args.format == "json":
        print(
            json.dumps(
                {
                    "query": args.query,
                    "count": len(results),
                    "documents": [asdict(result) for result in results],
                },
                indent=2,
            )
        )
    else:
        if not results:
            print("No documents matched query")
        for result in results:
            print(f"[{result.id}] {result.title} ({result.path})")
    return 0


def _handle_get_doc(args: argparse.Namespace) -> int:
    db_path = _resolve_db_path(args.config, args.db_path)
    initialize_database(db_path)
    result = get_document(db_path, args.id, include_content=args.include_content, max_tokens=args.max_tokens, section=args.section)
    result = get_document(db_path, args.id)

    if result is None:
        print(f"Document id={args.id} not found")
        return 1

    if args.format == "json":
        print(json.dumps(asdict(result), indent=2))
    else:
        print(f"[{result.id}] {result.title}")
        print(f"Path: {result.path}")
        print(f"Summary: {result.summary}")
        print(f"Headings: {len(result.headings)} Links: {len(result.links)}")
        if args.include_content and result.content:
            print("Content:")
            print(result.content)

    return 0


def _handle_check_links(args: argparse.Namespace) -> int:
    db_path = _resolve_db_path(args.config, args.db_path)
    initialize_database(db_path)
    results = validate_links(db_path)
    broken = [asdict(item) for item in results if item.status != "ok"]

    if args.format == "json":
        print(
            json.dumps(
                {
                    "checked": len(results),
                    "broken": len(broken),
                    "broken_links": broken,
                },
                indent=2,
            )
        )
    else:
        print(f"Checked {len(results)} links; broken={len(broken)}")
        for item in broken:
            print(f"- [{item['link_id']}] {item['target']}")

    return 0 if not broken else 1


def _handle_find_concept(args: argparse.Namespace) -> int:
    db_path = _resolve_db_path(args.config, args.db_path)
    initialize_database(db_path)
    results = find_documents_by_concept(db_path, args.concept, limit=max(1, args.limit))
    if args.format == "json":
        print(json.dumps({"concept": args.concept, "count": len(results), "documents": [asdict(item) for item in results]}, indent=2))
    else:
        for result in results:
            print(f"[{result.id}] {result.title} ({result.path})")
    return 0


def _handle_build_index(args: argparse.Namespace) -> int:
    db_path = _resolve_db_path(args.config, args.db_path)
    initialize_database(db_path)
    outs = generate_all_indexes(db_path, args.output_dir)
    for out in outs:
        print(f"Wrote index: {out}")
    return 0


def _handle_watch(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    db_path = _resolve_db_path(args.config, args.db_path)
    initialize_database(db_path)

    roots = [Path(root) for root in config.watch.roots]
    mode = args.mode
    if mode == "auto":
        mode = "watchdog" if is_watchdog_available() else "polling"

    if mode == "watchdog":
        result = watch_loop_watchdog(
            database_path=db_path,
            roots=roots,
            extensions=config.watch.extensions,
            debounce_s=max(0.05, args.interval),
            duration_s=args.duration,
        )
    else:
        result = watch_loop(
            database_path=db_path,
            roots=roots,
            extensions=config.watch.extensions,
            interval_s=max(0.1, args.interval),
            iterations=args.iterations,
        )
    print(
        f"watch summary mode={mode} created={result.created} modified={result.modified} deleted={result.deleted}"
    )
    return 0


def _handle_serve_api(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    db_path = _resolve_db_path(args.config, args.db_path)
    initialize_database(db_path)
    host = args.host or config.api.host
    port = args.port or config.api.port
    print(f"Starting API server on {host}:{port}")
    run_api_server(host, port, db_path)

    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "init-db": _handle_init_db,
        "show-config": _handle_show_config,
        "scan-file": _handle_scan_file,
        "query": _handle_query,
        "get-doc": _handle_get_doc,
        "check-links": _handle_check_links,
        "find-concept": _handle_find_concept,
        "build-index": _handle_build_index,
        "watch": _handle_watch,
        "serve-api": _handle_serve_api,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.error(f"Unknown command: {args.command}")
        return 2

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
