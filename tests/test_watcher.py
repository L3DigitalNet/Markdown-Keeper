from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import tempfile
import time
import unittest

from markdownkeeper.storage.repository import list_documents
from markdownkeeper.storage.schema import initialize_database
from markdownkeeper.watcher.service import (
    _MarkdownWatchEventHandler,
    _flush_pending_events,
    watch_once,
)


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

            time.sleep(0.02)
            file.write_text("# A\nupdated", encoding="utf-8")
            snap, r3 = watch_once(db, [docs], [".md"], snap)
            self.assertEqual(r3.modified, 1)

            file.unlink()
            _, r4 = watch_once(db, [docs], [".md"], snap)
            self.assertEqual(r4.deleted, 1)
            self.assertEqual(len(list_documents(db)), 0)


    def test_flush_pending_events_indexes_and_deletes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir(parents=True, exist_ok=True)
            db = root / ".markdownkeeper" / "index.db"
            initialize_database(db)

            existing = docs / "existing.md"
            existing.write_text("# Existing", encoding="utf-8")
            snap, _ = watch_once(db, [docs], [".md"], None)
            self.assertIn(existing.resolve(), snap)

            created = docs / "new.md"
            created.write_text("# New", encoding="utf-8")
            existing.unlink()

            handler = _MarkdownWatchEventHandler({".md"})
            handler._record_change(str(created))
            handler._record_delete(str(existing))

            result = _flush_pending_events(db, handler)
            self.assertEqual(result.modified, 1)
            self.assertEqual(result.deleted, 1)

            docs_now = list_documents(db)
            self.assertEqual(len(docs_now), 1)
            self.assertTrue(docs_now[0].path.endswith("new.md"))



if __name__ == "__main__":
    unittest.main()
