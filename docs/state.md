# State

**Last updated:** 2026-05-30

> Live git log, working tree, and pointers are appended by the SessionStart hook —
> this file carries only semantic state. Keep it short (DOC-001).

## Snapshot

- **Product milestone:** 0.9.5 complete. 1.0.0 is the only open milestone.
- **Package version (`pyproject`):** still `0.1.0`. The bump to `1.0.0` is itself an
  open release task — do not read `0.1.0` as "early/unfinished".
- **Tests:** 181 collected, pass without ML deps. ML path (`sentence-transformers`,
  `faiss-cpu`) is optional; default runtime uses deterministic hash-bucket embeddings.
- **Code:** frozen since `1080c38` (integration test suite, late April). Every commit
  since is handoff-system docs/scaffolding, not feature work.

## Active incidents / drift

- **`main` ↔ `origin/testing` diverged: 16 ahead / 3 behind.** `testing` is the
  integration branch (do not delete). `testing`-only commits: Serena project config,
  an architecture doc, a git-conventions doc. `main`-only: handoff-v3 migration +
  community-health files + auto-commits. Reconcile before tagging v1.0.0.
- **`deployed.md` was "Unknown" until 2026-05-30** — now corrected (no releases;
  only a GHCR devcontainer image). See `docs/deployed.md`.

## Open for v1.0.0

- [ ] Run full integration/performance suite and meet KPI targets
- [ ] Freeze CLI/API contracts; document compatibility guarantees (`docs/COMPATIBILITY.md`)
- [ ] Publish changelog + migration notes, bump `pyproject` to `1.0.0`, tag `v1.0.0`

### Carry-over tuning (not release-blocking)

- Sustained high-throughput watcher stress benchmark + baseline metrics
- Larger-corpus semantic tuning to lift precision@5
- Ranking quality for lexical + concept queries
