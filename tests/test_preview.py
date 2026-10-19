"""Tests for choosier.preview: structured entry previews."""

import tempfile
import unittest
from pathlib import Path

from choosier.preview import preview_entry


class PreviewEntryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_text_file_shows_first_lines(self) -> None:
        target = self.root / "doc.txt"
        target.write_text("one\ntwo\nthree\n", encoding="utf-8")
        preview = preview_entry(target)
        self.assertEqual(preview.kind, "text")
        self.assertEqual(preview.text, "one\ntwo\nthree")
        self.assertFalse(preview.truncated)

    def test_long_file_truncates(self) -> None:
        target = self.root / "long.txt"
        target.write_text("\n".join(f"line{i}" for i in range(30)), encoding="utf-8")
        preview = preview_entry(target)
        self.assertEqual(preview.kind, "text")
        self.assertTrue(preview.truncated)
        self.assertIn("line0", preview.text)
        self.assertNotIn("line29", preview.text)
        self.assertIn("truncated", preview.text)

    def test_binary_file_reports_size(self) -> None:
        target = self.root / "blob.bin"
        target.write_bytes(b"\x00\x01\x02binary")
        preview = preview_entry(target)
        self.assertEqual(preview.kind, "binary")
        self.assertEqual(preview.text, "<binary file, 9 bytes>")
        self.assertEqual(preview.size, 9)

    def test_empty_file(self) -> None:
        target = self.root / "empty.txt"
        target.write_text("", encoding="utf-8")
        preview = preview_entry(target)
        self.assertEqual(preview.kind, "empty")
        self.assertEqual(preview.text, "(empty file)")

    def test_missing_entry(self) -> None:
        preview = preview_entry(self.root / "gone")
        self.assertEqual(preview.kind, "gone")
        self.assertEqual(preview.text, "(gone)")

    def test_directory_reports_count(self) -> None:
        sub = self.root / "sub"
        sub.mkdir()
        (sub / "a").touch()
        (sub / "b").touch()
        preview = preview_entry(sub)
        self.assertEqual(preview.kind, "directory")
        self.assertEqual(preview.entry_count, 2)
        self.assertEqual(preview.text, "<directory with 2 entries>")
        lonely = self.root / "lonely"
        lonely.mkdir()
        (lonely / "only").touch()
        self.assertEqual(preview_entry(lonely).text, "<directory with 1 entry>")

    def test_huge_directory_count_is_bounded(self) -> None:
        big = self.root / "big"
        big.mkdir()
        for i in range(1005):
            (big / f"f{i}").touch()
        preview = preview_entry(big)
        self.assertTrue(preview.truncated)
        self.assertIsNone(preview.entry_count)
        self.assertEqual(preview.text, "<directory with 1000+ entries>")


if __name__ == "__main__":
    unittest.main()
