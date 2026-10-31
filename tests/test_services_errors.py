"""Direct tests for choosier.services.errors."""

import unittest

from choosier.services import FailureKind, ServiceError

EXPECTED_KINDS = {
    FailureKind.INVALID_INPUT: "invalid_input",
    FailureKind.FORBIDDEN: "forbidden",
    FailureKind.NOT_FOUND: "not_found",
    FailureKind.PAYLOAD_TOO_LARGE: "payload_too_large",
    FailureKind.UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
    FailureKind.RANGE_NOT_SATISFIABLE: "range_not_satisfiable",
    FailureKind.IO_ERROR: "io_error",
}


class FailureKindTest(unittest.TestCase):
    def test_every_failure_kind_has_the_contract_value(self) -> None:
        self.assertEqual(set(FailureKind), set(EXPECTED_KINDS))
        for kind, value in EXPECTED_KINDS.items():
            with self.subTest(kind=kind.name):
                self.assertEqual(kind.value, value)
                self.assertEqual(str(kind), value)


class ServiceErrorTest(unittest.TestCase):
    def test_propagates_kind_message_and_details(self) -> None:
        details = {"field": "name", "count": 2}
        error = ServiceError(FailureKind.NOT_FOUND, "Entry is gone", details)
        self.assertEqual(error.kind, FailureKind.NOT_FOUND)
        self.assertEqual(error.message, "Entry is gone")
        self.assertIs(error.details, details)
        self.assertEqual(str(error), "Entry is gone")
        self.assertEqual(error.args, ("Entry is gone",))

    def test_details_default_to_none(self) -> None:
        error = ServiceError(FailureKind.IO_ERROR, "boom")
        self.assertIsNone(error.details)

    def test_exception_exposes_no_transport_or_ui_state(self) -> None:
        error = ServiceError(FailureKind.FORBIDDEN, "Cannot list")
        self.assertEqual(
            set(vars(error)),
            {"kind", "message", "details"},
        )
        self.assertFalse(hasattr(error, "status_code"))
        self.assertFalse(hasattr(error, "status"))
        self.assertFalse(hasattr(error, "widget"))
        self.assertFalse(hasattr(error, "render"))


if __name__ == "__main__":
    unittest.main()
