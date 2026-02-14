# Markdown-Keeper

LLM-accessible markdown file database.

## Current Development Milestone

This repository now includes a working foundation for MarkdownKeeper:
This repository now includes the first implementation scaffold for MarkdownKeeper:

- Python package structure under `src/markdownkeeper`
- Config loading from `markdownkeeper.toml`
- SQLite schema initialization for core entities (`documents`, `headings`, `links`, `events`)
- CLI commands for indexing, retrieval, validation, indexing artifacts, watching, and API hosting:
- CLI commands with end-to-end indexing/query basics:
  - `mdkeeper show-config`
  - `mdkeeper init-db`
  - `mdkeeper scan-file <file>`
  - `mdkeeper query <text>`
  - `mdkeeper get-doc <id>`
  - `mdkeeper check-links`
  - `mdkeeper build-index`
  - `mdkeeper find-concept <concept>`
  - `mdkeeper watch`
  - `mdkeeper serve-api`
  - `mdkeeper write-systemd`
  - `mdkeeper daemon-start <watch|api>`
  - `mdkeeper daemon-stop <watch|api>`
  - `mdkeeper daemon-status <watch|api>`
  - `mdkeeper daemon-restart <watch|api>`
  - `mdkeeper embeddings-generate`
  - `mdkeeper embeddings-status`

## Quick Start

```bash
python -m markdownkeeper.cli.main init-db --db-path .markdownkeeper/index.db
python -m markdownkeeper.cli.main scan-file README.md --db-path .markdownkeeper/index.db --format json
python -m markdownkeeper.cli.main query "markdown" --db-path .markdownkeeper/index.db --format json --search-mode semantic
python -m markdownkeeper.cli.main build-index --db-path .markdownkeeper/index.db --output-dir _index
python -m markdownkeeper.cli.main check-links --db-path .markdownkeeper/index.db --format json
python -m markdownkeeper.cli.main find-concept kubernetes --db-path .markdownkeeper/index.db --format json
python -m markdownkeeper.cli.main get-doc 1 --db-path .markdownkeeper/index.db --format json --include-content --max-tokens 200
python -m markdownkeeper.cli.main watch --mode auto --interval 0.5 --duration 5
python -m markdownkeeper.cli.main write-systemd --output-dir deploy/systemd
python -m markdownkeeper.cli.main daemon-start watch --pid-file .markdownkeeper/watch.pid
python -m markdownkeeper.cli.main daemon-status watch --pid-file .markdownkeeper/watch.pid
python -m markdownkeeper.cli.main daemon-stop watch --pid-file .markdownkeeper/watch.pid
python -m markdownkeeper.cli.main daemon-restart watch --pid-file .markdownkeeper/watch.pid
python -m markdownkeeper.cli.main embeddings-generate --db-path .markdownkeeper/index.db
python -m markdownkeeper.cli.main embeddings-status --db-path .markdownkeeper/index.db --format json
```

## API Example

```bash
python -m markdownkeeper.cli.main serve-api --db-path .markdownkeeper/index.db --host 127.0.0.1 --port 8765
```

Then call:

- `POST /api/v1/query` with method `semantic_query`
- `POST /api/v1/get_doc` with method `get_document` (`include_content`, `max_tokens`, `section` supported)
- `POST /api/v1/find_concept` with method `find_by_concept`
- `GET /health`

## Milestones to v1.0.0

Track progress by checking items as they are completed.

### Milestone 0.8.0 — Reliability hardening
- [ ] Implement durable watcher queue persistence and replay after restart
- [ ] Add event coalescing and idempotent processing for create/modify/move/delete bursts
- [ ] Validate restart-safe ingestion under rapid file changes

### Milestone 0.9.0 — Semantic search quality
- [ ] Promote model-backed embeddings as primary runtime path (with fallback retained)
- [ ] Add chunk-level embedding retrieval and stronger hybrid ranking (vector + lexical + concept + freshness)
- [ ] Add evaluation harness for precision@5 and semantic regression tests

### Milestone 0.9.5 — Operations and packaging
- [ ] Finalize systemd hardening, lifecycle semantics, and config reload behavior
- [ ] Publish deployment runbook (install, upgrade, rollback, troubleshooting)
- [ ] Add structured metrics/logging for queue lag, embedding throughput, and API/query latency

### Milestone 1.0.0 — Release readiness
- [ ] Run full integration/performance suite and meet KPI targets
- [ ] Freeze CLI/API contracts and document compatibility guarantees
- [ ] Publish changelog, migration notes, and tag `v1.0.0`

## Remaining Work

- Harden watcher queue semantics and crash-safe replay for high event bursts
- Upgrade semantic retrieval from hash-embedding baseline to model-backed embeddings/vector search
- Expand service install/runbook docs and operational hardening guidance
- Improve ranking quality for lexical + concept queries
- Upgrade semantic retrieval from token-overlap baseline to embedding/vector-backed search
- Add systemd packaging and daemon lifecycle management
- Improve ranking quality for lexical + concept queries
python -m markdownkeeper.cli.main show-config
python -m markdownkeeper.cli.main init-db --db-path .markdownkeeper/index.db
python -m markdownkeeper.cli.main scan-file README.md --db-path .markdownkeeper/index.db --format json
python -m markdownkeeper.cli.main query "markdown" --db-path .markdownkeeper/index.db --format json
```

## Planned Next Steps

- Linux file watcher with event queue/debounce
- Link validation and indexing pipeline
- Semantic query and API service
