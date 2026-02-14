from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class SystemdUnitPaths:
    watcher_unit: Path
    api_unit: Path


def _watcher_unit_text(exec_path: str, config_path: str) -> str:
    return f"""[Unit]
Description=MarkdownKeeper watcher service
After=network.target

[Service]
Type=simple
ExecStart={exec_path} --config {config_path} watch --mode auto
ExecReload={exec_path} --config {config_path} daemon-restart watch
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def _api_unit_text(exec_path: str, config_path: str) -> str:
    return f"""[Unit]
Description=MarkdownKeeper API service
After=markdownkeeper.service
Requires=markdownkeeper.service

[Service]
Type=simple
ExecStart={exec_path} --config {config_path} serve-api
ExecReload={exec_path} --config {config_path} daemon-restart api
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def write_systemd_units(output_dir: Path, exec_path: str = "/usr/local/bin/mdkeeper", config_path: str = "/etc/markdownkeeper/config.toml") -> SystemdUnitPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    watcher_path = output_dir / "markdownkeeper.service"
    api_path = output_dir / "markdownkeeper-api.service"
    watcher_path.write_text(_watcher_unit_text(exec_path, config_path), encoding="utf-8")
    api_path.write_text(_api_unit_text(exec_path, config_path), encoding="utf-8")
    return SystemdUnitPaths(watcher_unit=watcher_path, api_unit=api_path)
