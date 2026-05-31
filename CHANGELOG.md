# Changelog

All notable changes to MarkdownKeeper are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-05-31

First stable release. Compatibility guarantees for the `1.x` line are defined in
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md). This release consolidates the 0.8.0
(reliability), 0.9.0 (semantic quality), and 0.9.5 (operations/packaging) milestones;
no earlier versions were published.

### Added

- **Hybrid semantic search** — weighted combination of document-vector, chunk-vector,
  lexical-overlap, concept, and freshness signals.
- **Two-tier embeddings** — sentence-transformers (`all-MiniLM-L6-v2`) when available,
  with a deterministic 64-dim SHA-256 hash fallback that needs no ML dependencies.
- **Chunk-level retrieval** — paragraph-targeted queries benefit from chunk embeddings,
  not just document-level vectors.
- **Durable file watcher** — watchdog or polling mode backed by a SQLite-persisted event
  queue, with event coalescing, idempotent create/modify/move/delete handling, up to 5
  retries, and restart-safe replay.
- **JSON-RPC HTTP API** — `/api/v1/query`, `/api/v1/get_doc`, `/api/v1/find_concept`, and
  `/health`, with token-budgeted, section-filtered content delivery for LLM agents.
- **Static index generation** — markdown index files grouped by category, tag, and
  concept.
- **Link validation** — internal file paths and external URLs, with per-domain rate
  limiting.
- **systemd integration** — hardened unit generation (`write-systemd`) and full daemon
  lifecycle management (`daemon-start` / `daemon-stop` / `daemon-status` /
  `daemon-restart` / `daemon-reload`).
- **Operations** — install/upgrade/rollback/troubleshooting runbook
  (`docs/OPERATIONS_RUNBOOK.md`) and structured metrics/logging for queue lag, embedding
  throughput, and API/query latency.
- **Evaluation tooling** — `embeddings-eval` (precision@k), `semantic-benchmark`
  (latency/precision), and an integration suite (`tests/integration`) that asserts the
  v1.0.0 KPI targets against a real model.

### Verified KPIs

Measured by the integration suite on the 25-document fixture corpus:

| KPI | Target | Measured |
|---|---|---|
| precision@5 | ≥ 0.90 | 1.000 |
| search latency p95 | < 150 ms | 0.3 ms |
| embed 25 documents | < 30 s | 13.5 s |

### Compatibility

- CLI command names, machine-oriented JSON output keys, `/api/v1/*` endpoint paths and
  RPC method names, and the `initialize_database` storage entry point are frozen for the
  `1.x` line. See [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

### Notes

- The default runtime requires **no ML dependencies** (hash-fallback embeddings). Install
  `markdownkeeper[embeddings]` for model-backed semantic search and `[faiss]` for vector
  index acceleration.
- Unit suite: 174 tests, no ML dependencies. Integration suite: 7 tests, requires
  `sentence-transformers` + `faiss-cpu`.

[1.0.0]: https://github.com/L3DigitalNet/Markdown-Keeper/releases/tag/v1.0.0
