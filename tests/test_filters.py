"""Tests for choosier.filters: type keys, options, and exclusions."""

import unittest

from choosier.filters import (
    DIR_TYPE_KEY,
    FILTER_ENTRY_LIMIT,
    MAX_ENTRY_EXCLUSIONS,
    MAX_TYPE_EXCLUSIONS,
    MAX_VALUE_LENGTH,
    SUFFIXLESS_TYPE_KEY,
    CandidateEntry,
    FilterOptions,
    FilterSelection,
    FilterValidationError,
    build_filter_options,
    filter_candidates,
    normalize_exclusions,
    type_key_for,
    type_label,
)


def _entry(name: str, *, is_dir: bool = False) -> CandidateEntry:
    return CandidateEntry(
        name=name,
        is_dir=is_dir,
        type_key=type_key_for(name, is_dir=is_dir),
    )


class TypeKeyTest(unittest.TestCase):
    def test_directories_share_one_key(self) -> None:
        self.assertEqual(type_key_for("sub", is_dir=True), DIR_TYPE_KEY)

    def test_suffix_is_lowercased_and_includes_the_dot(self) -> None:
        self.assertEqual(type_key_for("photo.JPG", is_dir=False), "file:.jpg")
        self.assertEqual(type_key_for("Song.FLAC", is_dir=False), "file:.flac")

    def test_final_suffix_only(self) -> None:
        self.assertEqual(type_key_for("archive.tar.gz", is_dir=False), "file:.gz")

    def test_suffixless_file_has_its_own_key(self) -> None:
        self.assertEqual(type_key_for("README", is_dir=False), SUFFIXLESS_TYPE_KEY)
        self.assertEqual(type_key_for("name.", is_dir=False), SUFFIXLESS_TYPE_KEY)

    def test_directory_wins_over_suffix(self) -> None:
        self.assertEqual(type_key_for("folder.txt", is_dir=True), DIR_TYPE_KEY)


class TypeLabelTest(unittest.TestCase):
    def test_labels(self) -> None:
        self.assertEqual(type_label(DIR_TYPE_KEY), "Folders")
        self.assertEqual(type_label("file:.jpg"), ".jpg files")
        self.assertEqual(type_label(SUFFIXLESS_TYPE_KEY), "Files without an extension")


class BuildFilterOptionsTest(unittest.TestCase):
    def test_order_counts_and_entry_list(self) -> None:
        options = build_filter_options(
            [
                _entry("b.txt"),
                _entry("README"),
                _entry("a.jpg"),
                _entry("B.JPG"),
                _entry("sub", is_dir=True),
            ]
        )
        self.assertEqual(
            [(item.key, item.label, item.count) for item in options.types],
            [
                (DIR_TYPE_KEY, "Folders", 1),
                ("file:.jpg", ".jpg files", 2),
                ("file:.txt", ".txt files", 1),
                (SUFFIXLESS_TYPE_KEY, "Files without an extension", 1),
            ],
        )
        self.assertEqual(
            [(item.name, item.type_key) for item in options.entries],
            [
                ("B.JPG", "file:.jpg"),
                ("README", SUFFIXLESS_TYPE_KEY),
                ("a.jpg", "file:.jpg"),
                ("b.txt", "file:.txt"),
                ("sub", DIR_TYPE_KEY),
            ],
        )
        self.assertEqual(options.entries_total, 5)
        self.assertFalse(options.entries_truncated)

    def test_suffixless_files_sort_last(self) -> None:
        options = build_filter_options(
            [_entry("README"), _entry("z.bin"), _entry("a.aaa")]
        )
        self.assertEqual(
            [item.key for item in options.types],
            ["file:.aaa", "file:.bin", SUFFIXLESS_TYPE_KEY],
        )

    def test_empty_folder(self) -> None:
        options = build_filter_options([])
        self.assertEqual(options, FilterOptions())
        self.assertEqual(options.entries_total, 0)
        self.assertFalse(options.entries_truncated)

    def test_entry_cap_and_truncation_flag(self) -> None:
        entries = [_entry(f"f{index:05d}") for index in range(FILTER_ENTRY_LIMIT + 5)]
        options = build_filter_options(entries)
        self.assertEqual(len(options.entries), FILTER_ENTRY_LIMIT)
        self.assertEqual(options.entries_total, FILTER_ENTRY_LIMIT + 5)
        self.assertTrue(options.entries_truncated)
        self.assertEqual(options.entries[0].name, "f00000")
        self.assertEqual(options.entries[-1].name, f"f{FILTER_ENTRY_LIMIT - 1:05d}")

    def test_exactly_at_the_cap_is_not_truncated(self) -> None:
        entries = [_entry(f"f{index:05d}") for index in range(FILTER_ENTRY_LIMIT)]
        options = build_filter_options(entries)
        self.assertEqual(len(options.entries), FILTER_ENTRY_LIMIT)
        self.assertFalse(options.entries_truncated)

    def test_two_hundred_types_are_complete_and_ordered(self) -> None:
        entries = [_entry(f"file.{index:03d}") for index in range(200)]
        options = build_filter_options(entries)
        self.assertEqual(len(options.types), 200)
        self.assertEqual(
            [item.key for item in options.types],
            [f"file:.{index:03d}" for index in range(200)],
        )
        self.assertTrue(all(item.count == 1 for item in options.types))


class FilterCandidatesTest(unittest.TestCase):
    def test_empty_selection_keeps_everything(self) -> None:
        entries = [_entry("b"), _entry("a")]
        kept = filter_candidates(entries, FilterSelection())
        self.assertEqual([entry.name for entry in kept], ["a", "b"])

    def test_type_and_entry_intersection(self) -> None:
        entries = [
            _entry("a.jpg"),
            _entry("b.jpg"),
            _entry("notes.txt"),
            _entry("sub", is_dir=True),
        ]
        selection = FilterSelection(
            excluded_types=frozenset({"file:.txt", "dir"}),
            excluded_entries=frozenset({"b.jpg"}),
        )
        kept = filter_candidates(entries, selection)
        self.assertEqual([entry.name for entry in kept], ["a.jpg"])
        self.assertTrue(selection.is_active)

    def test_result_is_sorted_by_exact_name(self) -> None:
        entries = [_entry("b"), _entry("A"), _entry("a")]
        kept = filter_candidates(entries, FilterSelection())
        self.assertEqual([entry.name for entry in kept], ["A", "a", "b"])


class NormalizeExclusionsTest(unittest.TestCase):
    def test_defaults_are_inactive(self) -> None:
        selection = normalize_exclusions([], [])
        self.assertEqual(selection, FilterSelection())
        self.assertFalse(selection.is_active)

    def test_valid_values_and_suffix_canonicalization(self) -> None:
        selection = normalize_exclusions(
            ["dir", "file:", "file:.JPG", "file:.jpg"],
            ["notes.txt", "notes.txt", "back\\slash"],
        )
        self.assertEqual(
            selection.excluded_types,
            frozenset({"dir", "file:", "file:.jpg"}),
        )
        self.assertEqual(
            selection.excluded_entries,
            frozenset({"notes.txt", "back\\slash"}),
        )
        self.assertTrue(selection.is_active)

    def test_unknown_but_well_formed_values_are_accepted(self) -> None:
        selection = normalize_exclusions(["file:.zzz"], ["missing.txt"])
        self.assertEqual(selection.excluded_types, frozenset({"file:.zzz"}))
        self.assertEqual(selection.excluded_entries, frozenset({"missing.txt"}))

    def test_value_length_boundary(self) -> None:
        at_limit = "file:." + "x" * (MAX_VALUE_LENGTH - len("file:."))
        self.assertEqual(len(at_limit), MAX_VALUE_LENGTH)
        selection = normalize_exclusions([at_limit], [])
        self.assertIn(at_limit, selection.excluded_types)

        over_limit = at_limit + "x"
        with self.assertRaises(FilterValidationError) as caught:
            normalize_exclusions([over_limit], [])
        self.assertEqual(caught.exception.field, "excluded_types")

        entry_at_limit = "x" * MAX_VALUE_LENGTH
        accepted = normalize_exclusions([], [entry_at_limit])
        self.assertIn(entry_at_limit, accepted.excluded_entries)
        with self.assertRaises(FilterValidationError) as caught:
            normalize_exclusions([], [entry_at_limit + "x"])
        self.assertEqual(caught.exception.field, "excluded_entries")

    def test_invalid_type_keys(self) -> None:
        for value in (
            "DIR",
            "file:jpg",
            "file:.",
            "file",
            "",
            "other:.jpg",
            "file:.jpg/evil",
            "file:.jp\x00g",
        ):
            with self.subTest(value=value):
                with self.assertRaises(FilterValidationError) as caught:
                    normalize_exclusions([value], [])
                self.assertEqual(caught.exception.field, "excluded_types")

    def test_invalid_entry_names(self) -> None:
        for value in ("", ".", "..", "dir/name", "nul\x00name"):
            with self.subTest(value=value):
                with self.assertRaises(FilterValidationError) as caught:
                    normalize_exclusions([], [value])
                self.assertEqual(caught.exception.field, "excluded_entries")

    def test_non_string_values_are_rejected(self) -> None:
        with self.assertRaises(FilterValidationError) as caught:
            normalize_exclusions([1], [])
        self.assertEqual(caught.exception.field, "excluded_types")
        with self.assertRaises(FilterValidationError) as caught:
            normalize_exclusions([], [None])
        self.assertEqual(caught.exception.field, "excluded_entries")

    def test_type_count_limit_is_checked_before_deduplication(self) -> None:
        at_limit = ["file:.jpg"] * MAX_TYPE_EXCLUSIONS
        selection = normalize_exclusions(at_limit, [])
        self.assertEqual(selection.excluded_types, frozenset({"file:.jpg"}))
        with self.assertRaises(FilterValidationError) as caught:
            normalize_exclusions([*at_limit, "file:.png"], [])
        self.assertEqual(caught.exception.field, "excluded_types")

    def test_entry_count_limit_is_checked_before_deduplication(self) -> None:
        at_limit = ["same"] * MAX_ENTRY_EXCLUSIONS
        selection = normalize_exclusions([], at_limit)
        self.assertEqual(selection.excluded_entries, frozenset({"same"}))
        with self.assertRaises(FilterValidationError) as caught:
            normalize_exclusions([], [*at_limit, "extra"])
        self.assertEqual(caught.exception.field, "excluded_entries")


if __name__ == "__main__":
    unittest.main()
