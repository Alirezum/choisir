"""Tests for choosier.tui display helpers (no widget testing)."""

import unittest

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


if __name__ == "__main__":
    unittest.main()
