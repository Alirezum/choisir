"""Tests for the shared skip selection and its validation rules."""

import unittest

from choosier.skip import (
    MAX_SKIPPED_ENTRIES,
    SKIP_COOLDOWN_SECONDS,
    SkipSelection,
    SkipValidationError,
    normalize_skips,
)


class SkipSelectionTest(unittest.TestCase):
    def test_empty_default(self) -> None:
        selection = SkipSelection()
        self.assertEqual(selection.names, frozenset())
        self.assertFalse(selection.is_active)

    def test_cooldown_is_ten_minutes(self) -> None:
        self.assertEqual(SKIP_COOLDOWN_SECONDS, 600)
        self.assertEqual(MAX_SKIPPED_ENTRIES, 20000)


class NormalizeSkipsTest(unittest.TestCase):
    def test_accepts_and_sorts_nothing(self) -> None:
        selection = normalize_skips(["beta.txt", "alpha", "beta.txt"])
        self.assertEqual(selection.names, frozenset({"alpha", "beta.txt"}))
        self.assertTrue(selection.is_active)

    def test_accepts_names_with_spaces_unicode_and_punctuation(self) -> None:
        names = ["a b.txt", "café", "what?!.md", "日本"]
        self.assertEqual(normalize_skips(names).names, frozenset(names))

    def test_accepts_exactly_the_limit(self) -> None:
        names = [f"item-{index}" for index in range(MAX_SKIPPED_ENTRIES)]
        self.assertEqual(len(normalize_skips(names).names), MAX_SKIPPED_ENTRIES)

    def test_rejects_over_the_limit(self) -> None:
        names = [f"item-{index}" for index in range(MAX_SKIPPED_ENTRIES + 1)]
        with self.assertRaises(SkipValidationError):
            normalize_skips(names)

    def test_rejects_non_string(self) -> None:
        with self.assertRaises(SkipValidationError):
            normalize_skips([1])

    def test_rejects_empty_and_reserved_names(self) -> None:
        for value in ("", ".", ".."):
            with self.subTest(value=value):
                with self.assertRaises(SkipValidationError):
                    normalize_skips([value])

    def test_rejects_over_long_name(self) -> None:
        with self.assertRaises(SkipValidationError):
            normalize_skips(["x" * 1025])

    def test_accepts_maximum_length_name(self) -> None:
        self.assertEqual(len(normalize_skips(["x" * 1024]).names), 1)

    def test_rejects_slash_and_nul(self) -> None:
        for value in ("dir/name", "bad\x00name"):
            with self.subTest(value=value):
                with self.assertRaises(SkipValidationError):
                    normalize_skips([value])

    def test_field_is_skipped_entries(self) -> None:
        with self.assertRaises(SkipValidationError) as raised:
            normalize_skips([1])
        self.assertEqual(raised.exception.field, "skipped_entries")


if __name__ == "__main__":
    unittest.main()
