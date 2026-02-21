#!/usr/bin/env bash
set -euo pipefail

pip install --upgrade pip
pip install -e ".[embeddings,faiss]"
pip install mypy

echo "MarkdownKeeper dev environment ready. Run: python -m unittest discover -s tests -v"
