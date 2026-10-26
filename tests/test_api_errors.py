"""Tests for the standardized API error envelope."""

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient

    from choosier.web import create_app

    HAS_WEB = True
except ImportError:
    HAS_WEB = False

from choosier.storage import log_selection
from tests.api_contract_support import assert_error_envelope

PNG = b"\x89PNG\r\n\x1a\npngdata"
MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"


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

    def _archive(
        self,
        members: dict[str, bytes],
        name: str = "pics.zip",
    ) -> Path:
        folder = self.root / "archives"
        folder.mkdir(exist_ok=True)
        archive = folder / name
        with zipfile.ZipFile(archive, "w") as handle:
            for member, data in members.items():
                handle.writestr(member, data)
        return archive

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

    @unittest.expectedFailure  # Route errors migrate in T011.
    def test_browse_errors(self) -> None:
        before = self._log_bytes()
        missing = self.client.get(
            "/api/browse", params={"path": str(self.target / "missing")}
        )
        body = assert_error_envelope(self, missing, 404, "not_found")
        self.assertEqual(body["error"]["message"], "Not a directory")
        self._assert_log_unchanged(before)

        with patch(
            "choosier.web.Path.iterdir",
            side_effect=PermissionError("denied"),
        ):
            forbidden = self.client.get(
                "/api/browse", params={"path": str(self.target)}
            )
        body = assert_error_envelope(self, forbidden, 403, "forbidden")
        self.assertTrue(body["error"]["message"].startswith("Cannot list:"))
        self._assert_log_unchanged(before)

    @unittest.expectedFailure  # Route errors migrate in T011.
    def test_conflicting_filter_errors(self) -> None:
        before = self._log_bytes()
        state = self.client.get(
            "/api/state",
            params=self._params(files_only="true", dirs_only="true"),
        )
        body = assert_error_envelope(self, state, 400, "invalid_request")
        self.assertEqual(
            body["error"]["message"],
            "files_only and dirs_only are mutually exclusive",
        )
        self._assert_log_unchanged(before)

        pick = self.client.post(
            "/api/pick",
            json={
                "path": str(self.target),
                "files_only": True,
                "dirs_only": True,
            },
        )
        body = assert_error_envelope(self, pick, 400, "invalid_request")
        self.assertEqual(
            body["error"]["message"],
            "files_only and dirs_only are mutually exclusive",
        )
        self._assert_log_unchanged(before)

    @unittest.expectedFailure  # Route errors migrate in T011.
    def test_pick_log_error(self) -> None:
        log_selection("a", self.log)
        before = self._log_bytes()
        with patch(
            "choosier.web.log_selection",
            side_effect=OSError("disk full"),
        ):
            response = self.client.post(
                "/api/pick",
                json={"path": str(self.target), "seed": 1},
            )
        body = assert_error_envelope(self, response, 500, "internal_error")
        self.assertTrue(body["error"]["message"].startswith("Error writing log:"))
        self._assert_log_unchanged(before)

    @unittest.expectedFailure  # Route errors migrate in T011.
    def test_image_errors(self) -> None:
        before = self._log_bytes()

        missing = self.client.get(
            "/api/image", params={"path": str(self.root / "missing.png")}
        )
        body = assert_error_envelope(self, missing, 404, "not_found")
        self.assertEqual(body["error"]["message"], "Image is gone")

        archive = self._archive({"one.png": PNG})
        bad_index = self.client.get(
            "/api/image", params={"path": str(archive), "index": 99}
        )
        body = assert_error_envelope(self, bad_index, 404, "not_found")
        self.assertEqual(body["error"]["message"], "Image not found in archive")

        fake = self.root / "fake.zip"
        fake.write_bytes(b"not a zip")
        non_zip = self.client.get("/api/image", params={"path": str(fake), "index": 0})
        body = assert_error_envelope(self, non_zip, 400, "invalid_request")
        self.assertEqual(body["error"]["message"], "Not a zip archive")

        corrupt = self._archive({"one.png": PNG}, name="corrupt.zip")
        data = bytearray(corrupt.read_bytes())
        offset = data.find(PNG)
        self.assertGreaterEqual(offset, 0)
        data[offset] ^= 0xFF
        corrupt.write_bytes(data)
        corrupt_response = self.client.get(
            "/api/image", params={"path": str(corrupt), "index": 0}
        )
        body = assert_error_envelope(self, corrupt_response, 400, "invalid_request")
        self.assertTrue(body["error"]["message"].startswith("Not a valid archive:"))

        encrypted = self._archive({"one.png": PNG}, name="encrypted.zip")
        original_infolist = zipfile.ZipFile.infolist

        def encrypted_infolist(handle: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
            infos = original_infolist(handle)
            for info in infos:
                info.flag_bits |= 0x1
            return infos

        with patch.object(zipfile.ZipFile, "infolist", encrypted_infolist):
            encrypted_response = self.client.get(
                "/api/image", params={"path": str(encrypted), "index": 0}
            )
        body = assert_error_envelope(self, encrypted_response, 400, "invalid_request")
        self.assertEqual(
            body["error"]["message"],
            "Encrypted archive members are not supported",
        )

        image = self.root / "big.png"
        image.write_bytes(PNG)
        with patch("choosier.web.PREVIEW_MAX_IMAGE_BYTES", 8):
            oversized = self.client.get("/api/image", params={"path": str(image)})
        body = assert_error_envelope(self, oversized, 413, "payload_too_large")
        self.assertEqual(body["error"]["message"], "Image is too large to preview")

        doc = self.target / "doc.txt"
        doc.write_text("hello\n", encoding="utf-8")
        unsupported = self.client.get("/api/image", params={"path": str(doc)})
        body = assert_error_envelope(self, unsupported, 415, "unsupported_media_type")
        self.assertEqual(body["error"]["message"], "Not a supported image")

        fake_png = self.root / "fake.png"
        fake_png.write_bytes(PNG)
        undecodable = self.client.get(
            "/api/image",
            params={"path": str(fake_png), "variant": "thumb"},
        )
        body = assert_error_envelope(self, undecodable, 415, "unsupported_media_type")
        self.assertTrue(body["error"]["message"].startswith("Cannot decode image:"))
        self._assert_log_unchanged(before)

    @unittest.expectedFailure  # Route errors migrate in T011.
    def test_video_errors(self) -> None:
        before = self._log_bytes()
        missing = self.client.get(
            "/api/video", params={"path": str(self.root / "missing.mp4")}
        )
        body = assert_error_envelope(self, missing, 404, "not_found")
        self.assertEqual(body["error"]["message"], "Video is gone")

        doc = self.target / "doc.txt"
        doc.write_text("hello\n", encoding="utf-8")
        unsupported = self.client.get("/api/video", params={"path": str(doc)})
        body = assert_error_envelope(self, unsupported, 415, "unsupported_media_type")
        self.assertEqual(body["error"]["message"], "Not a supported video")

        fake = self.root / "fake.mp4"
        fake.write_bytes(b"not a video")
        mislabeled = self.client.get("/api/video", params={"path": str(fake)})
        body = assert_error_envelope(self, mislabeled, 415, "unsupported_media_type")
        self.assertEqual(body["error"]["message"], "Not a supported video")
        self._assert_log_unchanged(before)

    @unittest.expectedFailure  # Route errors migrate in T011.
    def test_open_errors(self) -> None:
        before = self._log_bytes()
        missing = self.client.post(
            "/api/open", json={"path": str(self.target / "missing")}
        )
        body = assert_error_envelope(self, missing, 404, "not_found")
        self.assertEqual(body["error"]["message"], "Entry is gone")

        with patch(
            "choosier.web.launch_path",
            side_effect=OSError("no opener"),
        ):
            failure = self.client.post(
                "/api/open", json={"path": str(self.target / "a")}
            )
        body = assert_error_envelope(self, failure, 500, "internal_error")
        self.assertTrue(body["error"]["message"].startswith("Cannot open:"))
        self._assert_log_unchanged(before)

    @unittest.expectedFailure  # Route errors migrate in T011.
    def test_history_write_errors(self) -> None:
        log_selection("a", self.log)
        before = self._log_bytes()

        with patch(
            "choosier.web.archive_log",
            side_effect=OSError("archive fail"),
        ):
            archived = self.client.post("/api/history/archive", params=self._params())
        body = assert_error_envelope(self, archived, 500, "internal_error")
        self.assertTrue(body["error"]["message"].startswith("Error archiving log:"))
        self._assert_log_unchanged(before)

        with patch(
            "choosier.web.reset_log",
            side_effect=OSError("reset fail"),
        ):
            cleared = self.client.delete("/api/history", params=self._params())
        body = assert_error_envelope(self, cleared, 500, "internal_error")
        self.assertTrue(body["error"]["message"].startswith("Error resetting log:"))
        self._assert_log_unchanged(before)

        with patch(
            "choosier.web.remove_log_item",
            side_effect=OSError("remove fail"),
        ):
            removed_item = self.client.delete(
                "/api/history/item", params=self._params(item="a")
            )
        body = assert_error_envelope(self, removed_item, 500, "internal_error")
        self.assertTrue(
            body["error"]["message"].startswith("Error removing history item:")
        )
        self._assert_log_unchanged(before)

        with patch(
            "choosier.web.remove_log_items",
            side_effect=OSError("batch fail"),
        ):
            removed_batch = self.client.post(
                "/api/history/remove",
                json={"path": str(self.target), "items": ["a"]},
            )
        body = assert_error_envelope(self, removed_batch, 500, "internal_error")
        self.assertTrue(
            body["error"]["message"].startswith("Error removing history items:")
        )
        self._assert_log_unchanged(before)

    @unittest.expectedFailure  # Range validation lands in T012.
    def test_malformed_range_returns_json_error(self) -> None:
        video = self.root / "clip.mp4"
        video.write_bytes(MP4)
        for header in ("garbage", "bytes=5-2"):
            with self.subTest(header=header):
                response = self.client.get(
                    "/api/video",
                    params={"path": str(video)},
                    headers={"Range": header},
                )
                body = assert_error_envelope(self, response, 400, "invalid_request")
                self.assertTrue(body["error"]["message"])
                self.assertNotIn(
                    "text/plain",
                    response.headers.get("content-type", ""),
                )

    @unittest.expectedFailure  # Range validation lands in T012.
    def test_unsatisfiable_range_returns_json_error(self) -> None:
        video = self.root / "clip.mp4"
        video.write_bytes(MP4)
        response = self.client.get(
            "/api/video",
            params={"path": str(video)},
            headers={"Range": "bytes=999999-"},
        )
        body = assert_error_envelope(self, response, 416, "range_not_satisfiable")
        self.assertTrue(body["error"]["message"])
        self.assertEqual(
            response.headers["content-range"],
            f"bytes */{len(MP4)}",
        )
        self.assertNotIn(
            "text/plain",
            response.headers.get("content-type", ""),
        )


if __name__ == "__main__":
    unittest.main()
