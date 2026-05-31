# MarkdownKeeper Compatibility Guarantees

**Status:** frozen for the `v1.x` line as of `v1.0.0`.

MarkdownKeeper follows [Semantic Versioning](https://semver.org/). Within the `1.x`
line, the surfaces below are stable: they will not change in backward-incompatible ways
until `v2.0.0`. Additive changes (new commands, new fields, new endpoints) may ship in
minor releases.

## CLI compatibility

The following command names are frozen for `v1.x`:

`init-db`, `show-config`, `scan-file`, `query`, `get-doc`, `check-links`,
`find-concept`, `build-index`, `watch`, `serve-api`, `daemon-start`, `daemon-stop`,
`daemon-status`, `daemon-restart`, `daemon-reload`, `embeddings-generate`,
`embeddings-status`, `embeddings-eval`, `semantic-benchmark`, `stats`, `report`,
`write-systemd`.

- JSON output (`--format json`) for the machine-oriented commands — `query`, `get-doc`,
  `find-concept`, `embeddings-status`, `embeddings-eval`, `semantic-benchmark`, `stats`,
  `report`, `show-config` — has a stable key schema. Existing keys are not removed or
  renamed within `1.x`; new keys may be added.
- The `mdkeeper` console-script entry point is stable.

## API compatibility

Endpoint paths and JSON-RPC method names frozen for `v1.x`:

| Method | Path | RPC `method` |
|---|---|---|
| `GET` | `/health` | — |
| `POST` | `/api/v1/query` | `semantic_query` |
| `POST` | `/api/v1/get_doc` | `get_document` |
| `POST` | `/api/v1/find_concept` | `find_by_concept` |

- The `/api/v1/*` prefix is reserved for the `v1` contract. Breaking changes ship under a
  new prefix (`/api/v2/*`), not by mutating `v1`.
- Existing response fields (e.g. `result.documents[].id`) and the error-payload structure
  remain backward compatible within `1.x`. New fields may be added.

## Storage compatibility

- `initialize_database` is the stable migration/bootstrap entry point.
- Schema migrations are additive within `1.x` (new columns, indexes, tables). Destructive
  migrations are deferred to a major release and, if ever required, ship with documented
  operator steps.
- A `v1.x` database opened by a newer `1.y` build is migrated forward automatically.

## Versioning & deprecation policy

- **Patch (`1.0.x`)** — bug fixes, no surface change.
- **Minor (`1.x.0`)** — additive only (new commands/fields/endpoints); existing contracts
  preserved.
- **Major (`2.0.0`)** — the only release allowed to break the surfaces above.
- Breaking changes are announced in `CHANGELOG.md` with migration guidance at least one
  minor release before removal where feasible.
