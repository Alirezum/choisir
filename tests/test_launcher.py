"""Tests for choosier.launcher: OS-specific open behavior."""

import unittest
from pathlib import Path
from unittest.mock import patch

from choosier.launcher import launch_path


class LaunchPathTest(unittest.TestCase):
    def test_linux_uses_xdg_open(self) -> None:
        with (
            patch("choosier.launcher.sys.platform", "linux"),
            patch("choosier.launcher.subprocess.Popen") as popen,
        ):
            launch_path(Path("/tmp/picked.txt"))
        self.assertEqual(popen.call_args[0][0], ["xdg-open", "/tmp/picked.txt"])

    def test_macos_uses_open(self) -> None:
        with (
            patch("choosier.launcher.sys.platform", "darwin"),
            patch("choosier.launcher.subprocess.Popen") as popen,
        ):
            launch_path(Path("/tmp/picked.txt"))
        self.assertEqual(popen.call_args[0][0], ["open", "/tmp/picked.txt"])

    def test_missing_handler_raises_oserror(self) -> None:
        with (
            patch("choosier.launcher.sys.platform", "linux"),
            patch(
                "choosier.launcher.subprocess.Popen",
                side_effect=FileNotFoundError("xdg-open"),
            ),
        ):
            with self.assertRaises(OSError):
                launch_path(Path("/tmp/picked.txt"))

    def test_windows_uses_startfile(self) -> None:
        with (
            patch("choosier.launcher.sys.platform", "win32"),
            patch("choosier.launcher.os.startfile", create=True) as startfile,
        ):
            launch_path(Path("/tmp/picked.txt"))
        startfile.assert_called_once_with("/tmp/picked.txt")


if __name__ == "__main__":
    unittest.main()
