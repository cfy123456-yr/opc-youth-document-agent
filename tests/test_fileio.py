import tempfile
import unittest
from pathlib import Path
from unittest import mock

from opc_agent.fileio import atomic_write_text


class AtomicWriteTextTests(unittest.TestCase):
    def test_replaces_existing_file_and_leaves_no_temp_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "report.md"
            target.write_text("old", encoding="utf-8")

            atomic_write_text(target, "new")

            self.assertEqual(target.read_text(encoding="utf-8"), "new")
            self.assertEqual(list(target.parent.glob(".report.md.*.tmp")), [])

    def test_failed_replace_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "report.md"
            target.write_text("old", encoding="utf-8")

            with mock.patch(
                "opc_agent.fileio.os.replace",
                side_effect=OSError("replace failed"),
            ):
                with self.assertRaises(OSError):
                    atomic_write_text(target, "new")

            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(target.parent.glob(".report.md.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
