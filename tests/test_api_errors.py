"""Tests for the standardized API error envelope."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient

    from choosier.web import create_app

    HAS_WEB = True
except ImportError:
    HAS_WEB = False

from tests.api_contract_support import assert_error_envelope


@unittest.skipUnless(HAS_WEB, "web extra (fastapi) not installed")
class ApiErrorEnvelopeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / "target"
        self.target.mkdir()
        (self.target / "a").touch()
        (self.target / "b").touch()
        (self.target / "sub").mkdir()
        self.log = self.target / ".choosier.jsonl"
        self.client = TestClient(create_app())

    def _params(self, **extra: str) -> dict[str, str]:
        params = {"path": str(self.target)}
        params.update(extra)
        return params

    def _log_bytes(self) -> bytes | None:
        return self.log.read_bytes() if self.log.exists() else None

    def _assert_log_unchanged(self, before: bytes | None) -> None:
        self.assertEqual(self._log_bytes(), before)

    @unittest.expectedFailure  # Envelope handler lands in T009.
    def test_unknown_route_is_not_found(self) -> None:
        response = self.client.get("/api/nope")
        body = assert_error_envelope(self, response, 404, "not_found")
        self.assertEqual(body["error"]["message"], "Not Found")

    @unittest.expectedFailure  # Envelope handler lands in T009.
    def test_method_not_allowed_preserves_allow_header(self) -> None:
        response = self.client.post("/api/defaults")
        body = assert_error_envelope(self, response, 405, "method_not_allowed")
        self.assertEqual(body["error"]["message"], "Method Not Allowed")
        self.assertIn("GET", response.headers["allow"])

    @unittest.expectedFailure  # Validation handler lands in T010.
    def test_missing_query_is_validation_error(self) -> None:
        response = self.client.get("/api/state")
        body = assert_error_envelope(self, response, 422, "validation_error")
        self.assertTrue(
            body["error"]["message"].startswith("Request validation failed:")
        )
        issues = body["error"]["details"]["issues"]
        self.assertEqual(issues[0]["location"], ["query", "path"])
        self.assertEqual(issues[0]["message"], "Field required")
        self.assertEqual(issues[0]["type"], "missing")

    @unittest.expectedFailure  # Validation handler lands in T010.
    def test_malformed_json_is_validation_error(self) -> None:
        response = self.client.post(
            "/api/pick",
            content="{",
            headers={"Content-Type": "application/json"},
        )
        body = assert_error_envelope(self, response, 422, "validation_error")
        issues = body["error"]["details"]["issues"]
        self.assertEqual(issues[0]["location"][0], "body")
        self.assertEqual(issues[0]["type"], "json_invalid")

    @unittest.expectedFailure  # Envelope handler lands in T009.
    def test_unexpected_exception_is_internal_error(self) -> None:
        client = TestClient(create_app(), raise_server_exceptions=False)
        with patch(
            "choosier.web.read_log_entries",
            side_effect=RuntimeError("boom"),
        ):
            response = client.get("/api/state", params=self._params())
        body = assert_error_envelope(self, response, 500, "internal_error")
        self.assertEqual(body["error"]["message"], "Internal server error")


if __name__ == "__main__":
    unittest.main()
