# MarkdownKeeper Compatibility Guarantees (pre-1.0 draft)

This document defines intended compatibility guarantees to finalize for `v1.0.0`.

## CLI compatibility

- Existing command names will remain stable through `v1.0.0`.
- JSON output keys for machine-oriented commands (`query`, `get-doc`, `find-concept`, `embeddings-status`, `embeddings-eval`, `semantic-benchmark`, `stats`) are treated as compatibility-sensitive.
- New fields may be added to JSON payloads, but existing fields should not be removed before a major release.

## API compatibility

- API endpoint paths under `/api/v1/*` will remain stable for `v1`.
- Existing method names in JSON-RPC-style payload handling (`semantic_query`, `get_document`, `find_by_concept`) are compatibility-sensitive.
- Error payload structure should stay backward compatible for existing clients.

## Storage compatibility

- `initialize_database` remains the migration/bootstrap entrypoint.
- Migrations are additive where possible (new columns/indexes/tables) and should avoid destructive changes during the `v1` line.

## Upgrade policy target for v1.0.0

- Document all breaking changes in release notes.
- Provide migration guidance for any required manual operator actions.
- Maintain backward compatibility in minor releases (`1.x`).
