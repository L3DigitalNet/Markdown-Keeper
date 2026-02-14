# Markdown-Keeper

LLM-accessible markdown file database.

## Current Development Milestone

This repository now includes a working foundation for MarkdownKeeper:

- Python package structure under `src/markdownkeeper`
- Config loading from `markdownkeeper.toml`
- SQLite schema initialization for core entities (`documents`, `headings`, `links`, `events`)
- CLI commands for indexing, retrieval, validation, indexing artifacts, watching, and API hosting:
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

## Remaining Work

- Harden watcher queue semantics and crash-safe replay for high event bursts
- Upgrade semantic retrieval from token-overlap baseline to embedding/vector-backed search
- Add systemd packaging and daemon lifecycle management
- Improve ranking quality for lexical + concept queries
