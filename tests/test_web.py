"""Tests for choosier.web: JSON API behavior (no browser testing)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient

    from choosier.web import STATIC_DIR, create_app

    HAS_WEB = True
except ImportError:
    HAS_WEB = False


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

    def test_defaults_echo_initial_values(self) -> None:
        client = TestClient(create_app("/somewhere", "/tmp/history.jsonl"))
        response = client.get("/api/defaults")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"path": "/somewhere", "log_file": "/tmp/history.jsonl"},
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

    def test_open_launches_entry(self) -> None:
        with patch("choosier.web.launch_path") as launcher:
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


@unittest.skipUnless(HAS_WEB, "web extra (fastapi) not installed")
@unittest.skipUnless(STATIC_DIR.is_dir(), "frontend not built")
class StaticServingTest(unittest.TestCase):
    def test_index_is_served(self) -> None:
        response = TestClient(create_app()).get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("choosier", response.text)


if __name__ == "__main__":
    unittest.main()
