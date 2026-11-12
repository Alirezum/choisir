"""Tests for choosier.path_memory: location, format, pruning, and locking."""

import json
import multiprocessing
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from choosier.path_memory import (
    DEFAULT_FILENAME,
    ENV_OVERRIDE,
    MAX_RECENT,
    READ_WARNING,
    RECORD_WARNING,
    UPDATE_WARNING,
    MemorySnapshot,
    PathMemory,
    canonical_path,
    default_memory_path,
    is_usable_directory,
)

POSIX = os.name != "nt"


def _record_folders(memory_file: str, folders: list[str]) -> None:
    """Top-level worker so multiprocessing can target it."""
    memory = PathMemory(memory_file)
    for folder in folders:
        if not memory.record(folder).ok:
            raise RuntimeError(f"record failed for {folder}")


class PathMemoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / "folder"
        self.folder.mkdir()
        self.memory_file = self.root / "config" / "path-memory.json"
        self.memory = PathMemory(self.memory_file)

    def _folder(self, name: str) -> Path:
        target = self.root / name
        target.mkdir()
        return target

    def _write_raw(self, text: str) -> None:
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.memory_file.write_text(text, encoding="utf-8")

    def _skip_permission_checks(self) -> None:
        if not POSIX:
            self.skipTest("POSIX permissions are not available")
        if os.geteuid() == 0:
            self.skipTest("permission checks do not hold for root")

    # --- location and path helpers -------------------------------------

    def test_default_path_is_platform_appropriate(self) -> None:
        home = self.root / "home"
        with patch.dict(
            os.environ,
            {"HOME": str(home), "XDG_CONFIG_HOME": ""},
            clear=True,
        ):
            with patch("choosier.path_memory.sys.platform", "linux"):
                self.assertEqual(
                    default_memory_path(),
                    home / ".config" / "choosier" / DEFAULT_FILENAME,
                )
            with patch("choosier.path_memory.sys.platform", "darwin"):
                self.assertEqual(
                    default_memory_path(),
                    home
                    / "Library"
                    / "Application Support"
                    / "choosier"
                    / DEFAULT_FILENAME,
                )
            with patch("choosier.path_memory.sys.platform", "win32"):
                self.assertEqual(
                    default_memory_path(),
                    home / ".config" / "choosier" / DEFAULT_FILENAME,
                )

    def test_default_path_honors_xdg_and_appdata(self) -> None:
        home = self.root / "home"
        xdg = self.root / "xdg"
        appdata = self.root / "appdata"
        with patch.dict(
            os.environ,
            {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
                "APPDATA": str(appdata),
            },
            clear=True,
        ):
            with patch("choosier.path_memory.sys.platform", "linux"):
                self.assertEqual(
                    default_memory_path(),
                    xdg / "choosier" / DEFAULT_FILENAME,
                )
            with patch("choosier.path_memory.sys.platform", "win32"):
                self.assertEqual(
                    default_memory_path(),
                    appdata / "choosier" / DEFAULT_FILENAME,
                )

    def test_relative_xdg_is_ignored(self) -> None:
        home = self.root / "home"
        with patch.dict(
            os.environ,
            {"HOME": str(home), "XDG_CONFIG_HOME": "relative/config"},
            clear=True,
        ):
            with patch("choosier.path_memory.sys.platform", "linux"):
                self.assertEqual(
                    default_memory_path(),
                    home / ".config" / "choosier" / DEFAULT_FILENAME,
                )

    def test_environment_override_wins(self) -> None:
        with patch.dict(
            os.environ,
            {ENV_OVERRIDE: str(self.root / "elsewhere" / "memory.json")},
        ):
            self.assertEqual(
                default_memory_path(),
                self.root / "elsewhere" / "memory.json",
            )
        with patch.dict(os.environ, {ENV_OVERRIDE: "~/memory.json"}):
            self.assertEqual(default_memory_path(), Path("~/memory.json").expanduser())
        with patch.dict(
            os.environ,
            {"HOME": str(self.root / "home"), ENV_OVERRIDE: ""},
        ):
            self.assertNotEqual(default_memory_path(), Path(""))

    def test_canonical_path_normalizes_spellings(self) -> None:
        spaced = self.root / "folder with space – ü"
        spaced.mkdir()
        self.assertEqual(canonical_path(str(spaced) + "///"), spaced.resolve())
        self.assertEqual(canonical_path(spaced / "sub" / ".."), spaced.resolve())
        self.assertEqual(
            canonical_path(Path("relative")),
            (Path.cwd() / "relative").resolve(),
        )

    def test_canonical_path_resolves_symlinks(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are not available")
        link = self.root / "link"
        try:
            link.symlink_to(self.folder, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks cannot be created here")
        self.assertEqual(canonical_path(link), self.folder.resolve())

    def test_is_usable_directory(self) -> None:
        self.assertTrue(is_usable_directory(self.folder))
        self.assertFalse(is_usable_directory(self.root / "missing"))
        file_path = self.root / "file.txt"
        file_path.write_text("x", encoding="utf-8")
        self.assertFalse(is_usable_directory(file_path))

    def test_unreadable_directory_is_not_usable(self) -> None:
        self._skip_permission_checks()
        locked = self.root / "locked"
        locked.mkdir()
        locked.chmod(0o000)
        self.addCleanup(locked.chmod, 0o700)
        self.assertFalse(is_usable_directory(locked))

    # --- format, ordering, pruning, startup ----------------------------

    def test_missing_file_is_empty_without_warning(self) -> None:
        snapshot = self.memory.snapshot()
        self.assertEqual(snapshot, MemorySnapshot((), None))

    def test_malformed_documents_are_empty_with_a_warning(self) -> None:
        documents = (
            "{not json",
            "[]",
            '{"version": 2, "recent": []}',
            '{"version": 1, "recent": "nope"}',
            '{"recent": []}',
        )
        for text in documents:
            with self.subTest(text=text):
                self._write_raw(text)
                snapshot = self.memory.snapshot()
                self.assertEqual(snapshot.recent, ())
                self.assertEqual(snapshot.warning, READ_WARNING)
                self.assertEqual(self.memory_file.read_text(encoding="utf-8"), text)

    def test_invalid_elements_are_dropped_and_deduplicated(self) -> None:
        self._write_raw(
            json.dumps(
                {
                    "version": 1,
                    "recent": [
                        str(self.folder),
                        str(self.folder) + "/",
                        "relative/path",
                        "",
                        42,
                        str(self._folder("second")),
                    ],
                }
            )
        )
        snapshot = self.memory.snapshot()
        self.assertEqual(
            snapshot.recent,
            (str(self.folder.resolve()), str((self.root / "second").resolve())),
        )
        self.assertIsNone(snapshot.warning)

    def test_order_is_preserved_and_truncated_to_cap(self) -> None:
        folders = [self._folder(f"f{index:02d}") for index in range(MAX_RECENT + 2)]
        self._write_raw(
            json.dumps(
                {"version": 1, "recent": [str(folder.resolve()) for folder in folders]}
            )
        )
        snapshot = self.memory.snapshot()
        self.assertEqual(len(snapshot.recent), MAX_RECENT)
        self.assertEqual(
            list(snapshot.recent),
            [str(folder.resolve()) for folder in folders[:MAX_RECENT]],
        )

    def test_record_moves_reuse_to_the_top(self) -> None:
        first = self._folder("first")
        second = self._folder("second")
        self.memory.record(first)
        self.memory.record(second)
        result = self.memory.record(first)
        self.assertTrue(result.ok)
        self.assertEqual(
            self.memory.snapshot().recent,
            (str(first.resolve()), str(second.resolve())),
        )

    def test_record_caps_and_evicts_the_oldest(self) -> None:
        folders = [self._folder(f"f{index:02d}") for index in range(MAX_RECENT + 2)]
        for folder in folders:
            self.memory.record(folder)
        snapshot = self.memory.snapshot()
        self.assertEqual(len(snapshot.recent), MAX_RECENT)
        self.assertEqual(snapshot.recent[0], str(folders[-1].resolve()))
        self.assertNotIn(str(folders[0].resolve()), snapshot.recent)
        self.assertNotIn(str(folders[1].resolve()), snapshot.recent)

    def test_record_persists_across_instances(self) -> None:
        self.memory.record(self.folder)
        self.assertEqual(
            PathMemory(self.memory_file).snapshot().recent,
            (str(self.folder.resolve()),),
        )

    def test_missing_record_is_not_created_by_reads(self) -> None:
        self.memory.snapshot()
        self.assertFalse(self.memory_file.exists())

    def test_snapshot_prunes_unavailable_entries(self) -> None:
        first = self._folder("first")
        second = self._folder("second")
        self.memory.record(first)
        self.memory.record(second)
        second.rmdir()
        snapshot = self.memory.snapshot()
        self.assertEqual(snapshot.recent, (str(first.resolve()),))
        self.assertEqual(snapshot.warning, "Skipped 1 unavailable remembered folder.")
        stored = json.loads(self.memory_file.read_text(encoding="utf-8"))
        self.assertEqual(stored["recent"], [str(first.resolve())])

    def test_startup_uses_the_next_valid_recent(self) -> None:
        first = self._folder("first")
        second = self._folder("second")
        third = self._folder("third")
        self.memory.record(first)
        self.memory.record(second)
        self.memory.record(third)
        third.rmdir()
        fallback = self.root / "fallback"
        fallback.mkdir()
        resolution = self.memory.startup(fallback)
        self.assertEqual(resolution.path, second.resolve())
        self.assertEqual(resolution.source, "recent")
        self.assertIsNotNone(resolution.warning)

    def test_startup_falls_back_when_nothing_is_valid(self) -> None:
        first = self._folder("first")
        self.memory.record(first)
        first.rmdir()
        fallback = self.root / "fallback"
        fallback.mkdir()
        resolution = self.memory.startup(fallback)
        self.assertEqual(resolution.path, fallback)
        self.assertEqual(resolution.source, "default")
        self.assertIsNotNone(resolution.warning)

    def test_startup_is_clean_with_no_memory(self) -> None:
        fallback = self.root / "fallback"
        fallback.mkdir()
        resolution = self.memory.startup(fallback)
        self.assertEqual(resolution.path, fallback)
        self.assertEqual(resolution.source, "default")
        self.assertIsNone(resolution.warning)

    def test_clear_persists_an_empty_record(self) -> None:
        self.memory.record(self.folder)
        result = self.memory.clear()
        self.assertTrue(result.ok)
        self.assertTrue(result.changed)
        self.assertEqual(self.memory.snapshot(), MemorySnapshot((), None))
        self.assertEqual(
            json.loads(self.memory_file.read_text(encoding="utf-8")),
            {"version": 1, "recent": []},
        )
        self.assertFalse(self.memory.clear().changed)

    def test_remove_deletes_only_the_matching_identity(self) -> None:
        first = self._folder("first")
        second = self._folder("second")
        self.memory.record(first)
        self.memory.record(second)
        result = self.memory.remove(str(first) + "/")
        self.assertTrue(result.ok)
        self.assertTrue(result.changed)
        self.assertEqual(self.memory.snapshot().recent, (str(second.resolve()),))
        self.assertFalse(self.memory.remove(first).changed)
        self.assertEqual(self.memory.snapshot().recent, (str(second.resolve()),))

    def test_removing_the_most_recent_uses_the_next_one_at_launch(self) -> None:
        first = self._folder("first")
        second = self._folder("second")
        self.memory.record(first)
        self.memory.record(second)
        fallback = self._folder("fallback")
        self.assertEqual(self.memory.startup(fallback).path, second.resolve())

        self.memory.remove(second)

        resolution = self.memory.startup(fallback)
        self.assertEqual(resolution.path, first.resolve())
        self.assertEqual(resolution.source, "recent")
        self.assertIsNone(resolution.warning)
        self.assertEqual(self.memory.snapshot().recent, (str(first.resolve()),))

    def test_clear_restores_first_run_startup_behavior(self) -> None:
        self.memory.record(self._folder("first"))
        self.assertTrue(self.memory.clear().ok)
        fallback = self._folder("fallback")

        resolution = self.memory.startup(fallback)

        self.assertEqual(resolution.path, fallback)
        self.assertEqual(resolution.source, "default")
        self.assertIsNone(resolution.warning)
        self.assertEqual(self.memory.snapshot(), MemorySnapshot((), None))
        self.assertEqual(
            json.loads(self.memory_file.read_text(encoding="utf-8")),
            {"version": 1, "recent": []},
        )

    def test_record_contains_only_version_and_folder_paths(self) -> None:
        folder = self._folder("private")
        file_name = "secret-report.txt"
        (folder / file_name).write_text("contents", encoding="utf-8")
        log = self._folder("history")
        (log / ".choosier.jsonl").write_text(
            '{"timestamp": "2026-11-12T00:00:00", "item": "secret-report.txt"}\n',
            encoding="utf-8",
        )
        self.assertTrue(self.memory.record(folder).ok)

        stored = json.loads(self.memory_file.read_text(encoding="utf-8"))

        self.assertEqual(set(stored), {"version", "recent"})
        self.assertEqual(stored["version"], 1)
        self.assertEqual(stored["recent"], [str(folder.resolve())])
        text = self.memory_file.read_text(encoding="utf-8")
        self.assertNotIn(file_name, text)
        self.assertNotIn(".choosier.jsonl", text)
        self.assertNotIn("timestamp", text)

    # --- failure behavior ----------------------------------------------

    def test_record_rejects_missing_and_non_directory_targets(self) -> None:
        missing = self.memory.record(self.root / "missing")
        self.assertFalse(missing.ok)
        self.assertEqual(missing.notice, RECORD_WARNING)
        file_path = self.root / "file.txt"
        file_path.write_text("x", encoding="utf-8")
        self.assertFalse(self.memory.record(file_path).ok)
        self.assertFalse(self.memory_file.exists())

    def test_record_failure_leaves_the_previous_document(self) -> None:
        self._skip_permission_checks()
        self.memory.record(self.folder)
        before = self.memory_file.read_bytes()
        self.memory_file.parent.chmod(0o500)
        self.addCleanup(self.memory_file.parent.chmod, 0o700)
        result = self.memory.record(self._folder("second"))
        self.assertFalse(result.ok)
        self.assertEqual(result.notice, RECORD_WARNING)
        self.memory_file.parent.chmod(0o700)
        self.assertEqual(self.memory_file.read_bytes(), before)

    def test_remove_and_clear_fail_with_notices(self) -> None:
        self._skip_permission_checks()
        self.memory.record(self.folder)
        self.memory_file.parent.chmod(0o500)
        self.addCleanup(self.memory_file.parent.chmod, 0o700)
        remove = self.memory.remove(self.folder)
        self.assertFalse(remove.ok)
        self.assertEqual(remove.notice, UPDATE_WARNING)
        clear = self.memory.clear()
        self.assertFalse(clear.ok)
        self.assertEqual(clear.notice, UPDATE_WARNING)
        self.memory_file.parent.chmod(0o700)
        self.assertEqual(
            self.memory.snapshot().recent,
            (str(self.folder.resolve()),),
        )

    def test_corrupt_record_is_replaced_only_after_a_successful_mutation(self) -> None:
        self._write_raw("{broken")
        snapshot = self.memory.snapshot()
        self.assertEqual(snapshot.warning, READ_WARNING)
        self.assertEqual(self.memory_file.read_text(encoding="utf-8"), "{broken")
        self.assertTrue(self.memory.record(self.folder).ok)
        stored = json.loads(self.memory_file.read_text(encoding="utf-8"))
        self.assertEqual(stored, {"version": 1, "recent": [str(self.folder.resolve())]})

    def test_failed_replace_cleans_up_the_temporary_file(self) -> None:
        with patch("choosier.path_memory.os.replace", side_effect=OSError("boom")):
            result = self.memory.record(self.folder)
        self.assertFalse(result.ok)
        self.assertEqual(list(self.memory_file.parent.glob("*.tmp")), [])
        self.assertFalse(self.memory_file.exists())

    def test_record_file_mode_is_private(self) -> None:
        self._skip_permission_checks()
        self.memory.record(self.folder)
        self.assertEqual(
            stat.S_IMODE(self.memory_file.stat().st_mode),
            0o600,
        )

    def test_directory_in_place_of_record_is_a_warning(self) -> None:
        self.memory_file.mkdir(parents=True)
        snapshot = self.memory.snapshot()
        self.assertEqual(snapshot.recent, ())
        self.assertEqual(snapshot.warning, READ_WARNING)

    def test_concurrent_records_keep_a_valid_unique_list(self) -> None:
        folders = [self._folder(f"shared{index:02d}") for index in range(9)]
        groups = [folders[index : index + 3] for index in range(0, 9, 3)]
        context = multiprocessing.get_context("fork")
        processes = [
            context.Process(
                target=_record_folders,
                args=(str(self.memory_file), [str(folder) for folder in group]),
            )
            for group in groups
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=30)
            self.assertEqual(process.exitcode, 0)
        stored = json.loads(self.memory_file.read_text(encoding="utf-8"))
        self.assertEqual(stored["version"], 1)
        recent = stored["recent"]
        self.assertEqual(len(recent), len(set(recent)))
        self.assertEqual(set(recent), {str(folder.resolve()) for folder in folders})
        self.assertLessEqual(len(recent), MAX_RECENT)


if __name__ == "__main__":
    unittest.main()
