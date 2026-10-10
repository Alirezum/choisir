"""Tests for choosier.tui pure helpers (no widget testing)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from choosier.tui import (
        launch_path,
        parse_seed,
        preview_entry,
        read_history,
        render_panel,
        resolve_log_path,
    )

    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


@unittest.skipUnless(HAS_TEXTUAL, "ui extra (textual) not installed")
class ParseSeedTest(unittest.TestCase):
    def test_blank_means_random(self) -> None:
        self.assertIsNone(parse_seed(""))
        self.assertIsNone(parse_seed("   "))

    def test_valid_integer(self) -> None:
        self.assertEqual(parse_seed("7"), 7)
        self.assertEqual(parse_seed("  42 "), 42)

    def test_invalid_raises(self) -> None:
        for bad in ["abc", "1.5", "12a"]:
            with self.assertRaises(ValueError, msg=bad):
                parse_seed(bad)


@unittest.skipUnless(HAS_TEXTUAL, "ui extra (textual) not installed")
class ResolveLogPathTest(unittest.TestCase):
    def test_blank_uses_colocated_default(self) -> None:
        self.assertEqual(
            resolve_log_path(Path("/target"), ""),
            Path("/target/.choosier.jsonl"),
        )
        self.assertEqual(
            resolve_log_path(Path("/target"), "   "),
            Path("/target/.choosier.jsonl"),
        )

    def test_explicit_override(self) -> None:
        self.assertEqual(
            resolve_log_path(Path("/target"), "/elsewhere/history.jsonl"),
            Path("/elsewhere/history.jsonl"),
        )


@unittest.skipUnless(HAS_TEXTUAL, "ui extra (textual) not installed")
class ReadHistoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def test_missing_file_returns_empty(self) -> None:
        self.assertEqual(read_history(self.log), [])

    def test_json_lines_show_timestamp_and_item(self) -> None:
        self.log.write_text(
            '{"ts": "2026-01-01T00:00:00+00:00", "item": "a"}\n',
            encoding="utf-8",
        )
        self.assertEqual(read_history(self.log), ["2026-01-01T00:00:00+00:00  a"])

    def test_legacy_and_malformed_lines(self) -> None:
        self.log.write_text(
            '2026-01-01T00:00:00+00:00 - old - item\n[1, 2]\n\n{"noitem": 1}\n',
            encoding="utf-8",
        )
        self.assertEqual(
            read_history(self.log), ["2026-01-01T00:00:00+00:00 - old - item"]
        )


@unittest.skipUnless(HAS_TEXTUAL, "ui extra (textual) not installed")
class RenderPanelTest(unittest.TestCase):
    def test_empty_shows_placeholder(self) -> None:
        self.assertEqual(render_panel([], "(none)"), "(none)")

    def test_names_joined_and_escaped(self) -> None:
        self.assertEqual(render_panel(["a", "b[weird]"], "(none)"), "a\nb\\[weird]")


@unittest.skipUnless(HAS_TEXTUAL, "ui extra (textual) not installed")
class PreviewEntryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_text_file_shows_first_lines(self) -> None:
        target = self.root / "doc.txt"
        target.write_text("one\ntwo\nthree\n", encoding="utf-8")
        self.assertEqual(preview_entry(target), "one\ntwo\nthree")

    def test_long_file_truncates(self) -> None:
        target = self.root / "long.txt"
        target.write_text("\n".join(f"line{i}" for i in range(30)), encoding="utf-8")
        preview = preview_entry(target)
        self.assertIn("line0", preview)
        self.assertNotIn("line29", preview)
        self.assertIn("truncated", preview)

    def test_binary_file_reports_size(self) -> None:
        target = self.root / "blob.bin"
        target.write_bytes(b"\x00\x01\x02binary")
        self.assertEqual(preview_entry(target), "<binary file, 9 bytes>")

    def test_empty_file(self) -> None:
        target = self.root / "empty.txt"
        target.write_text("", encoding="utf-8")
        self.assertEqual(preview_entry(target), "(empty file)")

    def test_missing_entry(self) -> None:
        self.assertEqual(preview_entry(self.root / "gone"), "(gone)")

    def test_directory_reports_count(self) -> None:
        sub = self.root / "sub"
        sub.mkdir()
        (sub / "a").touch()
        (sub / "b").touch()
        self.assertEqual(preview_entry(sub), "<directory with 2 entries>")
        lonely = self.root / "lonely"
        lonely.mkdir()
        (lonely / "only").touch()
        self.assertEqual(preview_entry(lonely), "<directory with 1 entry>")


@unittest.skipUnless(HAS_TEXTUAL, "ui extra (textual) not installed")
class LaunchPathTest(unittest.TestCase):
    def test_linux_uses_xdg_open(self) -> None:
        with (
            patch("choosier.tui.sys.platform", "linux"),
            patch("choosier.tui.subprocess.Popen") as popen,
        ):
            launch_path(Path("/tmp/picked.txt"))
        self.assertEqual(popen.call_args[0][0], ["xdg-open", "/tmp/picked.txt"])

    def test_macos_uses_open(self) -> None:
        with (
            patch("choosier.tui.sys.platform", "darwin"),
            patch("choosier.tui.subprocess.Popen") as popen,
        ):
            launch_path(Path("/tmp/picked.txt"))
        self.assertEqual(popen.call_args[0][0], ["open", "/tmp/picked.txt"])

    def test_missing_handler_raises_oserror(self) -> None:
        with (
            patch("choosier.tui.sys.platform", "linux"),
            patch(
                "choosier.tui.subprocess.Popen",
                side_effect=FileNotFoundError("xdg-open"),
            ),
        ):
            with self.assertRaises(OSError):
                launch_path(Path("/tmp/picked.txt"))

    def test_windows_uses_startfile(self) -> None:
        with (
            patch("choosier.tui.sys.platform", "win32"),
            patch("os.startfile", create=True) as startfile,
        ):
            launch_path(Path("/tmp/picked.txt"))
        startfile.assert_called_once_with("/tmp/picked.txt")


if __name__ == "__main__":
    unittest.main()
