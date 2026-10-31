"""Direct tests for choosier.services.opening."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from choosier.services import FailureKind, ServiceError, open_entry


class OpenEntryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        self.entry = self.target / "file.txt"
        self.entry.touch()

    def test_success_returns_the_entry_name(self) -> None:
        with patch("choosier.launcher.launch_path") as launch:
            outcome = open_entry(self.entry)
        self.assertEqual(outcome.name, "file.txt")
        launch.assert_called_once_with(self.entry)

    def test_missing_entry_is_not_found(self) -> None:
        missing = self.target / "missing"
        with patch("choosier.launcher.launch_path") as launch:
            with self.assertRaises(ServiceError) as caught:
                open_entry(missing)
        self.assertEqual(caught.exception.kind, FailureKind.NOT_FOUND)
        self.assertEqual(caught.exception.message, "Entry is gone")
        launch.assert_not_called()

    def test_launcher_failure_is_wrapped(self) -> None:
        with patch(
            "choosier.launcher.launch_path",
            side_effect=OSError("boom"),
        ):
            with self.assertRaises(ServiceError) as caught:
                open_entry(self.entry)
        self.assertEqual(caught.exception.kind, FailureKind.IO_ERROR)
        self.assertEqual(caught.exception.message, "Cannot open: boom")
        self.assertIsInstance(caught.exception.__cause__, OSError)


if __name__ == "__main__":
    unittest.main()
