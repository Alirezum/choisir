"""Tests for choosier.preview: structured entry previews."""

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from choosier.preview import PREVIEW_MAX_IMAGES, preview_entry

PNG = b"\x89PNG\r\n\x1a\npngdata"
JPEG = b"\xff\xd8\xffjpegdata"
WEBP = b"RIFF\x00\x00\x00\x00WEBPdata"


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

    def _zip(self, name: str, members: dict[str, bytes]) -> Path:
        archive = self.root / name
        with zipfile.ZipFile(archive, "w") as handle:
            for member, data in members.items():
                handle.writestr(member, data)
        return archive

    def test_zip_archive_lists_images(self) -> None:
        archive = self._zip(
            "pics.zip",
            {
                "a.png": PNG,
                "sub/b.JPG": JPEG,
                "page.webp": WEBP,
                "notes.txt": b"hello",
                "__MACOSX/._a.png": b"junk",
            },
        )
        preview = preview_entry(archive)
        self.assertEqual(preview.kind, "archive")
        self.assertEqual(preview.image_total, 3)
        self.assertEqual(
            [image.name for image in preview.images],
            ["a.png", "sub/b.JPG", "page.webp"],
        )
        self.assertEqual(
            [image.media_type for image in preview.images],
            ["image/png", "image/jpeg", "image/webp"],
        )
        self.assertFalse(preview.truncated)
        self.assertIn("3 images", preview.text)
        self.assertIn("1 other entry", preview.text)

    def test_cbz_is_treated_as_archive(self) -> None:
        archive = self._zip("book.cbz", {"page1.gif": b"GIF89a" + b"data"})
        preview = preview_entry(archive)
        self.assertEqual(preview.kind, "archive")
        self.assertEqual(preview.image_total, 1)
        self.assertEqual(preview.images[0].media_type, "image/gif")

    def test_zip_without_images_reports_entries(self) -> None:
        archive = self._zip("docs.zip", {"readme.txt": b"hi", "data.bin": b"\x00\x01"})
        preview = preview_entry(archive)
        self.assertEqual(preview.kind, "archive")
        self.assertEqual(preview.image_total, 0)
        self.assertEqual(preview.images, ())
        self.assertIn("2 entries", preview.text)

    def test_archive_caps_listed_images(self) -> None:
        archive = self._zip("many.zip", {f"img{i:02d}.png": PNG for i in range(15)})
        preview = preview_entry(archive)
        self.assertEqual(preview.image_total, 15)
        self.assertEqual(len(preview.images), PREVIEW_MAX_IMAGES)
        self.assertTrue(preview.truncated)
        self.assertIn(f"showing first {PREVIEW_MAX_IMAGES} of 15 images", preview.text)

    def test_archive_skips_oversized_images(self) -> None:
        with patch("choosier.preview.PREVIEW_MAX_IMAGE_BYTES", 8):
            archive = self._zip(
                "large.zip",
                {"big.png": PNG, "small.png": b"\x89PNG\r\n\x1a\n"},
            )
            preview = preview_entry(archive)
        self.assertEqual(preview.image_total, 2)
        self.assertEqual([image.name for image in preview.images], ["small.png"])
        self.assertTrue(preview.truncated)
        self.assertIn("1 skipped", preview.text)

    def test_broken_zip_falls_back_to_binary(self) -> None:
        target = self.root / "broken.zip"
        target.write_bytes(b"PK\x03\x04broken\x00")
        preview = preview_entry(target)
        self.assertEqual(preview.kind, "binary")

    def test_standalone_image_gets_preview(self) -> None:
        target = self.root / "photo.png"
        target.write_bytes(PNG)
        preview = preview_entry(target)
        self.assertEqual(preview.kind, "image")
        self.assertEqual(preview.image_total, 1)
        self.assertEqual(preview.size, len(PNG))
        image = preview.images[0]
        self.assertIsNone(image.index)
        self.assertEqual(image.name, "photo.png")
        self.assertEqual(image.media_type, "image/png")
        self.assertIn("image/png", preview.text)

    def test_fake_image_extension_falls_back_to_binary(self) -> None:
        target = self.root / "fake.png"
        target.write_bytes(b"\x00not an image")
        preview = preview_entry(target)
        self.assertEqual(preview.kind, "binary")


if __name__ == "__main__":
    unittest.main()
