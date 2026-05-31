# What Is Deployed

**Last updated:** 2026-05-30

MarkdownKeeper is a self-hosted CLI + library, not a hosted service. Nothing runs as a
managed deployment.

## Published artifacts

| Artifact | Where | Produced by | Trigger |
|---|---|---|---|
| Devcontainer image | `ghcr.io/l3digitalnet/markdown-keeper-devcontainer:latest` | `.github/workflows/devcontainer.yml` | push to `main` touching `.devcontainer/**` or `pyproject.toml`; `workflow_dispatch` |

- **No PyPI package.** Install is source/editable (`pip install -e .`); console script
  `mdkeeper`.
- **No GitHub releases / tags.** `git tag` shows only `pre-handoff-migration`. The
  `v1.0.0` tag is an open release task.
- **No running service instance.** The watcher and API run on the end user's machine via
  `mdkeeper daemon-start {watch,api}` or the generated systemd units
  (`mdkeeper write-systemd`).

## Self-host runtime surface

- **Watcher daemon** — polling + watchdog, durable event queue, restart-safe replay.
- **HTTP API** — `serve-api`, JSON-RPC 2.0 over `ThreadingHTTPServer`; endpoints
  `/api/v1/{query,get_doc,find_concept}` + `/health`.
- **systemd** — `write-systemd` emits hardened units; `daemon-*` subcommands manage
  lifecycle locally.
