# State

**Last updated:** 2026-05-31

> Live git log, working tree, and pointers are appended by the SessionStart hook —
> this file carries only semantic state. Keep it short (DOC-001).

## Snapshot

- **Released `v1.0.0`** (2026-05-31, tag `v1.0.0`, commit `8b17b6b`). First stable
  release; compatibility frozen for the `1.x` line (`docs/COMPATIBILITY.md`).
- **Version:** `pyproject` + package `__version__` both `1.0.0`.
- **Tests:** 174 unit (no ML deps) + 7 integration (require `sentence-transformers` +
  `faiss-cpu`) = 181 total. All green. KPIs met on the 25-doc fixture corpus:
  precision@5 1.000, search p95 0.3 ms, 25 docs embedded 13.5 s.
- **Local ML env:** `.venv` (Python 3.13, CPU torch + ML extras) — run integration
  via `.venv/bin/python -m pytest tests/integration/`.

## Active incidents / drift

- _(none open)_

## Resolved

- **`main` ↔ `testing` divergence — resolved 2026-05-31.** The comprehensive doc work
  stranded on `testing` (architecture/usage/readme) was ported onto `main` (`b3e2895`);
  `testing` then merged `main` and snapped its tree identical to `main` (`0f0e72d`).
  `main` is now an ancestor of `testing`; trees match. Old `testing` tip preserved at
  tag `testing-pre-resync` (.serena config + pre-handoff CLAUDE.md/git-conventions edits,
  intentionally not carried over). Branch retained per "never delete `testing`".
- **`deployed.md` was "Unknown" until 2026-05-30** — now corrected (no releases;
  only a GHCR devcontainer image). See `docs/deployed.md`.

## Open (post-1.0, not blocking)

- GitHub Release from the `v1.0.0` tag (not yet created — tag is pushed; consider
  `gh release create v1.0.0 -F` notes from `CHANGELOG.md`).
- Sustained high-throughput watcher stress benchmark + baseline metrics.
- Larger-corpus semantic tuning (current precision@5 1.000 is on the curated 25-doc
  fixture set, not arbitrary corpora).
- Ranking quality for lexical + concept queries.
