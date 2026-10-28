"""Executable route, schema, and binary tests for the choosier API contract."""

import tempfile
import unittest
from io import BytesIO
from pathlib import Path

try:
    from fastapi.testclient import TestClient

    from choosier.web import ERROR_STATUS, create_app

    HAS_WEB = True
except ImportError:
    HAS_WEB = False

from tests.api_contract_support import (
    api_routes,
    assert_error_taxonomy,
    assert_route_parity,
    assert_success_schema,
    contract_route,
    load_contract,
)


def _real_png(size: tuple[int, int] = (32, 24)) -> bytes:
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", size, (10, 80, 160)).save(buffer, "PNG")
    return buffer.getvalue()


MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"


@unittest.skipUnless(HAS_WEB, "web extra (fastapi) not installed")
class ApiContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()
        self.app = create_app()
        self.openapi = self.app.openapi()

    def test_route_inventory_matches_contract(self) -> None:
        live = api_routes(self.app)
        assert_route_parity(self.contract, live)
        self.assertEqual(len(live), len(self.contract["routes"]))

    def test_error_taxonomy_matches_contract(self) -> None:
        assert_error_taxonomy(self.contract, ERROR_STATUS)

    def test_json_success_schemas_match_openapi(self) -> None:
        json_routes = [
            route
            for route in self.contract["routes"]
            if route["success"]["body"] == "json"
        ]
        self.assertTrue(json_routes)
        for route in json_routes:
            with self.subTest(route=f"{route['method']} {route['path']}"):
                assert_success_schema(self.contract, route, self.openapi)

    def test_binary_routes_declare_contract_rules(self) -> None:
        binary_routes = [
            route
            for route in self.contract["routes"]
            if route["success"]["body"] == "binary"
        ]
        self.assertEqual(
            {(route["method"], route["path"]) for route in binary_routes},
            {("GET", "/api/image"), ("GET", "/api/video")},
        )
        for route in binary_routes:
            with self.subTest(route=f"{route['method']} {route['path']}"):
                success = route["success"]
                statuses = success["statuses"]
                self.assertTrue(statuses)
                self.assertTrue(all(isinstance(status, int) for status in statuses))
                content_type = success["contentType"]
                if isinstance(content_type, str):
                    content_types = [content_type]
                else:
                    content_types = list(content_type)
                self.assertTrue(content_types)
                for declared in content_types:
                    self.assertIsInstance(declared, str)
                    self.assertIn("/", declared)
                headers = success.get("headers", {})
                self.assertEqual(headers.get("Cache-Control"), "no-store")
                self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")

        image = contract_route(self.contract, "GET", "/api/image")
        self.assertEqual(image["success"]["statuses"], [200])
        self.assertEqual(image["success"]["contentType"], "image/*")

        video = contract_route(self.contract, "GET", "/api/video")
        self.assertEqual(video["success"]["statuses"], [200, 206])
        self.assertEqual(
            video["success"]["contentType"],
            ["video/*", "multipart/byteranges"],
        )
        self.assertEqual(video["success"]["headers"]["Accept-Ranges"], "bytes")

    def test_binary_routes_serve_declared_content_types(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        client = TestClient(self.app)

        image = root / "photo.png"
        image.write_bytes(_real_png())
        image_response = client.get("/api/image", params={"path": str(image)})
        self.assertEqual(image_response.status_code, 200)
        self.assertTrue(image_response.headers["content-type"].startswith("image/"))
        self.assertEqual(image_response.content, image.read_bytes())

        video = root / "clip.mp4"
        video.write_bytes(MP4)
        full = client.get("/api/video", params={"path": str(video)})
        self.assertEqual(full.status_code, 200)
        self.assertTrue(full.headers["content-type"].startswith("video/"))
        self.assertEqual(full.headers["accept-ranges"], "bytes")

        partial = client.get(
            "/api/video",
            params={"path": str(video)},
            headers={"Range": "bytes=0-3"},
        )
        self.assertEqual(partial.status_code, 206)
        self.assertEqual(partial.content, MP4[:4])

        multipart = client.get(
            "/api/video",
            params={"path": str(video)},
            headers={"Range": "bytes=0-1,3-4"},
        )
        self.assertEqual(multipart.status_code, 206)
        self.assertTrue(
            multipart.headers["content-type"].startswith("multipart/byteranges")
        )


if __name__ == "__main__":
    unittest.main()
