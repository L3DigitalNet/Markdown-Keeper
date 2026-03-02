# Markdown-Keeper — Project Overview

## Purpose
LLM-accessible markdown documentation database. Indexes .md files into SQLite, supports semantic and lexical search, exposes results via CLI and JSON-RPC API. Designed as persistent service (watcher + API daemon) for LLM agent queries.

## Tech Stack
- Python 3.10+, SQLite, setuptools
- Optional: sentence-transformers (embeddings), faiss-cpu (vector search)
- Testing: pytest via unittest.TestCase (174 tests, ~12s)

## Data Flow
```
markdown files -> parser -> ParsedDocument -> upsert_document() -> SQLite
                                                  |
                                          compute_embedding() -> embeddings table
                                          _chunk_document()   -> document_chunks table
```

## Embedding Strategy
Two-tier fallback in `query/embeddings.py`:
1. sentence-transformers (all-MiniLM-L6-v2) when installed
2. token-hash-v1 fallback: deterministic hash-based pseudo-embeddings (64-dim)

## Key Directories
- `src/markdownkeeper/` — CLI + API
- `tests/` — unit tests (run without ML deps)
- `tests/integration/` — requires devcontainer with ML deps
