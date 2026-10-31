"""Cross-interface history consistency: CLI, web, and the shared service."""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from choosier.cli import main
from choosier.services import HistoryService, build_state, pick

try:
    from fastapi.testclient import TestClient

    from choosier.web import create_app

    HAS_WEB = True
except ImportError:
    HAS_WEB = False

FIXED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
MIXED = (
    '{"ts": "2026-01-01T00:00:00+00:00", "item": "alpha"}\n'
    "2020-01-01T00:00:00Z - legacy - beta\n"
    "plain-gamma\n"
    "\n"
    "[1, 2]\n"
    '{"ts": "2026-01-02T00:00:00+00:00", "item": "alpha"}\n'
)
EXPECTED_REMAINING = ["beta", "delta", "gamma"]
EXPECTED_ENTRIES = (
    ("2026-01-01T00:00:00+00:00", "alpha", "2026-01-01T00:00:00+00:00  alpha"),
    (None, "legacy - beta", "2020-01-01T00:00:00Z - legacy - beta"),
    (None, "plain-gamma", "plain-gamma"),
    ("2026-01-02T00:00:00+00:00", "alpha", "2026-01-02T00:00:00+00:00  alpha"),
)
AFTER_ALPHA_REMOVAL = "2020-01-01T00:00:00Z - legacy - beta\nplain-gamma\n\n[1, 2]\n"


@unittest.skipUnless(HAS_WEB, "web extra (fastapi) not installed")
class HistoryConsistencyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / "target"
        self.target.mkdir()
        for name in ("alpha", "beta", "gamma", "delta"):
            (self.target / name).touch()
        self.logs: dict[str, Path] = {}
        for interface in ("cli", "web", "service"):
            directory = self.root / interface
            directory.mkdir()
            log = directory / "history.jsonl"
            log.write_text(MIXED, encoding="utf-8")
            self.logs[interface] = log
        self.client = TestClient(create_app())

    def _run_cli(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(list(argv))
        return code, buffer.getvalue()

    def _cli_list(self, log: Path) -> list[str]:
        code, output = self._run_cli(str(self.target), "--list", "--log-file", str(log))
        self.assertEqual(code, 0)
        return output.splitlines()

    def _web_state(self, log: Path) -> dict[str, Any]:
        response = self.client.get(
            "/api/state",
            params={"path": str(self.target), "log_file": str(log)},
        )
        self.assertEqual(response.status_code, 200)
        body: dict[str, Any] = response.json()
        return body

    def _service_entries(self, log: Path) -> tuple[tuple[str | None, str, str], ...]:
        snapshot = HistoryService(log).snapshot()
        return tuple(
            (entry.timestamp, entry.item, entry.display) for entry in snapshot.entries
        )

    def test_reads_agree_across_cli_web_and_service(self) -> None:
        cli_remaining = self._cli_list(self.logs["cli"])
        web_state = self._web_state(self.logs["web"])
        service_state = build_state(self.target, self.logs["service"], max_lines=None)
        service_entries = self._service_entries(self.logs["service"])
        self.assertEqual(cli_remaining, EXPECTED_REMAINING)
        self.assertEqual(web_state["remaining"], EXPECTED_REMAINING)
        self.assertEqual(list(service_state.remaining), EXPECTED_REMAINING)
        self.assertEqual(web_state["remaining_total"], len(EXPECTED_REMAINING))
        self.assertEqual(service_state.remaining_total, len(EXPECTED_REMAINING))
        self.assertEqual(web_state["history_total"], len(EXPECTED_ENTRIES))
        self.assertEqual(service_state.history_total, len(EXPECTED_ENTRIES))
        self.assertEqual(service_entries, EXPECTED_ENTRIES)
        web_entries = tuple(
            (entry["timestamp"], entry["item"], entry["display"])
            for entry in web_state["history"]
        )
        self.assertEqual(web_entries, service_entries)
        self.assertEqual(len(service_state.history), len(EXPECTED_ENTRIES))

    def test_pick_appends_identically_across_all_interfaces(self) -> None:
        with patch("choosier.storage.datetime") as mock_datetime:
            mock_datetime.now.return_value = FIXED
            cli_code, cli_output = self._run_cli(
                str(self.target),
                "--log-file",
                str(self.logs["cli"]),
                "--seed",
                "1",
            )
            web_response = self.client.post(
                "/api/pick",
                json={
                    "path": str(self.target),
                    "log_file": str(self.logs["web"]),
                    "seed": 1,
                },
            )
            service_outcome = pick(self.target, self.logs["service"], seed=1)
        self.assertEqual(cli_code, 0)
        web_body = web_response.json()
        self.assertEqual(web_response.status_code, 200)
        self.assertEqual(web_body["status"], "picked")
        self.assertTrue(web_body["logged"])
        self.assertEqual(service_outcome.status, "picked")
        self.assertTrue(service_outcome.logged)
        cli_item = next(
            line.removeprefix("The choice: ")
            for line in cli_output.splitlines()
            if line.startswith("The choice: ")
        )
        self.assertEqual(cli_item, web_body["item"])
        self.assertEqual(web_body["item"], service_outcome.item)
        cli_content = self.logs["cli"].read_text(encoding="utf-8")
        web_content = self.logs["web"].read_text(encoding="utf-8")
        service_content = self.logs["service"].read_text(encoding="utf-8")
        self.assertEqual(cli_content, web_content)
        self.assertEqual(web_content, service_content)
        self.assertTrue(cli_content.startswith(MIXED))
        appended = cli_content[len(MIXED) :].splitlines()
        self.assertEqual(len(appended), 1)
        self.assertEqual(
            json.loads(appended[0]),
            {"ts": FIXED.isoformat(), "item": cli_item},
        )

        cli_remaining = self._cli_list(self.logs["cli"])
        web_state = self._web_state(self.logs["web"])
        service_state = build_state(self.target, self.logs["service"], max_lines=None)
        service_entries = self._service_entries(self.logs["service"])
        self.assertEqual(cli_remaining, web_state["remaining"])
        self.assertEqual(web_state["remaining"], list(service_state.remaining))
        self.assertEqual(web_state["history_total"], len(EXPECTED_ENTRIES) + 1)
        self.assertEqual(service_state.history_total, len(EXPECTED_ENTRIES) + 1)
        self.assertEqual(
            tuple(
                (entry["timestamp"], entry["item"], entry["display"])
                for entry in web_state["history"]
            ),
            service_entries,
        )

    def test_batch_removal_agrees_and_never_exposes_a_partial_write(self) -> None:
        initial = self.logs["web"].read_bytes()
        self.assertEqual(self.logs["service"].read_bytes(), initial)
        observed: list[bytes] = []
        real_replace = os.replace

        def observe(src: str, dst: str) -> None:
            observed.append(Path(dst).read_bytes())
            real_replace(src, dst)

        with patch("choosier.storage.os.replace", side_effect=observe):
            web_response = self.client.post(
                "/api/history/remove",
                json={
                    "path": str(self.target),
                    "log_file": str(self.logs["web"]),
                    "items": ["alpha"],
                },
            )
            service_removed = HistoryService(self.logs["service"]).remove_many(
                ["alpha"]
            )
        self.assertEqual(web_response.status_code, 200)
        self.assertEqual(web_response.json()["removed"], 2)
        self.assertEqual(service_removed, 2)
        final = AFTER_ALPHA_REMOVAL.encode()
        self.assertEqual(self.logs["web"].read_bytes(), final)
        self.assertEqual(self.logs["service"].read_bytes(), final)
        self.assertTrue(observed)
        for seen in observed:
            self.assertIn(seen, (initial, final))
        self.assertEqual(list((self.root / "web").glob(".*.tmp")), [])
        self.assertEqual(list((self.root / "service").glob(".*.tmp")), [])
        self.assertEqual(
            self._service_entries(self.logs["web"]),
            (
                (
                    None,
                    "legacy - beta",
                    "2020-01-01T00:00:00Z - legacy - beta",
                ),
                (None, "plain-gamma", "plain-gamma"),
            ),
        )

    def test_archive_agrees_between_web_and_service(self) -> None:
        with patch("choosier.storage.datetime") as mock_datetime:
            mock_datetime.now.return_value = FIXED
            web_response = self.client.post(
                "/api/history/archive",
                params={
                    "path": str(self.target),
                    "log_file": str(self.logs["web"]),
                },
            )
            service_backup = HistoryService(self.logs["service"]).archive()
        self.assertEqual(web_response.status_code, 200)
        web_name = web_response.json()["backup"]
        self.assertEqual(web_name, "history-20260102T030405Z.jsonl.old")
        assert service_backup is not None
        self.assertEqual(web_name, service_backup.name)
        self.assertFalse(self.logs["web"].exists())
        self.assertFalse(self.logs["service"].exists())
        self.assertEqual(
            (self.root / "web" / web_name).read_text(encoding="utf-8"), MIXED
        )
        self.assertEqual(service_backup.read_text(encoding="utf-8"), MIXED)

        with patch("choosier.storage.datetime") as mock_datetime:
            mock_datetime.now.return_value = FIXED
            web_again = self.client.post(
                "/api/history/archive",
                params={
                    "path": str(self.target),
                    "log_file": str(self.logs["web"]),
                },
            )
            service_again = HistoryService(self.logs["service"]).archive()
        self.assertIsNone(web_again.json()["backup"])
        self.assertIsNone(service_again)

    def test_clear_agrees_across_cli_web_and_service(self) -> None:
        cli_code, cli_output = self._run_cli(
            str(self.target), "--log-file", str(self.logs["cli"]), "--reset"
        )
        self.assertEqual(cli_code, 0)
        self.assertIn("Removed", cli_output)
        self.assertFalse(self.logs["cli"].exists())

        web_body = self.client.delete(
            "/api/history",
            params={"path": str(self.target), "log_file": str(self.logs["web"])},
        ).json()
        self.assertTrue(web_body["removed"])
        self.assertFalse(self.logs["web"].exists())

        service = HistoryService(self.logs["service"])
        self.assertTrue(service.clear())
        self.assertFalse(self.logs["service"].exists())

        cli_code, cli_output = self._run_cli(
            str(self.target), "--log-file", str(self.logs["cli"]), "--reset"
        )
        self.assertEqual(cli_code, 0)
        self.assertIn("No log", cli_output)
        again = self.client.delete(
            "/api/history",
            params={"path": str(self.target), "log_file": str(self.logs["web"])},
        ).json()
        self.assertFalse(again["removed"])
        self.assertFalse(service.clear())


if __name__ == "__main__":
    unittest.main()
