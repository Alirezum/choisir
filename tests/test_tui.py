"""Tests for choosier.tui pure helpers (no widget testing)."""

import tempfile
import unittest
from pathlib import Path

try:
    from choosier.tui import (
        parse_seed,
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


if __name__ == "__main__":
    unittest.main()
