"""Tests for choosier.tui display helpers (no widget testing)."""

import tempfile
import unittest
from pathlib import Path

from choosier.services import HistoryService, build_state
from choosier.services.state import PANEL_MAX_LINES

try:
    from choosier.tui import render_panel

    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


@unittest.skipUnless(HAS_TEXTUAL, "ui extra (textual) not installed")
class RenderPanelTest(unittest.TestCase):
    def test_empty_shows_placeholder(self) -> None:
        self.assertEqual(render_panel([], "(none)"), "(none)")

    def test_names_joined_and_escaped(self) -> None:
        self.assertEqual(render_panel(["a", "b[weird]"], "(none)"), "a\nb\\[weird]")

    def test_long_views_capped_with_count(self) -> None:
        lines = [f"item{i}" for i in range(5)]
        self.assertEqual(
            render_panel(lines, "(none)", max_lines=3),
            "(showing last 3 of 5)\nitem2\nitem3\nitem4",
        )
        self.assertEqual(render_panel(lines, "(none)", max_lines=5), "\n".join(lines))


@unittest.skipUnless(HAS_TEXTUAL, "ui extra (textual) not installed")
class TuiHistoryScenarioTest(unittest.TestCase):
    HISTORY_SIZE = PANEL_MAX_LINES + 50

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        self.log = self.target / ".choosier.jsonl"
        for index in range(self.HISTORY_SIZE):
            (self.target / f"item{index:03d}").touch()
        history = HistoryService(self.log)
        for index in range(self.HISTORY_SIZE):
            history.append(f"item{index:03d}")

    def test_long_history_panel_renders_the_last_200_lines(self) -> None:
        state = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(state.history_total, self.HISTORY_SIZE)
        self.assertEqual(len(state.history), self.HISTORY_SIZE)
        self.assertEqual(state.remaining, ())
        history_lines = [entry.display for entry in state.history]
        rendered = render_panel(history_lines, "(no history yet)")
        lines = rendered.splitlines()
        self.assertEqual(
            lines[0],
            f"(showing last {PANEL_MAX_LINES} of {self.HISTORY_SIZE})",
        )
        self.assertEqual(lines[1:], history_lines[-PANEL_MAX_LINES:])
        self.assertTrue(history_lines[-1].endswith(f"item{self.HISTORY_SIZE - 1:03d}"))
        self.assertNotIn(history_lines[0], lines[1:])

    def test_archive_and_clear_match_shared_service_outcomes(self) -> None:
        history = HistoryService(self.log)
        backup = history.archive()
        self.assertIsNotNone(backup)
        assert backup is not None
        self.assertTrue(backup.name.endswith(".jsonl.old"))
        self.assertTrue(backup.exists())
        self.assertFalse(self.log.exists())
        state = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(state.history_total, 0)
        self.assertEqual(state.history, ())
        self.assertEqual(
            render_panel(
                [entry.display for entry in state.history],
                "(no history yet)",
            ),
            "(no history yet)",
        )

        history.append("fresh")
        state = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(state.history_total, 1)
        self.assertEqual([entry.item for entry in state.history], ["fresh"])
        self.assertTrue(history.clear())
        self.assertFalse(self.log.exists())
        self.assertFalse(history.clear())
        state = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(state.history_total, 0)
        self.assertEqual(state.history, ())


if __name__ == "__main__":
    unittest.main()
