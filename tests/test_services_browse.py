"""Direct tests for choosier.services.browse."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from choosier.services import FailureKind, ServiceError, browse_directory


class BrowseDirectoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()

    def test_orders_directories_first_case_insensitively(self) -> None:
        for name in ("Beta", "alpha"):
            (self.target / name).touch()
        for name in ("zDir", "adir"):
            (self.target / name).mkdir()
        listing = browse_directory(self.target)
        self.assertEqual(
            [entry.name for entry in listing.entries],
            ["adir", "zDir", "alpha", "Beta"],
        )
        self.assertEqual(
            [entry.is_dir for entry in listing.entries],
            [True, True, False, False],
        )
        self.assertEqual(listing.path, self.target)
        self.assertEqual(listing.parent, self.target.parent)

    def test_filesystem_root_has_no_parent(self) -> None:
        root = Path(self.target.anchor)
        listing = browse_directory(root)
        self.assertIsNone(listing.parent)
        self.assertEqual(listing.path, root)

    def test_missing_or_non_directory_target(self) -> None:
        regular_file = self.target / "file.txt"
        regular_file.touch()
        for path in (self.target / "missing", regular_file):
            with self.subTest(path=path.name):
                with self.assertRaises(ServiceError) as caught:
                    browse_directory(path)
                self.assertEqual(caught.exception.kind, FailureKind.NOT_FOUND)
                self.assertEqual(caught.exception.message, "Not a directory")

    def test_listing_permission_failure_uses_public_seam(self) -> None:
        with patch(
            "choosier.services.browse.Path.iterdir",
            side_effect=PermissionError("denied"),
        ):
            with self.assertRaises(ServiceError) as caught:
                browse_directory(self.target)
        self.assertEqual(caught.exception.kind, FailureKind.FORBIDDEN)
        self.assertEqual(caught.exception.message, "Cannot list: denied")
        self.assertIsInstance(caught.exception.__cause__, PermissionError)


if __name__ == "__main__":
    unittest.main()
