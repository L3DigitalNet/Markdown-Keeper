from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import tempfile
import unittest

from markdownkeeper.service import write_systemd_units


class ServiceTests(unittest.TestCase):
    def test_write_systemd_units_creates_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "units"
            paths = write_systemd_units(out, exec_path="/opt/mdkeeper", config_path="/etc/mdk.toml")
            self.assertTrue(paths.watcher_unit.exists())
            self.assertTrue(paths.api_unit.exists())
            watcher = paths.watcher_unit.read_text(encoding="utf-8")
            api = paths.api_unit.read_text(encoding="utf-8")
            self.assertIn("ExecStart=/opt/mdkeeper --config /etc/mdk.toml watch --mode auto", watcher)
            self.assertIn("ExecStart=/opt/mdkeeper --config /etc/mdk.toml serve-api", api)
            self.assertIn("ExecReload=/opt/mdkeeper --config /etc/mdk.toml daemon-reload watch", watcher)
            self.assertIn("ExecReload=/opt/mdkeeper --config /etc/mdk.toml daemon-reload api", api)
            self.assertIn("NoNewPrivileges=true", watcher)
            self.assertIn("ProtectSystem=strict", watcher)
            self.assertIn("User=markdownkeeper", api)


if __name__ == "__main__":
    unittest.main()
