from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import tempfile
import unittest

from markdownkeeper.storage.repository import list_documents
from markdownkeeper.storage.schema import initialize_database
from markdownkeeper.watcher.service import watch_once


class WatcherTests(unittest.TestCase):
    def test_watch_once_detects_create_modify_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir(parents=True, exist_ok=True)
            db = root / ".markdownkeeper" / "index.db"
            initialize_database(db)

            snap, r1 = watch_once(db, [docs], [".md"], None)
            self.assertEqual((r1.created, r1.modified, r1.deleted), (0, 0, 0))

            file = docs / "a.md"
            file.write_text("# A", encoding="utf-8")
            snap, r2 = watch_once(db, [docs], [".md"], snap)
            self.assertEqual(r2.created, 1)

            file.write_text("# A\nupdated", encoding="utf-8")
            snap, r3 = watch_once(db, [docs], [".md"], snap)
            self.assertEqual(r3.modified, 1)

            file.unlink()
            _, r4 = watch_once(db, [docs], [".md"], snap)
            self.assertEqual(r4.deleted, 1)
            self.assertEqual(len(list_documents(db)), 0)


if __name__ == "__main__":
    unittest.main()
