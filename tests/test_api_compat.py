"""Compatibility tests for every existing successful API flow."""

import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient

    from choosier.web import create_app

    HAS_WEB = True
except ImportError:
    HAS_WEB = False

from tests.api_contract_support import (
    assert_value_matches_schema,
    contract_route,
    load_contract,
)

MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"


def _real_png(size: tuple[int, int] = (64, 48)) -> bytes:
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", size, (40, 120, 200)).save(buffer, "PNG")
    return buffer.getvalue()


@unittest.skipUnless(HAS_WEB, "web extra (fastapi) not installed")
class ApiSuccessCompatibilityTest(unittest.TestCase):
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
        self.contract = load_contract()

    def _params(self, **extra: str) -> dict[str, str]:
        params = {"path": str(self.target)}
        params.update(extra)
        return params

    def _assert_json_success(
        self,
        response: Any,
        method: str,
        path: str,
    ) -> dict[str, Any]:
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.headers.get("content-type", "").split(";", 1)[0],
            "application/json",
        )
        route = contract_route(self.contract, method, path)
        body = response.json()
        assert_value_matches_schema(
            self,
            body,
            route["success"]["schema"],
            self.contract,
            f"{method} {path}",
        )
        return cast(dict[str, Any], body)

    def _assert_binary_success(
        self,
        response: Any,
        method: str,
        path: str,
        expected_status: int,
    ) -> None:
        self.assertEqual(response.status_code, expected_status, response.text)
        route = contract_route(self.contract, method, path)
        for name, value in route["success"].get("headers", {}).items():
            self.assertEqual(response.headers[name.lower()], value)

    def _archive(self, members: dict[str, bytes], name: str = "pics.zip") -> Path:
        folder = self.root / "archives"
        folder.mkdir(exist_ok=True)
        archive = folder / name
        with zipfile.ZipFile(archive, "w") as handle:
            for member, data in members.items():
                handle.writestr(member, data)
        return archive

    def test_json_success_shapes(self) -> None:
        defaults = self.client.get("/api/defaults")
        self._assert_json_success(defaults, "GET", "/api/defaults")
        self.assertEqual(
            set(defaults.json()),
            {"path", "log_file"},
        )

        browse = self.client.get("/api/browse", params=self._params())
        self._assert_json_success(browse, "GET", "/api/browse")

        state = self.client.get("/api/state", params=self._params())
        state_body = self._assert_json_success(state, "GET", "/api/state")
        self.assertTrue(state_body["valid_path"])

        pick = self.client.post(
            "/api/pick",
            json={"path": str(self.target), "seed": 1, "dry_run": True},
        )
        pick_body = self._assert_json_success(pick, "POST", "/api/pick")
        self.assertEqual(pick_body["status"], "picked")

        preview = self.client.get(
            "/api/preview", params={"path": str(self.target / "a")}
        )
        self._assert_json_success(preview, "GET", "/api/preview")

        with patch("choosier.web.launch_path"):
            opened = self.client.post(
                "/api/open", json={"path": str(self.target / "a")}
            )
        self._assert_json_success(opened, "POST", "/api/open")

        archived = self.client.post("/api/history/archive", params=self._params())
        archive_body = self._assert_json_success(
            archived, "POST", "/api/history/archive"
        )
        self.assertIsNone(archive_body["backup"])

        cleared = self.client.delete("/api/history", params=self._params())
        clear_body = self._assert_json_success(cleared, "DELETE", "/api/history")
        self.assertFalse(clear_body["removed"])

        removed_item = self.client.delete(
            "/api/history/item", params=self._params(item="a")
        )
        item_body = self._assert_json_success(
            removed_item, "DELETE", "/api/history/item"
        )
        self.assertEqual(item_body["removed"], 0)

        removed_batch = self.client.post(
            "/api/history/remove",
            json={"path": str(self.target), "items": ["a"]},
        )
        batch_body = self._assert_json_success(
            removed_batch, "POST", "/api/history/remove"
        )
        self.assertEqual(batch_body["removed"], 0)

    def test_state_invalid_path_is_a_successful_domain_outcome(self) -> None:
        response = self.client.get(
            "/api/state", params={"path": str(self.target / "missing")}
        )
        body = self._assert_json_success(response, "GET", "/api/state")
        self.assertFalse(body["valid_path"])
        self.assertEqual(body["remaining"], [])
        self.assertEqual(body["remaining_total"], 0)
        self.assertEqual(body["history"], [])
        self.assertEqual(body["history_total"], 0)

    def test_pick_domain_outcomes_are_successful(self) -> None:
        invalid = self.client.post(
            "/api/pick", json={"path": str(self.target / "missing")}
        )
        invalid_body = self._assert_json_success(invalid, "POST", "/api/pick")
        self.assertEqual(invalid_body["status"], "invalid_path")
        self.assertIsNone(invalid_body["item"])
        self.assertFalse(invalid_body["logged"])

        empty_dir = self.root / "empty"
        empty_dir.mkdir()
        empty = self.client.post("/api/pick", json={"path": str(empty_dir)})
        self.assertEqual(
            self._assert_json_success(empty, "POST", "/api/pick")["status"],
            "empty",
        )

        lonely = self.root / "lonely"
        lonely.mkdir()
        (lonely / "only").touch()
        first = self.client.post("/api/pick", json={"path": str(lonely)})
        self.assertEqual(
            self._assert_json_success(first, "POST", "/api/pick")["status"],
            "picked",
        )
        second = self.client.post("/api/pick", json={"path": str(lonely)})
        self.assertEqual(
            self._assert_json_success(second, "POST", "/api/pick")["status"],
            "exhausted",
        )

    def test_preview_gone_and_empty_are_successful(self) -> None:
        gone = self.client.get(
            "/api/preview", params={"path": str(self.target / "missing")}
        )
        self.assertEqual(
            self._assert_json_success(gone, "GET", "/api/preview")["kind"],
            "gone",
        )

        empty_file = self.target / "empty.txt"
        empty_file.touch()
        empty = self.client.get("/api/preview", params={"path": str(empty_file)})
        self.assertEqual(
            self._assert_json_success(empty, "GET", "/api/preview")["kind"],
            "empty",
        )

    def test_image_success_preserves_bytes_and_webp_variants(self) -> None:
        original = _real_png()
        image = self.root / "photo.png"
        image.write_bytes(original)

        full = self.client.get("/api/image", params={"path": str(image)})
        self._assert_binary_success(full, "GET", "/api/image", 200)
        self.assertEqual(full.content, original)
        self.assertEqual(full.headers["content-type"], "image/png")

        thumb = self.client.get(
            "/api/image", params={"path": str(image), "variant": "thumb"}
        )
        self._assert_binary_success(thumb, "GET", "/api/image", 200)
        self.assertEqual(thumb.headers["content-type"], "image/webp")
        self.assertEqual(thumb.content[:4], b"RIFF")
        self.assertEqual(thumb.content[8:12], b"WEBP")

        preview = self.client.get(
            "/api/image", params={"path": str(image), "variant": "preview"}
        )
        self._assert_binary_success(preview, "GET", "/api/image", 200)
        self.assertEqual(preview.headers["content-type"], "image/webp")

    def test_archive_member_image_success(self) -> None:
        original = _real_png()
        archive = self._archive({"one.png": original})
        response = self.client.get(
            "/api/image", params={"path": str(archive), "index": 0}
        )
        self._assert_binary_success(response, "GET", "/api/image", 200)
        self.assertEqual(response.content, original)
        self.assertEqual(response.headers["content-type"], "image/png")

    def test_video_success_and_range_behavior(self) -> None:
        video = self.root / "clip.mp4"
        video.write_bytes(MP4)

        full = self.client.get("/api/video", params={"path": str(video)})
        self._assert_binary_success(full, "GET", "/api/video", 200)
        self.assertEqual(full.headers["content-type"], "video/mp4")
        self.assertEqual(full.content, MP4)

        single = self.client.get(
            "/api/video",
            params={"path": str(video)},
            headers={"Range": "bytes=0-3"},
        )
        self._assert_binary_success(single, "GET", "/api/video", 206)
        self.assertEqual(single.content, MP4[:4])
        self.assertEqual(
            single.headers["content-range"],
            f"bytes 0-3/{len(MP4)}",
        )

        suffix = self.client.get(
            "/api/video",
            params={"path": str(video)},
            headers={"Range": "bytes=-4"},
        )
        self._assert_binary_success(suffix, "GET", "/api/video", 206)
        self.assertEqual(suffix.content, MP4[-4:])

        multipart = self.client.get(
            "/api/video",
            params={"path": str(video)},
            headers={"Range": "bytes=0-1,3-4"},
        )
        self._assert_binary_success(multipart, "GET", "/api/video", 206)
        self.assertTrue(
            multipart.headers["content-type"].startswith("multipart/byteranges")
        )


if __name__ == "__main__":
    unittest.main()
