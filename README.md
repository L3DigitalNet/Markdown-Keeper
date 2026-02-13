# Markdown-Keeper

LLM-accessible markdown file database.

## Current Development Milestone

This repository now includes the first implementation scaffold for MarkdownKeeper:

- Python package structure under `src/markdownkeeper`
- Config loading from `markdownkeeper.toml`
- SQLite schema initialization for core entities (`documents`, `headings`, `links`, `events`)
- CLI commands with end-to-end indexing/query basics:
  - `mdkeeper show-config`
  - `mdkeeper init-db`
  - `mdkeeper scan-file <file>`
  - `mdkeeper query <text>`
  - `mdkeeper get-doc <id>`

## Quick Start

```bash
python -m markdownkeeper.cli.main show-config
python -m markdownkeeper.cli.main init-db --db-path .markdownkeeper/index.db
python -m markdownkeeper.cli.main scan-file README.md --db-path .markdownkeeper/index.db --format json
python -m markdownkeeper.cli.main query "markdown" --db-path .markdownkeeper/index.db --format json
```

## Planned Next Steps

- Linux file watcher with event queue/debounce
- Link validation and indexing pipeline
- Semantic query and API service
