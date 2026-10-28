"""Executable route and taxonomy tests for the choosier API contract."""

import unittest

try:
    from choosier.web import ERROR_STATUS, create_app

    HAS_WEB = True
except ImportError:
    HAS_WEB = False

from tests.api_contract_support import (
    api_routes,
    assert_error_taxonomy,
    assert_route_parity,
    load_contract,
)


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


if __name__ == "__main__":
    unittest.main()
