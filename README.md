# Markdown-Keeper

LLM-accessible markdown file database.

## Current Development Milestone

This repository now includes a working foundation for MarkdownKeeper:

- Python package structure under `src/markdownkeeper`
- Config loading from `markdownkeeper.toml`
- SQLite schema initialization for core entities (`documents`, `headings`, `links`,
  `tags`, `concepts`, `document_chunks`, `embeddings`, `query_cache`, `events`)
- CLI commands for indexing, retrieval, validation, indexing artifacts, watching, and
  API hosting:
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
  - `mdkeeper daemon-reload <watch|api>`
  - `mdkeeper stats`
  - `mdkeeper embeddings-generate`
  - `mdkeeper embeddings-status`
  - `mdkeeper embeddings-eval <cases.json>`
  - `mdkeeper semantic-benchmark <cases.json>`

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
python -m markdownkeeper.cli.main daemon-reload watch --pid-file .markdownkeeper/watch.pid
python -m markdownkeeper.cli.main stats --db-path .markdownkeeper/index.db --format json
python -m markdownkeeper.cli.main embeddings-generate --db-path .markdownkeeper/index.db
python -m markdownkeeper.cli.main embeddings-status --db-path .markdownkeeper/index.db --format json
python -m markdownkeeper.cli.main embeddings-eval examples/semantic-cases.json --db-path .markdownkeeper/index.db --k 5 --format json
python -m markdownkeeper.cli.main semantic-benchmark examples/semantic-cases.json --db-path .markdownkeeper/index.db --k 5 --iterations 3 --format json
```

## API Example

```bash
python -m markdownkeeper.cli.main serve-api --db-path .markdownkeeper/index.db --host 127.0.0.1 --port 8765
```

Then call:

- `POST /api/v1/query` with method `semantic_query`
- `POST /api/v1/get_doc` with method `get_document` (`include_content`, `max_tokens`,
  `section` supported)
- `POST /api/v1/find_concept` with method `find_by_concept`
- `GET /health`

## Milestones to v1.0.0

Track progress by checking items as they are completed.

### Milestone 0.8.0 — Reliability hardening

- [x] Implement durable watcher queue persistence and replay after restart
- [x] Add event coalescing and idempotent processing for create/modify/move/delete
      bursts
- [x] Validate restart-safe ingestion under rapid file changes

### Milestone 0.9.0 — Semantic search quality

- [x] Promote model-backed embeddings as primary runtime path (with fallback retained)
- [x] Add chunk-level embedding retrieval and stronger hybrid ranking (vector +
      lexical + concept + freshness)
- [x] Add evaluation harness for precision@5 and semantic regression tests

### Milestone 0.9.5 — Operations and packaging

- [x] Finalize systemd hardening, lifecycle semantics, and config reload behavior
- [x] Publish deployment runbook (install, upgrade, rollback, troubleshooting)
- [x] Add structured metrics/logging for queue lag, embedding throughput, and API/query
      latency

### Milestone 1.0.0 — Release readiness

- [ ] Run full integration/performance suite and meet KPI targets
- [ ] Freeze CLI/API contracts and document compatibility guarantees
- [ ] Publish changelog, migration notes, and tag `v1.0.0`

## Documentation

- See `docs/USAGE.md` for comprehensive usage documentation covering CLI commands, HTTP
  API reference, configuration, semantic search, embeddings, and LLM agent integration.
- See `docs/OPERATIONS_RUNBOOK.md` for install/upgrade/rollback and troubleshooting
  guidance.
- See `docs/COMPATIBILITY.md` for CLI/API/storage compatibility targets toward `v1.0.0`.

## Remaining Work

- Execute sustained high-throughput watcher stress benchmark and publish baseline
  metrics
- Run larger-corpus semantic tuning to improve precision@5 beyond baseline thresholds
- Continue expanding production ops docs (alerts, SLOs, incident playbooks)
- Improve ranking quality for lexical + concept queries
