# Markdown-Keeper — Development Commands

```bash
pip install -e .                        # Install editable
pip install -e ".[embeddings]"          # With sentence-transformers
python -m pytest tests/                 # All tests (174, ~12s)
python -m pytest tests/test_parser.py   # Single file
bash scripts/run-integration-tests.sh   # Integration (devcontainer only)
```

## Quick dev workflow
```bash
mdkeeper init-db --db-path .markdownkeeper/index.db
mdkeeper scan-file README.md --db-path .markdownkeeper/index.db --format json
mdkeeper query "markdown" --db-path .markdownkeeper/index.db --format json
```

## Git
- Work on `testing` branch; pre-commit/pre-push hooks block direct main commits
