# Contributing to Markdown-Keeper

## Setup

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Branch Workflow

Development happens on the `testing` branch. `main` is protected and only receives authorized merges from `testing`.

```bash
git checkout testing
```

## Development Cycle

1. Write tests first (TDD)
2. Implement the feature or fix
3. Run the full test suite before committing

```bash
pytest tests/          # run tests
mypy src/              # type check
ruff check src/ tests/ # lint
ruff format src/ tests/ # format
```

## Architecture

| Layer | Role |
|-------|------|
| `src/markdownkeeper/cli/` | CLI entry points — argument parsing only |
| `src/markdownkeeper/core/` | Business logic — indexing, querying, embeddings |
| `src/markdownkeeper/db/` | SQLite schema, migrations, queries |
| `src/markdownkeeper/api/` | HTTP API server |

CLI commands call core functions directly — no framework coupling in `core/`.

## Commit Format

```
feat: add chunk-level retrieval to semantic query
fix: watcher queue not replaying on restart
test: add precision@5 regression cases
docs: update CLI reference in USAGE.md
```

## Checklist Before Committing

- [ ] Branch is `testing`, not `main`
- [ ] `pytest tests/` passes
- [ ] `mypy src/` passes with 0 errors
- [ ] No breaking changes to CLI or API contracts (see `docs/COMPATIBILITY.md`)
