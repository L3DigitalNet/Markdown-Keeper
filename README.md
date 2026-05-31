# MarkdownKeeper

An LLM-accessible markdown documentation database. Indexes `.md` files into SQLite,
provides hybrid semantic and lexical search, and exposes results via CLI and JSON-RPC
HTTP API. Designed to run as a persistent service that LLM agents query
programmatically.

## Features

- **Hybrid semantic search** — weighted combination of vector similarity, chunk-level
  matching, lexical overlap, concept matching, and a freshness signal
- **Two-tier embeddings** — sentence-transformers (all-MiniLM-L6-v2) with a
  deterministic hash-based fallback for offline and test environments
- **Durable file watcher** — inotify-backed (via watchdog) or polling mode, with a
  SQLite-persisted event queue, event coalescing, and automatic retry (up to 5 attempts)
- **JSON-RPC HTTP API** — token-budgeted content delivery with section filtering, built
  for LLM agent consumption
- **Static index generation** — markdown index files grouped by category, tag, and
  concept
- **Link validation** — internal file paths and external URLs with per-domain rate
  limiting
- **Systemd integration** — hardened service units with full lifecycle management
  (start, stop, reload, restart)

## Quick Start

```bash
# Install with semantic embedding support
pip install 'markdownkeeper[embeddings]'

# Initialize the database
mdkeeper init-db

# Index some markdown files
mdkeeper scan-file docs/README.md
mdkeeper scan-file docs/guide.md

# Search
mdkeeper query "kubernetes deployment" --format json

# Start the watcher and API as background daemons
mdkeeper daemon-start watch
mdkeeper daemon-start api

# Check health
mdkeeper stats --format json
curl http://127.0.0.1:8765/health
```

## Requirements

| Dependency | Required? | Purpose |
|---|---|---|
| Python >= 3.10 | Yes | Runtime |
| `watchdog >= 3.0.0` | Yes | File watching |
| `tomli >= 2.0.1` | Yes (Python 3.10 only) | TOML config parsing |
| `sentence-transformers >= 2.2` | Optional (`[embeddings]`) | Model-backed semantic search |
| `faiss-cpu >= 1.7`, `numpy >= 1.24` | Optional (`[faiss]`) | FAISS vector index acceleration |

## Installation

```bash
# Base install — hash-based embeddings only, no ML dependencies
pip install markdownkeeper

# With sentence-transformers for real semantic embeddings
pip install 'markdownkeeper[embeddings]'

# With FAISS acceleration (requires embeddings)
pip install 'markdownkeeper[embeddings,faiss]'
```

## CLI Commands

| Command | Description |
|---|---|
| `init-db` | Initialize or migrate the SQLite database |
| `scan-file <file>` | Parse and index a single markdown file |
| `query <text>` | Search indexed documents (semantic or lexical) |
| `get-doc <id>` | Retrieve a document by ID with optional content |
| `find-concept <concept>` | Find documents associated with a concept |
| `check-links` | Validate all indexed links (internal and external) |
| `build-index` | Generate static markdown index files |
| `watch` | Monitor directories and auto-index file changes |
| `serve-api` | Start the JSON-RPC HTTP API server |
| `daemon-start/stop/status/restart/reload <watch\|api>` | Manage background daemons |
| `embeddings-generate` | Regenerate all document embeddings |
| `embeddings-status` | Show embedding coverage statistics |
| `embeddings-eval <cases.json>` | Evaluate search precision@k |
| `semantic-benchmark <cases.json>` | Benchmark search latency and precision |
| `stats` | Show operational statistics (documents, queue, embeddings) |
| `report` | Generate a full health report with broken links and coverage |
| `show-config` | Show resolved configuration as JSON |
| `write-systemd` | Generate systemd service unit files |

## API Endpoints

Start the server with `mdkeeper serve-api`, then:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/query` (method: `semantic_query`) | Semantic document search |
| `POST` | `/api/v1/get_doc` (method: `get_document`) | Retrieve document by ID |
| `POST` | `/api/v1/find_concept` (method: `find_by_concept`) | Find documents by concept |

## Documentation

- [docs/USAGE.md](docs/USAGE.md) — Complete CLI and API reference, configuration,
  semantic search, embeddings, and LLM agent integration patterns
- [docs/architecture.md](docs/architecture.md) — System architecture, data flow,
  database schema, and component diagrams
- [docs/OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md) — Install, upgrade,
  rollback, and troubleshooting
- [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) — CLI/API/storage compatibility policy
  toward v1.0.0

## Development Status

Milestones 0.8.0 through 0.9.5 are complete. Remaining for v1.0.0:

- Run full integration and performance test suite against KPI targets
- Freeze CLI and API contracts; publish compatibility guarantees
- Publish changelog, migration notes, and tag `v1.0.0`

```bash
# Unit tests (181 tests, no ML dependencies required)
python -m pytest tests/

# Integration tests (devcontainer only — requires sentence-transformers + faiss-cpu)
bash scripts/run-integration-tests.sh
```
