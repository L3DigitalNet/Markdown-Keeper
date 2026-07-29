# Codex Instructions for Markdown-Keeper

**Session state:** Agent Handoff SessionStart injects `docs/handoff/state.md`; do not reread it when injected. Then use this file and `docs/handoff/conventions.md`.

**Full conventions reference:** [`docs/handoff/conventions.md`](docs/handoff/conventions.md) - LLM-targeted pattern library. Every convention follows the six-field schema (Applies-when / Rule / Code / Why / Sources / Related) with a Quick Reference table at the top for O(1) lookup. Do not introduce new patterns without checking conventions first.

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

<!-- prettier-ignore-start -->

<!-- BEGIN project-standards:agent-handoff -->
<!-- markdownlint-disable MD025 -->
# Agent Handoff

Use the repo-local `agent-handoff` skill at session startup and closeout. Do not reread state already injected by SessionStart. Keep project knowledge inside this repository and store credential references only, never values.
<!-- markdownlint-enable MD025 -->
<!-- END project-standards:agent-handoff -->

<!-- prettier-ignore-end -->
