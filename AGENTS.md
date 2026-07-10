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

<!-- BEGIN agent-handoff managed instructions -->
Use the repo-local `$agent-handoff` skill at startup and closeout.
Do not reread `docs/handoff/state.md` when SessionStart already injected it.
Keep current status and tasks in `docs/STATUS.md` and `docs/TODO.md`; route durable facts through `docs/handoff/`.
At closeout, update only changed facts, preserve user-authored work, store credential references only, and run relevant validation.
<!-- END agent-handoff managed instructions -->
