# Codex Instructions for Markdown-Keeper

**Session handoff:** [`docs/handoff.md`](docs/handoff.md) - read this first. Current deployed state, remaining work, bugs log, architecture, credential locations / required env vars / secret names (never secret values), and gotchas.

**Full conventions reference:** [`docs/conventions.md`](docs/conventions.md) - LLM-targeted pattern library. Every convention follows the six-field schema (Applies-when / Rule / Code / Why / Sources / Related) with a Quick Reference table at the top for O(1) lookup. Do not introduce new patterns without checking conventions first.

**Detailed review workflows:** [AGENTS.reviews.md](AGENTS.reviews.md) - read this only for review-related tasks (review planning, review sweeps, code/security/test/etc. reviews). The verbose per-review routing, defaults, and orchestrator notes live there.

## Repo Purpose

Markdown indexing and search service for LLM workflows. Indexes markdown into SQLite, supports lexical and semantic search, and exposes both CLI and JSON-RPC endpoints.

## Commands

```bash
pip install -e .
pip install -e ".[embeddings]"
python -m pytest tests/
mdkeeper init-db --db-path .markdownkeeper/index.db
mdkeeper scan-file README.md --db-path .markdownkeeper/index.db --format json
mdkeeper query "markdown" --db-path .markdownkeeper/index.db --format json
```

## Key Architecture

- Parser -> `ParsedDocument` -> SQLite repository is the core ingest path.
- Embeddings use a two-tier fallback: sentence-transformers when installed, deterministic hash embeddings otherwise.
- The watcher subsystem uses a durable SQLite event queue with coalescing and retry.
- `api/server.py` is stdlib `ThreadingHTTPServer`, not a framework app.
