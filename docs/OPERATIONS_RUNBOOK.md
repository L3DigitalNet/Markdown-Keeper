# MarkdownKeeper Operations Runbook

## Installation

1. Install package and optional embedding extras:
   - `pip install markdownkeeper[embeddings]`
2. Initialize database:
   - `mdkeeper init-db --db-path /var/lib/markdownkeeper/index.db`
3. Generate systemd units:
   - `mdkeeper write-systemd --output-dir deploy/systemd --exec-path /usr/local/bin/mdkeeper --config-path /etc/markdownkeeper/config.toml`
4. Copy units and reload systemd:
   - `sudo cp deploy/systemd/*.service /etc/systemd/system/`
   - `sudo systemctl daemon-reload`

## Service lifecycle

- Start watcher: `sudo systemctl start markdownkeeper.service`
- Start API: `sudo systemctl start markdownkeeper-api.service`
- Reload config (SIGHUP): `sudo systemctl reload markdownkeeper.service`
- Restart service: `sudo systemctl restart markdownkeeper.service`
- Status: `sudo systemctl status markdownkeeper.service markdownkeeper-api.service`

## Upgrade steps

1. Backup DB: `cp /var/lib/markdownkeeper/index.db /var/lib/markdownkeeper/index.db.bak`
2. Deploy new package version.
3. Run DB migration bootstrap:
   - `mdkeeper init-db --db-path /var/lib/markdownkeeper/index.db`
4. Restart services:
   - `sudo systemctl restart markdownkeeper.service markdownkeeper-api.service`
5. Regenerate embeddings:
   - `mdkeeper embeddings-generate --db-path /var/lib/markdownkeeper/index.db`

## Rollback

1. Stop services.
2. Reinstall previous package version.
3. Restore DB backup if required.
4. Restart services.

## Operational checks

- Queue and embedding health:
  - `mdkeeper stats --db-path /var/lib/markdownkeeper/index.db --format json`
- Embedding coverage:
  - `mdkeeper embeddings-status --db-path /var/lib/markdownkeeper/index.db --format json`
- Semantic quality baseline:
  - `mdkeeper embeddings-eval examples/semantic-cases.json --db-path /var/lib/markdownkeeper/index.db --k 5 --format json`

## Troubleshooting

- Queue backlog growing:
  - Check `stats.queue.queued` and `stats.queue.lag_seconds`.
  - Increase resources or reduce watch scope.
- Embeddings unavailable:
  - Verify `stats.embeddings.model_available`.
  - Install extras: `pip install markdownkeeper[embeddings]`.
- API slow queries:
  - Run `embeddings-eval` and inspect precision/latency externally.
