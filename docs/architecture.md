# Architecture

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

MarkdownKeeper is an LLM-accessible markdown documentation database. It indexes `.md` files into SQLite, supports semantic and lexical search, and exposes results via CLI and JSON-RPC API. Designed to run as a persistent service (watcher + API daemon) that LLM agents query programmatically.

## Build & Test Commands

Requires Python >= 3.10. On 3.10, `tomli` is auto-installed; 3.11+ uses stdlib `tomllib`.

```bash
# Install (editable, from repo root)
pip install -e .

# Install with optional ML dependencies
pip install -e ".[embeddings]"       # sentence-transformers
pip install -e ".[faiss]"            # faiss-cpu + numpy

# Run all tests (174 tests, ~12s)
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_parser.py

# Run a single test method
python -m pytest tests/test_cli.py::CliTests::test_scan_file_indexes_document_and_outputs_json

# Tests also work via unittest directly
python -m unittest tests/test_schema.py
```

```bash
# Quick dev workflow: create a DB, scan a file, query it
mdkeeper init-db --db-path .markdownkeeper/index.db
mdkeeper scan-file README.md --db-path .markdownkeeper/index.db --format json
mdkeeper query "markdown" --db-path .markdownkeeper/index.db --format json
```

```bash
# Integration tests (devcontainer only — requires sentence-transformers + faiss-cpu)
bash scripts/run-integration-tests.sh

# Run integration tests directly with pytest
python -m pytest tests/integration/ -v --tb=short
```

No linter or type checker is configured in CI. Tests use `unittest.TestCase` (not pytest fixtures) and create temporary databases via `tempfile.TemporaryDirectory`. Integration tests in `tests/integration/` require the devcontainer environment with ML dependencies.

## Git Conventions

Single branch (`main`), no branch protection configured. No CI test pipeline beyond the devcontainer prebuild workflow.

## Architecture

### Data Flow

```
markdown files -> parser -> ParsedDocument -> upsert_document() -> SQLite
                                                  |
                                          compute_embedding() -> embeddings table
                                          _chunk_document()   -> document_chunks table
```

The parser (`processor/parser.py`) extracts headings, links, frontmatter, tags, concepts, and a content hash. The repository (`storage/repository.py`) persists everything into SQLite and computes embeddings at upsert time.

### Embedding Strategy

Two-tier fallback in `query/embeddings.py`:
1. **sentence-transformers** (all-MiniLM-L6-v2) when installed: real vector embeddings
2. **token-hash-v1** fallback: deterministic hash-based pseudo-embeddings (64-dim)

All tests run without sentence-transformers installed, using the hash fallback. The `compute_embedding()` return is `(vector, model_name)` so callers always know which path was used.

### Search Ranking

`semantic_search_documents()` in `repository.py` uses a weighted multi-signal score:
- 0.45 * document-level vector similarity
- 0.30 * best chunk-level vector similarity
- 0.20 * lexical token overlap
- 0.05 * concept graph match
- +0.05 freshness bonus (current year)

Falls back to pure lexical `search_documents()` when no vectors score above zero. Results are cached in `query_cache` with TTL-based invalidation; cache is fully cleared on any document upsert/delete.

### FAISS Index (`query/faiss_index.py`)

Optional acceleration layer: `FaissIndex` wraps faiss-cpu with a brute-force fallback. Built during `embeddings-generate`, saved alongside the database. Not used in the main search path yet (search still scans embeddings table directly).

### Watcher Subsystem

Two modes in `watcher/service.py`:
- **Polling**: snapshot-diff loop (`watch_loop`)
- **Watchdog**: inotify-based via `watchdog` library (`watch_loop_watchdog`)

`watchdog` is a core dependency (always installed), so `auto` mode defaults to watchdog. Both modes funnel through a durable event queue (SQLite `events` table) with coalescing, retry (up to 5 attempts), and status tracking. `_drain_event_queue()` processes events in FIFO batches.

### API Server

`api/server.py`: stdlib `ThreadingHTTPServer` with JSON-RPC 2.0 endpoints. No framework dependency. Endpoints: `/api/v1/query`, `/api/v1/get_doc`, `/api/v1/find_concept`, `/health`.

### CLI Structure

`cli/main.py`: argparse with a handler-dispatch dict. Every subcommand resolves its DB path via `_resolve_db_path()` (CLI override > config file > default `.markdownkeeper/index.db`). Most handlers call `initialize_database()` first, which is idempotent and handles schema migrations.

## Key Conventions

- All dataclasses use `slots=True`
- `from __future__ import annotations` in every source file
- Config via `markdownkeeper.toml` (TOML), loaded by `config.py` with dataclass defaults
- Database path resolution: `--db-path` flag > `storage.database_path` in config > `.markdownkeeper/index.db`
- Tests add `src/` to `sys.path` manually (no conftest.py or pytest config)
- All timestamps are UTC ISO format via `datetime.now(tz=timezone.utc).isoformat()`

## Schema Notes

`storage/schema.py` manages schema via idempotent CREATE IF NOT EXISTS plus ALTER TABLE migrations for columns added post-initial design. Foreign keys are enforced (`PRAGMA foreign_keys = ON`); documents cascade-delete all child rows.

## v1.0.0 Roadmap

Milestones 0.8.0 through 0.9.5 are complete. Remaining for 1.0.0:
- Integration/performance test suite against KPI targets
- CLI/API contract freeze (see `docs/COMPATIBILITY.md`)
- Changelog, migration notes, and release tag
