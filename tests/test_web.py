"""Tests for choosier.web: JSON API behavior (no browser testing)."""

import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient

    from choosier.web import STATIC_DIR, create_app

    HAS_WEB = True
except ImportError:
    HAS_WEB = False

from choosier.path_memory import (
    READ_WARNING,
    RECORD_WARNING,
    PathMemory,
)
from choosier.storage import log_selection

PNG = b"\x89PNG\r\n\x1a\npngdata"
JPEG = b"\xff\xd8\xffjpegdata"
MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"


@unittest.skipUnless(HAS_WEB, "web extra (fastapi) not installed")
class WebApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
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

    def _archive(
        self, members: dict[str, bytes] | None = None, name: str = "pics.zip"
    ) -> Path:
        folder = Path(self.tmp.name) / "archives"
        folder.mkdir(exist_ok=True)
        archive = folder / name
        contents = {"one.png": PNG} if members is None else members
        with zipfile.ZipFile(archive, "w") as handle:
            for member, data in contents.items():
                handle.writestr(member, data)
        return archive

    def _real_png(self, size: tuple[int, int] = (640, 480)) -> bytes:
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", size, (40, 120, 200)).save(buffer, "PNG")
        return buffer.getvalue()

    def test_defaults_echo_initial_values(self) -> None:
        client = TestClient(create_app("/somewhere", "/tmp/history.jsonl"))
        response = client.get("/api/defaults")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "path": "/somewhere",
                "log_file": "/tmp/history.jsonl",
                "path_warning": None,
            },
        )

    def test_state_lists_remaining_sorted(self) -> None:
        response = self.client.get("/api/state", params=self._params())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["valid_path"])
        self.assertEqual(body["remaining"], ["a", "b", "sub"])
        self.assertEqual(body["remaining_total"], 3)
        self.assertEqual(body["history"], [])
        self.assertEqual(body["log_file"], str(self.log))

    def test_state_invalid_path_is_not_an_error(self) -> None:
        response = self.client.get(
            "/api/state", params={"path": str(self.target / "nope")}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["valid_path"])
        self.assertEqual(body["remaining"], [])

    def test_state_respects_filters(self) -> None:
        files = self.client.get(
            "/api/state", params=self._params(files_only="true")
        ).json()
        dirs = self.client.get(
            "/api/state", params=self._params(dirs_only="true")
        ).json()
        self.assertEqual(files["remaining"], ["a", "b"])
        self.assertEqual(dirs["remaining"], ["sub"])
        conflict = self.client.get(
            "/api/state",
            params=self._params(files_only="true", dirs_only="true"),
        )
        self.assertEqual(conflict.status_code, 400)

    def test_state_reflects_logged_history(self) -> None:
        self.client.post("/api/pick", json={"path": str(self.target), "seed": 1})
        body = self.client.get("/api/state", params=self._params()).json()
        self.assertEqual(body["remaining_total"], 2)
        self.assertEqual(body["history_total"], 1)

    def test_state_history_is_structured(self) -> None:
        log_selection("a", self.log)
        body = self.client.get("/api/state", params=self._params()).json()
        self.assertEqual(body["history_total"], 1)
        entry = body["history"][0]
        self.assertEqual(entry["item"], "a")
        self.assertIsNotNone(entry["timestamp"])
        self.assertIn("a", entry["display"])

    def test_pick_logs_and_previews(self) -> None:
        response = self.client.post(
            "/api/pick", json={"path": str(self.target), "seed": 1}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "picked")
        self.assertIn(body["item"], {"a", "b", "sub"})
        self.assertTrue(body["logged"])
        self.assertIsNotNone(body["preview"])
        self.assertTrue(self.log.exists())

    def test_pick_dry_run_does_not_log(self) -> None:
        response = self.client.post(
            "/api/pick",
            json={"path": str(self.target), "seed": 2, "dry_run": True},
        )
        body = response.json()
        self.assertEqual(body["status"], "picked")
        self.assertFalse(body["logged"])
        self.assertFalse(self.log.exists())

    def test_pick_is_deterministic_with_seed(self) -> None:
        first = self.client.post(
            "/api/pick",
            json={"path": str(self.target), "seed": 7, "dry_run": True},
        ).json()
        second = self.client.post(
            "/api/pick",
            json={"path": str(self.target), "seed": 7, "dry_run": True},
        ).json()
        self.assertEqual(first["item"], second["item"])

    def test_pick_empty_directory(self) -> None:
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        body = self.client.post("/api/pick", json={"path": str(empty)}).json()
        self.assertEqual(body["status"], "empty")

    def test_pick_exhausted(self) -> None:
        lonely = Path(self.tmp.name) / "lonely"
        lonely.mkdir()
        (lonely / "only").touch()
        first = self.client.post("/api/pick", json={"path": str(lonely)}).json()
        second = self.client.post("/api/pick", json={"path": str(lonely)}).json()
        self.assertEqual(first["status"], "picked")
        self.assertEqual(second["status"], "exhausted")

    def test_pick_invalid_path(self) -> None:
        body = self.client.post(
            "/api/pick", json={"path": str(self.target / "nope")}
        ).json()
        self.assertEqual(body["status"], "invalid_path")

    def test_pick_conflicting_filters(self) -> None:
        response = self.client.post(
            "/api/pick",
            json={
                "path": str(self.target),
                "files_only": True,
                "dirs_only": True,
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_preview_kinds(self) -> None:
        doc = self.target / "doc.txt"
        doc.write_text("hello\n", encoding="utf-8")
        self.assertEqual(
            self.client.get("/api/preview", params={"path": str(doc)}).json()["kind"],
            "text",
        )
        self.assertEqual(
            self.client.get(
                "/api/preview", params={"path": str(self.target / "sub")}
            ).json()["kind"],
            "directory",
        )
        self.assertEqual(
            self.client.get(
                "/api/preview", params={"path": str(self.target / "gone")}
            ).json()["kind"],
            "gone",
        )

    def test_preview_archive_lists_images(self) -> None:
        archive = self._archive({"one.png": PNG, "two.jpg": JPEG, "notes.txt": b"hi"})
        body = self.client.get("/api/preview", params={"path": str(archive)}).json()
        self.assertEqual(body["kind"], "archive")
        self.assertEqual(body["image_total"], 2)
        self.assertEqual(
            [image["name"] for image in body["images"]], ["one.png", "two.jpg"]
        )
        self.assertEqual(body["images"][0]["index"], 0)
        self.assertEqual(body["images"][0]["media_type"], "image/png")

    def test_image_endpoint_serves_archive_member(self) -> None:
        archive = self._archive()
        response = self.client.get(
            "/api/image", params={"path": str(archive), "index": 0}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PNG)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def test_image_endpoint_serves_standalone_image(self) -> None:
        image = Path(self.tmp.name) / "photo.jpg"
        image.write_bytes(JPEG)
        response = self.client.get("/api/image", params={"path": str(image)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, JPEG)
        self.assertEqual(response.headers["content-type"], "image/jpeg")

    def test_thumbnail_endpoint_returns_small_webp(self) -> None:
        from PIL import Image

        image = Path(self.tmp.name) / "photo.png"
        original = self._real_png()
        image.write_bytes(original)
        response = self.client.get(
            "/api/image", params={"path": str(image), "variant": "thumb"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/webp")
        self.assertEqual(response.content[:4], b"RIFF")
        self.assertEqual(response.content[8:12], b"WEBP")
        self.assertLess(len(response.content), len(original))
        with Image.open(BytesIO(response.content)) as thumbnail:
            self.assertLessEqual(max(thumbnail.size), 480)

    def test_preview_variant_returns_large_webp(self) -> None:
        from PIL import Image

        image = Path(self.tmp.name) / "photo.png"
        image.write_bytes(self._real_png((2400, 1800)))
        response = self.client.get(
            "/api/image", params={"path": str(image), "variant": "preview"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/webp")
        with Image.open(BytesIO(response.content)) as preview:
            self.assertEqual(preview.size, (1600, 1200))

    def test_thumbnail_endpoint_serves_archive_member(self) -> None:
        archive = self._archive({"one.png": self._real_png()})
        response = self.client.get(
            "/api/image",
            params={"path": str(archive), "index": 0, "variant": "thumb"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/webp")

    def test_thumbnail_endpoint_rejects_undecodable_image(self) -> None:
        fake = Path(self.tmp.name) / "fake.png"
        fake.write_bytes(PNG)
        response = self.client.get(
            "/api/image", params={"path": str(fake), "variant": "thumb"}
        )
        self.assertEqual(response.status_code, 415)

    def test_image_endpoint_rejects_bad_index(self) -> None:
        archive = self._archive()
        response = self.client.get(
            "/api/image", params={"path": str(archive), "index": 99}
        )
        self.assertEqual(response.status_code, 404)

    def test_image_endpoint_rejects_non_image_member(self) -> None:
        archive = self._archive({"notes.txt": b"hi"})
        response = self.client.get(
            "/api/image", params={"path": str(archive), "index": 0}
        )
        self.assertEqual(response.status_code, 415)

    def test_image_endpoint_rejects_oversized_image(self) -> None:
        image = Path(self.tmp.name) / "big.png"
        image.write_bytes(PNG)
        with patch("choosier.preview.PREVIEW_MAX_IMAGE_BYTES", 8):
            response = self.client.get("/api/image", params={"path": str(image)})
        self.assertEqual(response.status_code, 413)

    def test_image_endpoint_rejects_missing_image(self) -> None:
        response = self.client.get(
            "/api/image", params={"path": str(self.target / "gone.png")}
        )
        self.assertEqual(response.status_code, 404)

    def test_image_endpoint_rejects_non_image_file(self) -> None:
        doc = self.target / "doc.txt"
        doc.write_text("hello\n", encoding="utf-8")
        response = self.client.get("/api/image", params={"path": str(doc)})
        self.assertEqual(response.status_code, 415)

    def test_preview_reports_video(self) -> None:
        video = Path(self.tmp.name) / "clip.mp4"
        video.write_bytes(MP4)
        response = self.client.get("/api/preview", params={"path": str(video)})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["kind"], "video")
        self.assertEqual(
            body["video"],
            {"name": "clip.mp4", "media_type": "video/mp4", "size": len(MP4)},
        )
        self.assertIn("video/mp4", body["text"])

    def test_video_endpoint_streams_file(self) -> None:
        video = Path(self.tmp.name) / "clip.mp4"
        video.write_bytes(MP4)
        response = self.client.get("/api/video", params={"path": str(video)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "video/mp4")
        self.assertEqual(response.headers["accept-ranges"], "bytes")
        self.assertEqual(response.content, MP4)

    def test_video_endpoint_supports_range(self) -> None:
        video = Path(self.tmp.name) / "clip.mp4"
        video.write_bytes(MP4)
        response = self.client.get(
            "/api/video",
            params={"path": str(video)},
            headers={"Range": "bytes=0-3"},
        )
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, MP4[:4])
        self.assertEqual(response.headers["content-range"], f"bytes 0-3/{len(MP4)}")

    def test_video_endpoint_rejects_non_video(self) -> None:
        doc = self.target / "doc.txt"
        doc.write_text("hello\n", encoding="utf-8")
        response = self.client.get("/api/video", params={"path": str(doc)})
        self.assertEqual(response.status_code, 415)

    def test_video_endpoint_rejects_mislabeled_video(self) -> None:
        video = Path(self.tmp.name) / "fake.mp4"
        video.write_bytes(b"not a video")
        response = self.client.get("/api/video", params={"path": str(video)})
        self.assertEqual(response.status_code, 415)

    def test_video_endpoint_rejects_missing_video(self) -> None:
        response = self.client.get(
            "/api/video", params={"path": str(self.target / "gone.mp4")}
        )
        self.assertEqual(response.status_code, 404)

    def test_image_endpoint_rejects_non_archive(self) -> None:
        fake = Path(self.tmp.name) / "fake.zip"
        fake.write_bytes(b"not a zip")
        response = self.client.get("/api/image", params={"path": str(fake), "index": 0})
        self.assertEqual(response.status_code, 400)

    def test_browse_lists_dirs_first(self) -> None:
        response = self.client.get("/api/browse", params={"path": str(self.target)})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["path"], str(self.target))
        self.assertEqual(body["parent"], str(self.target.parent))
        self.assertEqual([e["name"] for e in body["entries"]], ["sub", "a", "b"])
        self.assertFalse(body["entries"][1]["is_dir"])

    def test_browse_missing_path_is_404(self) -> None:
        response = self.client.get(
            "/api/browse", params={"path": str(self.target / "nope")}
        )
        self.assertEqual(response.status_code, 404)

    def test_history_archive_then_clear(self) -> None:
        self.client.post("/api/pick", json={"path": str(self.target), "seed": 1})
        archive = self.client.post("/api/history/archive", params=self._params()).json()
        self.assertIsNotNone(archive["backup"])
        self.assertTrue(archive["backup"].endswith(".jsonl.old"))
        self.assertFalse(self.log.exists())
        self.client.post("/api/pick", json={"path": str(self.target), "seed": 2})
        cleared = self.client.delete("/api/history", params=self._params()).json()
        self.assertTrue(cleared["removed"])
        self.assertFalse(self.log.exists())
        again = self.client.delete("/api/history", params=self._params()).json()
        self.assertFalse(again["removed"])

    def test_archive_without_log_reports_none(self) -> None:
        body = self.client.post("/api/history/archive", params=self._params()).json()
        self.assertIsNone(body["backup"])

    def test_remove_history_item_removes_all_matching_entries(self) -> None:
        for item in ("a", "b", "a"):
            log_selection(item, self.log)
        response = self.client.delete(
            "/api/history/item", params=self._params(item="a")
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["item"], "a")
        self.assertEqual(body["removed"], 2)
        state = self.client.get("/api/state", params=self._params()).json()
        self.assertEqual(state["history_total"], 1)
        self.assertEqual([entry["item"] for entry in state["history"]], ["b"])
        self.assertIn("a", state["remaining"])
        self.assertNotIn("b", state["remaining"])

    def test_remove_history_item_unknown_is_noop(self) -> None:
        log_selection("a", self.log)
        before = self.log.read_bytes()
        body = self.client.delete(
            "/api/history/item", params=self._params(item="missing")
        ).json()
        self.assertEqual(body["removed"], 0)
        self.assertEqual(self.log.read_bytes(), before)

    def test_remove_history_item_without_log(self) -> None:
        body = self.client.delete(
            "/api/history/item", params=self._params(item="a")
        ).json()
        self.assertEqual(body["removed"], 0)
        self.assertFalse(self.log.exists())

    def test_remove_history_item_special_name(self) -> None:
        log_selection("a - b", self.log)
        body = self.client.delete(
            "/api/history/item", params=self._params(item="a - b")
        ).json()
        self.assertEqual(body["removed"], 1)
        self.assertEqual(
            self.client.get("/api/state", params=self._params()).json()[
                "history_total"
            ],
            0,
        )

    def test_remove_history_items_batch(self) -> None:
        (self.target / "c").touch()
        for item in ("a", "b", "c", "a"):
            log_selection(item, self.log)
        response = self.client.post(
            "/api/history/remove",
            json={"path": str(self.target), "items": ["a", "c"]},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["items"], ["a", "c"])
        self.assertEqual(body["removed"], 3)
        state = self.client.get("/api/state", params=self._params()).json()
        self.assertEqual([entry["item"] for entry in state["history"]], ["b"])
        self.assertIn("a", state["remaining"])
        self.assertIn("c", state["remaining"])
        self.assertNotIn("b", state["remaining"])

    def test_remove_history_items_unknown_is_noop(self) -> None:
        log_selection("a", self.log)
        before = self.log.read_bytes()
        body = self.client.post(
            "/api/history/remove",
            json={"path": str(self.target), "items": ["missing"]},
        ).json()
        self.assertEqual(body["removed"], 0)
        self.assertEqual(self.log.read_bytes(), before)

    def test_remove_history_items_without_log(self) -> None:
        body = self.client.post(
            "/api/history/remove",
            json={"path": str(self.target), "items": ["a"]},
        ).json()
        self.assertEqual(body["removed"], 0)
        self.assertFalse(self.log.exists())

    def test_remove_history_items_requires_selection(self) -> None:
        response = self.client.post(
            "/api/history/remove",
            json={"path": str(self.target), "items": []},
        )
        self.assertEqual(response.status_code, 422)

    def test_open_launches_entry(self) -> None:
        with patch("choosier.launcher.launch_path") as launcher:
            response = self.client.post(
                "/api/open", json={"path": str(self.target / "a")}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["opened"], "a")
        launcher.assert_called_once()

    def test_open_missing_entry_is_404(self) -> None:
        response = self.client.post(
            "/api/open", json={"path": str(self.target / "gone")}
        )
        self.assertEqual(response.status_code, 404)


class FilteredWebApiTest(unittest.TestCase):
    """Route-level coverage for the additive filtered state and pick fields."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        for name in ("a.txt", "b.TXT", "README", "notes.md"):
            (self.target / name).touch()
        (self.target / "sub").mkdir()
        self.log = self.target / ".choosier.jsonl"
        self.client = TestClient(create_app())

    def _post_state(self, **body: object) -> dict[str, Any]:
        payload: dict[str, object] = {"path": str(self.target)}
        payload.update(body)
        response = self.client.post("/api/state", json=payload)
        self.assertEqual(response.status_code, 200)
        return cast(dict[str, Any], response.json())

    def test_post_state_returns_filter_options(self) -> None:
        body = self._post_state()
        options = body["filter_options"]
        self.assertEqual(
            [(item["key"], item["count"]) for item in options["types"]],
            [
                ("dir", 1),
                ("file:.md", 1),
                ("file:.txt", 2),
                ("file:", 1),
            ],
        )
        self.assertEqual(
            [item["name"] for item in options["entries"]],
            ["README", "a.txt", "b.TXT", "notes.md", "sub"],
        )
        self.assertEqual(options["entries_total"], 5)
        self.assertFalse(options["entries_truncated"])
        self.assertEqual(body["known_entry_exclusions"], [])

    def test_post_state_applies_type_and_entry_exclusions(self) -> None:
        body = self._post_state(
            excluded_types=["dir"],
            excluded_entries=["notes.md", "stale.txt", "notes.md"],
        )
        self.assertEqual(body["remaining"], ["README", "a.txt", "b.TXT"])
        self.assertEqual(body["remaining_total"], 3)
        self.assertEqual(body["known_entry_exclusions"], ["notes.md"])

    def test_post_state_canonicalizes_type_case(self) -> None:
        body = self._post_state(excluded_types=["file:.TXT"])
        self.assertEqual(body["remaining"], ["README", "notes.md", "sub"])
        counts = {
            item["key"]: item["count"] for item in body["filter_options"]["types"]
        }
        self.assertEqual(counts["file:.txt"], 2)

    def test_post_state_invalid_path_has_empty_options(self) -> None:
        response = self.client.post(
            "/api/state",
            json={
                "path": str(self.target / "nope"),
                "excluded_entries": ["a.txt"],
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["valid_path"])
        self.assertEqual(body["remaining"], [])
        self.assertEqual(body["filter_options"]["types"], [])
        self.assertEqual(body["filter_options"]["entries"], [])
        self.assertEqual(body["filter_options"]["entries_total"], 0)
        self.assertFalse(body["filter_options"]["entries_truncated"])
        self.assertEqual(body["known_entry_exclusions"], [])

    def test_post_state_stale_exclusions_match_nothing(self) -> None:
        body = self._post_state(
            excluded_types=["file:.png"],
            excluded_entries=["missing.bin"],
        )
        self.assertEqual(
            body["remaining"],
            ["README", "a.txt", "b.TXT", "notes.md", "sub"],
        )
        self.assertEqual(body["known_entry_exclusions"], [])

    def test_post_state_conflicting_options_is_400(self) -> None:
        response = self.client.post(
            "/api/state",
            json={
                "path": str(self.target),
                "files_only": True,
                "dirs_only": True,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["message"],
            "files_only and dirs_only are mutually exclusive",
        )

    def test_get_state_shape_is_unchanged(self) -> None:
        response = self.client.get("/api/state", params={"path": str(self.target)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()),
            {
                "valid_path",
                "path",
                "log_file",
                "remaining",
                "remaining_total",
                "history",
                "history_total",
            },
        )

    def test_pick_honors_exclusions_without_writing_on_failure(self) -> None:
        filtered_empty = self.client.post(
            "/api/pick",
            json={
                "path": str(self.target),
                "excluded_types": ["dir", "file:.md", "file:.txt", "file:"],
            },
        ).json()
        self.assertEqual(filtered_empty["status"], "filtered_empty")
        self.assertIsNone(filtered_empty["item"])
        self.assertFalse(filtered_empty["logged"])
        self.assertFalse(self.log.exists())

        only_txt = {
            "path": str(self.target),
            "excluded_types": ["dir", "file:.md", "file:"],
        }
        first = self.client.post("/api/pick", json=only_txt).json()
        second = self.client.post("/api/pick", json=only_txt).json()
        self.assertEqual(first["status"], "picked")
        self.assertEqual(second["status"], "picked")
        self.assertEqual({first["item"], second["item"]}, {"a.txt", "b.TXT"})
        third = self.client.post("/api/pick", json=only_txt).json()
        self.assertEqual(third["status"], "filtered_exhausted")
        self.assertIsNone(third["item"])
        self.assertFalse(third["logged"])
        self.assertEqual(self.log.read_text(encoding="utf-8").count("\n"), 2)

    def test_pick_exclusion_intersection(self) -> None:
        body = self.client.post(
            "/api/pick",
            json={
                "path": str(self.target),
                "seed": 1,
                "dry_run": True,
                "excluded_types": ["dir", "file:.md", "file:"],
                "excluded_entries": ["b.TXT"],
            },
        ).json()
        self.assertEqual(body["status"], "picked")
        self.assertEqual(body["item"], "a.txt")
        self.assertFalse(body["logged"])
        self.assertFalse(self.log.exists())


@unittest.skipUnless(HAS_WEB, "web extra (fastapi) not installed")
class WebPathMemoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self._folder("target", "a.txt", "b.jpg")
        self.memory = PathMemory()

    def _folder(self, name: str, *files: str) -> Path:
        folder = self.root / name
        folder.mkdir()
        for file_name in files:
            (folder / file_name).touch()
        return folder

    def test_defaults_restore_the_most_recent_folder(self) -> None:
        self.memory.record(self.target)
        body = TestClient(create_app()).get("/api/defaults").json()
        self.assertEqual(body["path"], str(self.target.resolve()))
        self.assertIsNone(body["path_warning"])

    def test_defaults_fall_back_to_cwd_without_memory(self) -> None:
        body = TestClient(create_app()).get("/api/defaults").json()
        self.assertEqual(body["path"], str(Path.cwd()))
        self.assertIsNone(body["path_warning"])

    def test_explicit_path_wins_even_when_invalid(self) -> None:
        self.memory.record(self.target)
        missing = str(self.root / "missing")
        body = TestClient(create_app(missing)).get("/api/defaults").json()
        self.assertEqual(body["path"], missing)
        self.assertIsNone(body["path_warning"])

    def test_defaults_report_pruning_and_corruption(self) -> None:
        stale = self._folder("stale")
        self.memory.record(self.target)
        self.memory.record(stale)
        stale.rmdir()
        body = TestClient(create_app()).get("/api/defaults").json()
        self.assertEqual(body["path"], str(self.target.resolve()))
        self.assertIn("unavailable", body["path_warning"])
        self.assertNotIn(str(stale.resolve()), self.memory.snapshot().recent)

        self.memory.file.write_text("{broken", encoding="utf-8")
        body = TestClient(create_app()).get("/api/defaults").json()
        self.assertEqual(body["path"], str(Path.cwd()))
        self.assertEqual(body["path_warning"], READ_WARNING)

    def test_paths_reports_newest_first_and_moves_reuse_to_the_top(self) -> None:
        first = self._folder("first")
        second = self._folder("second")
        self.memory.record(first)
        self.memory.record(second)

        body = TestClient(create_app()).get("/api/paths").json()
        self.assertEqual(
            body,
            {
                "recent": [str(second.resolve()), str(first.resolve())],
                "warning": None,
            },
        )

        self.memory.record(first)
        body = TestClient(create_app()).get("/api/paths").json()
        self.assertEqual(
            body["recent"],
            [str(first.resolve()), str(second.resolve())],
        )

    def test_paths_caps_the_list_at_ten(self) -> None:
        folders = [self._folder(f"recent{index:02d}") for index in range(12)]
        for folder in folders:
            self.memory.record(folder)

        body = TestClient(create_app()).get("/api/paths").json()

        self.assertEqual(
            body["recent"],
            [str(folder.resolve()) for folder in reversed(folders)][:10],
        )

    def test_paths_prunes_stale_entries_and_reports_a_warning(self) -> None:
        stale = self._folder("stale")
        self.memory.record(self.target)
        self.memory.record(stale)
        client = TestClient(create_app())
        stale.rmdir()

        body = client.get("/api/paths").json()

        self.assertEqual(body["recent"], [str(self.target.resolve())])
        self.assertIn("unavailable", body["warning"])
        self.assertEqual(
            self.memory.snapshot().recent,
            (str(self.target.resolve()),),
        )

    def test_paths_is_empty_without_a_record(self) -> None:
        body = TestClient(create_app()).get("/api/paths").json()

        self.assertEqual(body, {"recent": [], "warning": None})
        self.assertFalse(self.memory.file.exists())

    def test_paths_warns_on_a_corrupt_record(self) -> None:
        self.memory.file.parent.mkdir(parents=True, exist_ok=True)
        self.memory.file.write_text("{broken", encoding="utf-8")

        body = TestClient(create_app()).get("/api/paths").json()

        self.assertEqual(body["recent"], [])
        self.assertEqual(body["warning"], READ_WARNING)

    def test_paths_rejects_other_methods(self) -> None:
        response = TestClient(create_app()).post("/api/paths")

        self.assertEqual(response.status_code, 405)
        body = response.json()
        self.assertEqual(body["error"]["code"], "method_not_allowed")
        self.assertEqual(body["detail"], body["error"]["message"])

    def test_pick_records_the_target_and_dry_run_records_too(self) -> None:
        client = TestClient(create_app(str(self.target)))
        body = client.post(
            "/api/pick", json={"path": str(self.target), "seed": 1}
        ).json()
        self.assertEqual(body["status"], "picked")
        self.assertIsNone(body["path_memory_notice"])
        self.assertEqual(
            self.memory.snapshot().recent,
            (str(self.target.resolve()),),
        )

        other = self._folder("other", "c.txt")
        body = client.post(
            "/api/pick",
            json={"path": str(other), "seed": 1, "dry_run": True},
        ).json()
        self.assertEqual(body["status"], "picked")
        self.assertIsNone(body["path_memory_notice"])
        self.assertEqual(self.memory.snapshot().recent[0], str(other.resolve()))

    def test_non_picked_outcomes_do_not_record(self) -> None:
        empty = self._folder("empty")
        client = TestClient(create_app(str(self.target)))
        self.assertEqual(
            client.post("/api/pick", json={"path": str(empty), "seed": 1}).json()[
                "status"
            ],
            "empty",
        )
        self.assertEqual(
            client.post("/api/pick", json={"path": str(self.root / "missing")}).json()[
                "status"
            ],
            "invalid_path",
        )
        self.assertEqual(self.memory.snapshot().recent, ())

    def test_memory_failure_is_a_notice_not_a_pick_failure(self) -> None:
        self.memory.file.mkdir(parents=True)
        client = TestClient(create_app(str(self.target)))
        body = client.post(
            "/api/pick", json={"path": str(self.target), "seed": 1}
        ).json()
        self.assertEqual(body["status"], "picked")
        self.assertEqual(body["path_memory_notice"], RECORD_WARNING)
        self.assertTrue((self.target / ".choosier.jsonl").exists())

    def test_recording_preserves_history_filters_and_preview(self) -> None:
        log = self.target / ".choosier.jsonl"
        log_selection("a.txt", log)
        before = log.read_bytes()
        client = TestClient(create_app(str(self.target)))
        body = client.post(
            "/api/pick",
            json={
                "path": str(self.target),
                "seed": 1,
                "dry_run": True,
                "excluded_types": ["file:.txt"],
            },
        ).json()
        self.assertEqual(body["status"], "picked")
        self.assertEqual(body["item"], "b.jpg")
        self.assertIsNotNone(body["preview"])
        self.assertIsNone(body["path_memory_notice"])
        self.assertEqual(log.read_bytes(), before)
        self.assertEqual(
            self.memory.snapshot().recent,
            (str(self.target.resolve()),),
        )
        state = client.post(
            "/api/state",
            json={
                "path": str(self.target),
                "excluded_types": ["file:.txt"],
            },
        ).json()
        self.assertIn("b.jpg", state["remaining"])
        self.assertNotIn("a.txt", state["remaining"])


@unittest.skipUnless(HAS_WEB, "web extra (fastapi) not installed")
@unittest.skipUnless(STATIC_DIR.is_dir(), "frontend not built")
class StaticServingTest(unittest.TestCase):
    def test_index_is_served(self) -> None:
        response = TestClient(create_app()).get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("choosier", response.text)


if __name__ == "__main__":
    unittest.main()
