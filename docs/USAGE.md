# MarkdownKeeper Usage Guide

Comprehensive reference for installing, configuring, and operating MarkdownKeeper — an
LLM-optimized markdown documentation management service.

---

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Getting Started](#getting-started)
- [CLI Command Reference](#cli-command-reference)
  - [Database Management](#database-management)
  - [Document Indexing](#document-indexing)
  - [Search and Retrieval](#search-and-retrieval)
  - [Link Validation](#link-validation)
  - [Index Generation](#index-generation)
  - [File Watching](#file-watching)
  - [API Server](#api-server)
  - [Daemon Management](#daemon-management)
  - [Embeddings](#embeddings)
  - [Operational Metrics](#operational-metrics)
  - [Systemd Deployment](#systemd-deployment)
- [HTTP API Reference](#http-api-reference)
- [Frontmatter and Document Structure](#frontmatter-and-document-structure)
- [Semantic Search](#semantic-search)
- [Token-Budgeted Content Delivery](#token-budgeted-content-delivery)
- [Embedding Evaluation](#embedding-evaluation)
- [Output Formats](#output-formats)
- [Integration with LLM Agents](#integration-with-llm-agents)
- [Examples](#examples)

---

## Installation

### From source

```bash
git clone https://github.com/L3DigitalNet/Markdown-Keeper.git
cd Markdown-Keeper
pip install .
```

### With embedding support

Install the optional `sentence-transformers` dependency for model-backed semantic
embeddings. Without it, MarkdownKeeper falls back to a hash-based embedding baseline.

```bash
pip install '.[embeddings]'
```

### Verify installation

```bash
mdkeeper --help
```

### Requirements

- Python >= 3.10
- `watchdog >= 3.0.0` (included in base dependencies)
- `tomli >= 2.0.1` (included automatically for Python < 3.11)
- `sentence-transformers >= 2.2` (optional, for model-backed embeddings)

---

## Configuration

MarkdownKeeper reads configuration from a TOML file. The default path is
`markdownkeeper.toml` in the current working directory. Override it with the global
`--config` flag on any command.

### Configuration file format

```toml
[watch]
roots = ["docs", "wiki"]            # Directories to monitor (default: ["."])
extensions = [".md", ".markdown"]   # File extensions to track (default: [".md", ".markdown"])
debounce_ms = 500                   # Debounce interval in milliseconds (default: 500)

[storage]
database_path = ".markdownkeeper/index.db"  # SQLite database path (default shown)

[api]
host = "127.0.0.1"   # API bind address (default: "127.0.0.1")
port = 8765           # API bind port (default: 8765)
```

### Default behavior

If no configuration file exists, MarkdownKeeper uses sensible defaults:

| Section   | Key             | Default                      |
| --------- | --------------- | ---------------------------- |
| `watch`   | `roots`         | `["."]`                      |
| `watch`   | `extensions`    | `[".md", ".markdown"]`       |
| `watch`   | `debounce_ms`   | `500`                        |
| `storage` | `database_path` | `".markdownkeeper/index.db"` |
| `api`     | `host`          | `"127.0.0.1"`                |
| `api`     | `port`          | `8765`                       |

### Viewing resolved configuration

```bash
mdkeeper show-config
mdkeeper --config /etc/markdownkeeper/config.toml show-config
```

Output is JSON:

```json
{
  "watch": {
    "roots": ["docs"],
    "extensions": [".md", ".markdown"],
    "debounce_ms": 500
  },
  "storage": { "database_path": ".markdownkeeper/index.db" },
  "api": { "host": "127.0.0.1", "port": 8765 }
}
```

---

## Getting Started

A minimal workflow to index documents and query them:

```bash
# 1. Initialize the database
mdkeeper init-db

# 2. Scan a markdown file
mdkeeper scan-file README.md --format json

# 3. Search for documents
mdkeeper query "installation guide" --format json

# 4. Retrieve a specific document by ID
mdkeeper get-doc 1 --format json --include-content --max-tokens 200

# 5. Validate links across all indexed documents
mdkeeper check-links --format json

# 6. Generate index files
mdkeeper build-index --output-dir _index
```

---

## CLI Command Reference

All commands support the global `--config <path>` flag to specify a custom configuration
file. Most database-related commands also accept `--db-path <path>` to override the
configured database location.

```text
mdkeeper [--config <path>] <command> [options]
```

### Database Management

#### `init-db`

Create or migrate the SQLite database schema. Safe to run multiple times — uses
`CREATE TABLE IF NOT EXISTS` semantics.

```bash
mdkeeper init-db
mdkeeper init-db --db-path /var/lib/markdownkeeper/index.db
```

| Option      | Type | Default     | Description            |
| ----------- | ---- | ----------- | ---------------------- |
| `--db-path` | Path | from config | Override database path |

### Document Indexing

#### `scan-file <file>`

Parse a markdown file and upsert it into the database. Extracts headings, links,
frontmatter, tags, concepts, generates document chunks, and computes embeddings.

```bash
mdkeeper scan-file docs/setup.md
mdkeeper scan-file docs/setup.md --format json
```

| Option      | Type   | Default     | Description                     |
| ----------- | ------ | ----------- | ------------------------------- |
| `--db-path` | Path   | from config | Override database path          |
| `--format`  | Choice | `text`      | Output format: `text` or `json` |

**JSON output** includes `document_id`, `path`, `title`, heading count, link count, and
`token_estimate`.

### Search and Retrieval

#### `query <text>`

Search indexed documents. Defaults to semantic search mode, which uses hybrid ranking
combining vector similarity, chunk-level matching, lexical overlap, concept matching,
and a freshness bonus. Falls back to lexical (LIKE-based) search if no semantic results
are found.

```bash
mdkeeper query "kubernetes deployment"
mdkeeper query "kubernetes deployment" --format json --search-mode semantic
mdkeeper query "kubernetes deployment" --format json --search-mode lexical
mdkeeper query "setup guide" --include-content --max-tokens 500 --format json
```

| Option              | Type   | Default     | Description                               |
| ------------------- | ------ | ----------- | ----------------------------------------- |
| `--db-path`         | Path   | from config | Override database path                    |
| `--limit`           | int    | `10`        | Maximum number of results                 |
| `--format`          | Choice | `text`      | Output format: `text` or `json`           |
| `--include-content` | Flag   | off         | Include document content in results       |
| `--max-tokens`      | int    | `200`       | Token budget for included content         |
| `--search-mode`     | Choice | `semantic`  | Search algorithm: `semantic` or `lexical` |

**Semantic scoring formula:**

```text
score = (0.45 × vector_score)
      + (0.30 × chunk_score)
      + (0.20 × lexical_score)
      + (0.05 × concept_score)
      + freshness_bonus
```

Where `freshness_bonus` is `0.05` for documents updated in the current year.

#### `get-doc <id>`

Retrieve full metadata for a document by its numeric ID. Supports progressive content
delivery with token budgeting and section filtering.

```bash
mdkeeper get-doc 1 --format json
mdkeeper get-doc 1 --format json --include-content
mdkeeper get-doc 1 --format json --include-content --max-tokens 500
mdkeeper get-doc 1 --format json --include-content --section "installation"
```

| Option              | Type   | Default     | Description                                 |
| ------------------- | ------ | ----------- | ------------------------------------------- |
| `--db-path`         | Path   | from config | Override database path                      |
| `--format`          | Choice | `json`      | Output format: `text` or `json`             |
| `--include-content` | Flag   | off         | Include document body in response           |
| `--max-tokens`      | int    | None        | Limit content to approximately N tokens     |
| `--section`         | str    | None        | Filter content to chunks under this heading |

**JSON output** includes `id`, `path`, `title`, `summary`, `category`, `token_estimate`,
`updated_at`, `headings`, `links`, `tags`, `concepts`, and optionally `content`.

#### `find-concept <concept>`

Find documents associated with a specific concept. Concepts are extracted automatically
from document content or defined explicitly in frontmatter.

```bash
mdkeeper find-concept kubernetes --format json
mdkeeper find-concept authentication --format json --limit 5
```

| Option      | Type   | Default     | Description                     |
| ----------- | ------ | ----------- | ------------------------------- |
| `--db-path` | Path   | from config | Override database path          |
| `--limit`   | int    | `10`        | Maximum number of results       |
| `--format`  | Choice | `json`      | Output format: `text` or `json` |

### Link Validation

#### `check-links`

Validate all links stored in the database. Internal links are checked by resolving file
paths on disk. External links are checked with HTTP HEAD requests (3-second timeout).
Each link's status is updated to `ok` or `broken` in the database.

```bash
mdkeeper check-links
mdkeeper check-links --format json
```

| Option      | Type   | Default     | Description                     |
| ----------- | ------ | ----------- | ------------------------------- |
| `--db-path` | Path   | from config | Override database path          |
| `--format`  | Choice | `text`      | Output format: `text` or `json` |

Returns exit code `1` if any broken links are found, `0` otherwise.

### Index Generation

#### `build-index`

Generate static markdown index files from the database. Produces four files:

- **`master.md`** — All documents ordered by last update
- **`by-category.md`** — Documents grouped by category
- **`by-tag.md`** — Documents grouped by tag
- **`by-concept.md`** — Documents grouped by concept

```bash
mdkeeper build-index
mdkeeper build-index --output-dir _index
mdkeeper build-index --output-dir docs/generated
```

| Option         | Type | Default     | Description                         |
| -------------- | ---- | ----------- | ----------------------------------- |
| `--db-path`    | Path | from config | Override database path              |
| `--output-dir` | Path | `_index`    | Directory for generated index files |

### File Watching

#### `watch`

Continuously monitor configured directories for markdown file changes and automatically
index them. Supports two monitoring backends:

- **`watchdog`** — Event-driven via OS filesystem notifications (recommended)
- **`polling`** — Periodic filesystem snapshot comparison

In `auto` mode (default), watchdog is used when available, falling back to polling.

Changes are processed through a durable event queue with retry logic (up to 5 attempts).
Events are coalesced to handle rapid create/modify/delete bursts idempotently.

```bash
mdkeeper watch
mdkeeper watch --mode auto
mdkeeper watch --mode polling --interval 2.0 --iterations 10
mdkeeper watch --mode watchdog --interval 0.5 --duration 60
```

| Option         | Type   | Default     | Description                                     |
| -------------- | ------ | ----------- | ----------------------------------------------- |
| `--db-path`    | Path   | from config | Override database path                          |
| `--interval`   | float  | `1.0`       | Polling interval / debounce (seconds)           |
| `--iterations` | int    | None        | Stop after N polling cycles (polling mode only) |
| `--mode`       | Choice | `auto`      | Watch backend: `auto`, `polling`, or `watchdog` |
| `--duration`   | float  | None        | Max runtime in seconds (watchdog mode only)     |

### API Server

#### `serve-api`

Start the JSON-RPC HTTP API server. Binds to the configured host and port. See
[HTTP API Reference](#http-api-reference) for endpoint details.

```bash
mdkeeper serve-api
mdkeeper serve-api --host 0.0.0.0 --port 9000
mdkeeper serve-api --db-path /var/lib/markdownkeeper/index.db
```

| Option      | Type | Default     | Description            |
| ----------- | ---- | ----------- | ---------------------- |
| `--db-path` | Path | from config | Override database path |
| `--host`    | str  | from config | Bind address           |
| `--port`    | int  | from config | Bind port              |

### Daemon Management

Background daemon commands manage long-running `watch` or `api` processes via PID files.

#### `daemon-start <target>`

Start the watcher or API server as a background daemon.

```bash
mdkeeper daemon-start watch
mdkeeper daemon-start api
mdkeeper daemon-start watch --pid-file /run/markdownkeeper/watch.pid
```

#### `daemon-stop <target>`

Stop a running daemon gracefully (SIGTERM, then SIGKILL after 5 seconds).

```bash
mdkeeper daemon-stop watch
mdkeeper daemon-stop api
```

#### `daemon-status <target>`

Check whether a daemon is running. Returns exit code `0` if running, `1` otherwise.

```bash
mdkeeper daemon-status watch
mdkeeper daemon-status api
```

#### `daemon-restart <target>`

Stop and restart a daemon.

```bash
mdkeeper daemon-restart watch
mdkeeper daemon-restart api
```

#### `daemon-reload <target>`

Send SIGHUP to a running daemon to reload configuration without restarting.

```bash
mdkeeper daemon-reload watch
mdkeeper daemon-reload api
```

**Common daemon options:**

| Option       | Type | Default                        | Description                                 |
| ------------ | ---- | ------------------------------ | ------------------------------------------- |
| `target`     | str  | required                       | `watch` or `api`                            |
| `--pid-file` | Path | `.markdownkeeper/<target>.pid` | PID file location                           |
| `--db-path`  | Path | from config                    | Override database path (start/restart only) |

### Embeddings

#### `embeddings-generate`

Generate or regenerate embeddings for all indexed documents. Uses
`sentence-transformers` when available; otherwise falls back to hash-based embeddings.

```bash
mdkeeper embeddings-generate
mdkeeper embeddings-generate --model all-MiniLM-L6-v2
```

| Option      | Type | Default            | Description                      |
| ----------- | ---- | ------------------ | -------------------------------- |
| `--db-path` | Path | from config        | Override database path           |
| `--model`   | str  | `all-MiniLM-L6-v2` | Sentence-transformers model name |

#### `embeddings-status`

Show embedding coverage statistics: how many documents have embeddings, how many are
missing, and whether the model backend is available.

```bash
mdkeeper embeddings-status
mdkeeper embeddings-status --format json
```

| Option      | Type   | Default     | Description                     |
| ----------- | ------ | ----------- | ------------------------------- |
| `--db-path` | Path   | from config | Override database path          |
| `--format`  | Choice | `text`      | Output format: `text` or `json` |

**JSON output:**

```json
{
  "documents": 42,
  "embedded": 42,
  "missing": 0,
  "chunks": 156,
  "chunk_embedded": 156,
  "chunk_missing": 0,
  "model_available": true
}
```

#### `embeddings-eval <cases_file>`

Evaluate semantic search precision against a set of known-good test cases. See
[Embedding Evaluation](#embedding-evaluation) for case file format.

```bash
mdkeeper embeddings-eval examples/semantic-cases.json
mdkeeper embeddings-eval examples/semantic-cases.json --k 10 --format json
```

| Option      | Type   | Default     | Description                       |
| ----------- | ------ | ----------- | --------------------------------- |
| `--db-path` | Path   | from config | Override database path            |
| `--k`       | int    | `5`         | Number of top results to evaluate |
| `--format`  | Choice | `json`      | Output format: `text` or `json`   |

#### `semantic-benchmark <cases_file>`

Run a latency and precision benchmark over multiple iterations.

```bash
mdkeeper semantic-benchmark examples/semantic-cases.json
mdkeeper semantic-benchmark examples/semantic-cases.json --k 5 --iterations 10 --format json
```

| Option         | Type   | Default     | Description                       |
| -------------- | ------ | ----------- | --------------------------------- |
| `--db-path`    | Path   | from config | Override database path            |
| `--k`          | int    | `5`         | Number of top results to evaluate |
| `--iterations` | int    | `3`         | Number of benchmark iterations    |
| `--format`     | Choice | `json`      | Output format: `text` or `json`   |

**JSON output** includes `precision_at_k` and `latency_ms` with `avg`, `p50`, `p95`, and
`max` percentiles.

### Operational Metrics

#### `stats`

Display operational statistics: document count, link count, event queue status
(queued/failed/lag), and embedding coverage.

```bash
mdkeeper stats
mdkeeper stats --format json
```

| Option      | Type   | Default     | Description                     |
| ----------- | ------ | ----------- | ------------------------------- |
| `--db-path` | Path   | from config | Override database path          |
| `--format`  | Choice | `json`      | Output format: `text` or `json` |

**JSON output:**

```json
{
  "documents": 42,
  "links": 128,
  "queue": {
    "queued": 0,
    "failed": 0,
    "lag_seconds": 0.0
  },
  "embeddings": {
    "documents": 42,
    "embedded": 42,
    "missing": 0,
    "chunks": 156,
    "chunk_embedded": 156,
    "chunk_missing": 0,
    "model_available": true
  }
}
```

### Systemd Deployment

#### `write-systemd`

Generate systemd service unit files for the watcher and API services.

```bash
mdkeeper write-systemd
mdkeeper write-systemd --output-dir deploy/systemd
mdkeeper write-systemd --exec-path /usr/local/bin/mdkeeper --config-path /etc/markdownkeeper/config.toml
```

| Option          | Type | Default                           | Description                     |
| --------------- | ---- | --------------------------------- | ------------------------------- |
| `--output-dir`  | Path | `deploy/systemd`                  | Output directory for unit files |
| `--exec-path`   | str  | `/usr/local/bin/mdkeeper`         | Path to `mdkeeper` executable   |
| `--config-path` | str  | `/etc/markdownkeeper/config.toml` | Path to configuration file      |

Generates two files:

- **`markdownkeeper.service`** — Watcher service with security hardening
  (`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome=true`)
- **`markdownkeeper-api.service`** — API service, depends on the watcher service

After generating, install with:

```bash
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now markdownkeeper.service markdownkeeper-api.service
```

---

## HTTP API Reference

The API server exposes a JSON-RPC-style HTTP interface.

### Health Check

```http
GET /health
```

**Response:**

```json
{ "status": "ok" }
```

### Semantic Query

```http
POST /api/v1/query
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "semantic_query",
  "params": {
    "query": "kubernetes deployment",
    "max_results": 10,
    "include_content": true,
    "max_tokens": 500,
    "section": "installation"
  }
}
```

| Parameter         | Type   | Default | Description                                |
| ----------------- | ------ | ------- | ------------------------------------------ |
| `query`           | string | —       | Search text                                |
| `max_results`     | int    | `10`    | Maximum results (capped at 100)            |
| `include_content` | bool   | `false` | Include document body in response          |
| `max_tokens`      | int    | `200`   | Token budget for content (capped at 10000) |
| `section`         | string | None    | Filter content to a specific heading       |

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "query": "kubernetes deployment",
    "count": 2,
    "documents": [
      {
        "id": 1,
        "path": "/docs/k8s-guide.md",
        "title": "Kubernetes Deployment Guide",
        "summary": "Step-by-step guide for deploying...",
        "category": "devops",
        "token_estimate": 1250,
        "updated_at": "2026-02-14T10:30:00+00:00",
        "content": "..."
      }
    ]
  }
}
```

### Get Document

```http
POST /api/v1/get_doc
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "get_document",
  "params": {
    "document_id": 1,
    "include_content": true,
    "max_tokens": 500,
    "section": "prerequisites"
  }
}
```

| Parameter         | Type   | Default | Description                          |
| ----------------- | ------ | ------- | ------------------------------------ |
| `document_id`     | int    | —       | Document ID to retrieve              |
| `include_content` | bool   | `false` | Include document body                |
| `max_tokens`      | int    | `200`   | Token budget for content             |
| `section`         | string | None    | Filter content to a specific heading |

### Find by Concept

```http
POST /api/v1/find_concept
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "find_by_concept",
  "params": {
    "concept": "authentication",
    "max_results": 5
  }
}
```

| Parameter     | Type   | Default | Description                |
| ------------- | ------ | ------- | -------------------------- |
| `concept`     | string | —       | Concept name to search for |
| `max_results` | int    | `10`    | Maximum number of results  |

### Error Responses

Errors follow JSON-RPC conventions:

```json
{
  "jsonrpc": "2.0",
  "error": { "code": -32700, "message": "invalid json" },
  "id": null
}
```

| Code   | Meaning                     |
| ------ | --------------------------- |
| -32700 | Parse error (invalid JSON)  |
| -32600 | Request too large (> 1 MiB) |
| -32601 | Method not found            |
| -32004 | Document not found          |

---

## Frontmatter and Document Structure

MarkdownKeeper parses YAML-style frontmatter delimited by `---` markers. Supported
fields:

```markdown
---
title: Kubernetes Setup Guide
tags: devops, kubernetes, containers
category: infrastructure
concepts: kubernetes, helm, deployment
---

# Kubernetes Setup Guide

Content starts here...
```

| Field      | Type   | Description                                             |
| ---------- | ------ | ------------------------------------------------------- |
| `title`    | string | Document title (falls back to first heading if absent)  |
| `tags`     | string | Comma-separated tags, stored for filtering and indexing |
| `category` | string | Single category label for grouping                      |
| `concepts` | string | Comma-separated concepts (auto-extracted if absent)     |

### Automatic extraction

When frontmatter fields are absent, MarkdownKeeper extracts:

- **Title**: First heading in the document, or `"Untitled"`
- **Summary**: First two lines of body text (up to 280 characters)
- **Concepts**: Top 10 significant words by frequency, with heading words weighted 2×.
  Common stopwords (`the`, `and`, `for`, `with`, etc.) are excluded.
- **Token estimate**: Word count of the document body
- **Content hash**: SHA-256 of the full document text

### Document chunking

Documents are split into paragraph-level chunks (max 120 words each). Each chunk is
associated with its nearest preceding heading and receives its own embedding vector.
This enables chunk-level semantic matching during search.

---

## Semantic Search

MarkdownKeeper implements hybrid semantic search with five scoring components:

1. **Vector similarity (45%)** — Cosine similarity between query and full-document
   embeddings
2. **Chunk similarity (30%)** — Best cosine similarity across all document chunks
3. **Lexical overlap (20%)** — Token intersection between query and document text
4. **Concept matching (5%)** — Whether query tokens match any document concepts
5. **Freshness bonus (+0.05)** — Added for documents updated in the current year

### Embedding backends

| Backend                 | Model Name         | When Used                                 |
| ----------------------- | ------------------ | ----------------------------------------- |
| `sentence-transformers` | `all-MiniLM-L6-v2` | When `sentence-transformers` is installed |
| Hash-based fallback     | `token-hash-v1`    | When no model library is available        |

The hash-based fallback uses SHA-256 token hashing into a 64-dimensional vector. It
provides basic keyword matching but significantly lower semantic quality than
model-backed embeddings.

### Query caching

Semantic query results are cached by a SHA-256 hash of the normalized query string and
limit. Cache hits increment a counter and update the last-accessed timestamp. The cache
is not automatically invalidated when documents are re-indexed or deleted — once a query
result is cached, subsequent identical queries always return the cached result. To force
fresh results, clear the `query_cache` table manually or re-initialize the database with
`init-db`.

---

## Token-Budgeted Content Delivery

MarkdownKeeper is designed for LLM agent consumption with token-aware responses. When
requesting content, you can control how much text is returned:

### Progressive delivery pattern

```bash
# Step 1: Get metadata only (minimal tokens)
mdkeeper get-doc 1 --format json

# Step 2: Get content with a tight budget
mdkeeper get-doc 1 --format json --include-content --max-tokens 100

# Step 3: Get a specific section
mdkeeper get-doc 1 --format json --include-content --section "installation"

# Step 4: Get full content
mdkeeper get-doc 1 --format json --include-content
```

This pattern allows LLM agents to first inspect metadata (title, summary, headings,
concepts) and then selectively request content sections, minimizing token usage.

### Section filtering

The `--section` option filters content to chunks whose heading path contains the given
substring (case-insensitive). This enables retrieving only the relevant part of a large
document.

---

## Embedding Evaluation

Use test case files to measure semantic search quality. Cases are defined in JSON:

```json
[
  {
    "query": "kubernetes installation guide",
    "expected_ids": [1, 5]
  },
  {
    "query": "database backup procedures",
    "expected_ids": [3]
  }
]
```

Each entry specifies a natural-language query and the document IDs expected in the top-k
results. Precision@k is computed as the number of expected IDs found in the top-k
results divided by k, averaged across all cases.

### Running evaluations

```bash
# Precision evaluation
mdkeeper embeddings-eval cases.json --k 5 --format json

# Full benchmark with latency measurements
mdkeeper semantic-benchmark cases.json --k 5 --iterations 10 --format json
```

### Interpreting results

- **`precision_at_k`**: Fraction of expected results found (0.0 to 1.0). Higher is
  better.
- **`latency_ms.avg`**: Average query time in milliseconds.
- **`latency_ms.p50`**: Median query time.
- **`latency_ms.p95`**: 95th percentile query time.
- **`latency_ms.max`**: Maximum observed query time.

---

## Output Formats

Most commands support `--format text` (human-readable) and `--format json`
(machine-readable).

### Text format

Concise single-line output suitable for terminal use:

```text
[1] Kubernetes Setup Guide (docs/k8s-guide.md)
[2] Database Backup Runbook (docs/backup.md)
```

### JSON format

Structured output suitable for LLM agents and programmatic consumption. All JSON
payloads use consistent key naming and include counts for list responses:

```json
{
  "query": "kubernetes",
  "search_mode": "semantic",
  "count": 2,
  "documents": [...]
}
```

---

## Integration with LLM Agents

MarkdownKeeper is purpose-built for LLM coding agents. The recommended integration
pattern:

### Via HTTP API

Start the API server and point your agent's tool configuration to it:

```bash
mdkeeper serve-api --host 127.0.0.1 --port 8765
```

The agent can then:

1. **Discover** relevant documents: `POST /api/v1/query` with `semantic_query`
2. **Inspect** metadata: `POST /api/v1/get_doc` with `get_document`
   (`include_content: false`)
3. **Retrieve** content progressively: `POST /api/v1/get_doc` with
   `include_content: true` and a `max_tokens` budget
4. **Browse** by concept: `POST /api/v1/find_concept` with `find_by_concept`

### Via CLI

Agents with shell access can use CLI commands directly with `--format json` for
structured output:

```bash
mdkeeper query "deployment steps" --format json --include-content --max-tokens 300
mdkeeper get-doc 5 --format json --include-content --section "prerequisites"
mdkeeper find-concept "authentication" --format json
```

### Keeping the index fresh

Run the watcher as a daemon or systemd service so documents are automatically re-indexed
when they change:

```bash
# As a daemon
mdkeeper daemon-start watch

# As a systemd service
sudo systemctl start markdownkeeper.service
```

---

## Examples

### Index an entire docs directory

```bash
mdkeeper init-db
for f in docs/*.md; do
  mdkeeper scan-file "$f" --format json
done
mdkeeper stats --format json
```

### Watch for changes and serve the API simultaneously

```bash
mdkeeper daemon-start watch
mdkeeper daemon-start api
mdkeeper daemon-status watch
mdkeeper daemon-status api
```

### Evaluate search quality after re-indexing

```bash
mdkeeper embeddings-generate
mdkeeper embeddings-status --format json
mdkeeper embeddings-eval examples/semantic-cases.json --k 5 --format json
```

### Full production deployment

```bash
# Install
pip install 'markdownkeeper[embeddings]'

# Initialize
mdkeeper init-db --db-path /var/lib/markdownkeeper/index.db

# Generate and install systemd units
mdkeeper write-systemd --output-dir /tmp/systemd \
  --exec-path /usr/local/bin/mdkeeper \
  --config-path /etc/markdownkeeper/config.toml
sudo cp /tmp/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# Start services
sudo systemctl enable --now markdownkeeper.service markdownkeeper-api.service

# Verify
mdkeeper stats --db-path /var/lib/markdownkeeper/index.db --format json
curl http://127.0.0.1:8765/health
```

### Query the API with curl

```bash
# Semantic search
curl -s -X POST http://127.0.0.1:8765/api/v1/query \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "semantic_query",
    "params": {"query": "how to deploy", "max_results": 5, "include_content": true, "max_tokens": 300}
  }' | python -m json.tool

# Get a specific document
curl -s -X POST http://127.0.0.1:8765/api/v1/get_doc \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "get_document",
    "params": {"document_id": 1, "include_content": true, "max_tokens": 500}
  }' | python -m json.tool

# Find by concept
curl -s -X POST http://127.0.0.1:8765/api/v1/find_concept \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "find_by_concept",
    "params": {"concept": "kubernetes", "max_results": 10}
  }' | python -m json.tool
```
