"""Shared helpers for the API contract and compatibility tests."""

import json
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import httpx
from fastapi import FastAPI
from fastapi.routing import APIRoute

from choosier.web import ERROR_STATUS, ErrorCode

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    REPO_ROOT
    / "specs"
    / "001-standardize-api-responses"
    / "contracts"
    / "api-contract.json"
)


def load_contract() -> dict[str, Any]:
    """Load the machine-readable route contract used by the tests."""
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise TypeError(f"{CONTRACT_PATH} must contain a JSON object")
    return cast(dict[str, Any], data)


def normalize_contract_schema(
    schema: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve `ref`/`nullable` into the small comparison schema."""
    nullable = bool(schema.get("nullable", False))
    ref = schema.get("ref")
    if ref is not None:
        schemas = contract["schemas"]
        resolved = normalize_contract_schema(schemas[ref], contract)
        return {
            **resolved,
            "nullable": bool(resolved.get("nullable", False)) or nullable,
        }
    schema_type = schema.get("type")
    if schema_type is None:
        raise AssertionError(f"Contract schema is missing type: {schema!r}")
    normalized: dict[str, Any] = {"type": schema_type, "nullable": nullable}
    if "enum" in schema:
        normalized["enum"] = list(schema["enum"])
    if "fields" in schema:
        normalized["fields"] = {
            name: normalize_contract_schema(field, contract)
            for name, field in schema["fields"].items()
        }
    if "items" in schema:
        normalized["items"] = normalize_contract_schema(schema["items"], contract)
    return normalized


def normalize_openapi_schema(
    schema: Mapping[str, Any],
    components: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize FastAPI's `$ref`/`anyOf` output to the comparison schema."""
    ref = schema.get("$ref")
    if ref is not None:
        name = str(ref).rsplit("/", 1)[-1]
        return normalize_openapi_schema(components[name], components)
    any_of = schema.get("anyOf")
    if any_of is not None:
        variants = [
            item
            for item in any_of
            if not (isinstance(item, Mapping) and item.get("type") == "null")
        ]
        if len(variants) != 1:
            raise AssertionError(f"Unsupported OpenAPI anyOf: {any_of!r}")
        resolved = normalize_openapi_schema(variants[0], components)
        if len(variants) != len(any_of):
            resolved = {**resolved, "nullable": True}
        return resolved
    schema_type = schema.get("type")
    if schema_type is None:
        raise AssertionError(f"OpenAPI schema is missing type: {schema!r}")
    normalized: dict[str, Any] = {
        "type": schema_type,
        "nullable": bool(schema.get("nullable", False)),
    }
    if "enum" in schema:
        normalized["enum"] = list(schema["enum"])
    properties = schema.get("properties")
    if properties is not None:
        normalized["fields"] = {
            name: normalize_openapi_schema(prop, components)
            for name, prop in properties.items()
        }
    items = schema.get("items")
    if items is not None:
        normalized["items"] = normalize_openapi_schema(items, components)
    return normalized


def normalize_contract_route_schema(
    route: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a route's contract success schema in normalized form."""
    return normalize_contract_schema(route["success"]["schema"], contract)


def assert_schema_matches(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    path: str = "response",
) -> None:
    """Fail on any field, type, nullability, or enum drift."""
    if expected["type"] != actual["type"]:
        raise AssertionError(f"{path}: type {actual['type']!r} != {expected['type']!r}")
    if bool(expected["nullable"]) != bool(actual.get("nullable", False)):
        raise AssertionError(
            f"{path}: nullable {actual.get('nullable', False)!r} "
            f"!= {expected['nullable']!r}"
        )
    expected_enum = expected.get("enum")
    actual_enum = actual.get("enum")
    if expected_enum is not None or actual_enum is not None:
        if expected_enum != actual_enum:
            raise AssertionError(f"{path}: enum {actual_enum!r} != {expected_enum!r}")
    if expected["type"] == "object":
        expected_fields = expected.get("fields")
        actual_fields = actual.get("fields")
        if not isinstance(expected_fields, Mapping) or not isinstance(
            actual_fields, Mapping
        ):
            raise AssertionError(f"{path}: object is missing fields")
        missing = sorted(set(expected_fields) - set(actual_fields))
        extra = sorted(set(actual_fields) - set(expected_fields))
        if missing or extra:
            raise AssertionError(
                f"{path}: field drift (missing={missing}, extra={extra})"
            )
        for name, field in expected_fields.items():
            assert_schema_matches(
                field,
                actual_fields[name],
                f"{path}.{name}",
            )
    elif expected["type"] == "array":
        expected_items = expected.get("items")
        actual_items = actual.get("items")
        if not isinstance(expected_items, Mapping) or not isinstance(
            actual_items, Mapping
        ):
            raise AssertionError(f"{path}: array is missing items")
        assert_schema_matches(expected_items, actual_items, f"{path}[]")


def _assert_value(
    testcase: unittest.TestCase,
    value: Any,
    schema: Mapping[str, Any],
    path: str,
) -> None:
    if value is None:
        testcase.assertTrue(
            bool(schema["nullable"]),
            f"{path}: null is not allowed",
        )
        return
    schema_type = schema["type"]
    if schema_type == "object":
        testcase.assertIsInstance(value, dict, f"{path}: expected object")
        fields = schema.get("fields")
        if not isinstance(fields, Mapping):
            raise AssertionError(f"{path}: object schema has no fields")
        testcase.assertEqual(
            set(value),
            set(fields),
            f"{path}: field set differs from the contract",
        )
        for name, field in fields.items():
            _assert_value(testcase, value[name], field, f"{path}.{name}")
    elif schema_type == "array":
        testcase.assertIsInstance(value, list, f"{path}: expected array")
        items = schema.get("items")
        if not isinstance(items, Mapping):
            raise AssertionError(f"{path}: array schema has no items")
        for index, item in enumerate(value):
            _assert_value(testcase, item, items, f"{path}[{index}]")
    elif schema_type == "string":
        testcase.assertIsInstance(value, str, f"{path}: expected string")
    elif schema_type == "boolean":
        testcase.assertIsInstance(value, bool, f"{path}: expected boolean")
    elif schema_type == "integer":
        testcase.assertIsInstance(value, int, f"{path}: expected integer")
        testcase.assertNotIsInstance(value, bool, f"{path}: expected integer")
    elif schema_type == "number":
        testcase.assertIsInstance(value, (int, float), f"{path}: expected number")
        testcase.assertNotIsInstance(value, bool, f"{path}: expected number")
    else:
        raise AssertionError(f"{path}: unsupported schema type {schema_type!r}")
    enum = schema.get("enum")
    if enum is not None:
        testcase.assertIn(value, enum, f"{path}: value is outside the enum")


def assert_value_matches_schema(
    testcase: unittest.TestCase,
    value: Any,
    schema: Mapping[str, Any],
    contract: Mapping[str, Any],
    path: str = "response",
) -> None:
    """Validate a live JSON value against the contract schema exactly."""
    normalized = normalize_contract_schema(schema, contract)
    _assert_value(testcase, value, normalized, path)


def contract_route(
    contract: Mapping[str, Any],
    method: str,
    path: str,
) -> dict[str, Any]:
    """Return the one documented route for a method/path pair."""
    for route in contract["routes"]:
        if route["method"] == method and route["path"] == path:
            return cast(dict[str, Any], route)
    raise AssertionError(f"Route is missing from the contract: {method} {path}")


def contract_route_pairs(contract: Mapping[str, Any]) -> set[tuple[str, str]]:
    """Return every documented (method, path) pair."""
    return {
        (str(route["method"]).upper(), str(route["path"]))
        for route in contract["routes"]
    }


def api_routes(app: FastAPI) -> set[tuple[str, str]]:
    """Collect every (method, path) pair the live app exposes under /api."""
    pairs: set[tuple[str, str]] = set()
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api"):
            for method in route.methods or set():
                pairs.add((method.upper(), route.path))
    return pairs


def assert_route_parity(
    contract: Mapping[str, Any],
    live: set[tuple[str, str]],
) -> None:
    """Require the contract and live route tables to match in both directions."""
    documented = contract_route_pairs(contract)
    if documented != live:
        missing = sorted(documented - live)
        extra = sorted(live - documented)
        raise AssertionError(
            f"Route drift (missing from app={missing}, undocumented={extra})"
        )


def assert_error_taxonomy(
    contract: Mapping[str, Any],
    error_status: Mapping[ErrorCode, int],
) -> None:
    """Require one documented status per code and a documented use for each."""
    documented = {
        str(code): int(info["status"]) for code, info in contract["errorCodes"].items()
    }
    if dict(error_status) != documented:
        raise AssertionError(
            f"Error vocabulary drift: {dict(error_status)!r} != {documented!r}"
        )
    referenced: set[str] = set()
    for route in contract["routes"]:
        codes = set()
        for error in route["errors"]:
            code = str(error["code"])
            status = int(error["status"])
            if code not in documented:
                raise AssertionError(f"Undocumented error code: {code}")
            if documented[code] != status:
                raise AssertionError(
                    f"{route['method']} {route['path']}: {code} uses status "
                    f"{status}, expected {documented[code]}"
                )
            codes.add(code)
            referenced.add(code)
        for required in ("method_not_allowed", "internal_error"):
            if required not in codes:
                raise AssertionError(
                    f"{route['method']} {route['path']} is missing {required}"
                )
    for error in contract["globalErrors"]:
        code = str(error["code"])
        if code not in documented:
            raise AssertionError(f"Undocumented global error code: {code}")
        if documented[code] != int(error["status"]):
            raise AssertionError(f"Global error {code} has a mismatched status")
        referenced.add(code)
    unused = documented.keys() - referenced
    if unused:
        raise AssertionError(f"Error codes are never referenced: {sorted(unused)}")


def openapi_success_schema(
    openapi: Mapping[str, Any],
    method: str,
    path: str,
) -> dict[str, Any]:
    """Extract and normalize a JSON success schema from FastAPI's OpenAPI."""
    operation = openapi["paths"][path][method.lower()]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    components = openapi["components"]["schemas"]
    return normalize_openapi_schema(schema, components)


def assert_success_schema(
    contract: Mapping[str, Any],
    route: Mapping[str, Any],
    openapi: Mapping[str, Any],
) -> None:
    """Compare one route's contract schema with FastAPI's OpenAPI schema."""
    expected = normalize_contract_route_schema(route, contract)
    actual = openapi_success_schema(
        openapi,
        str(route["method"]),
        str(route["path"]),
    )
    assert_schema_matches(
        expected,
        actual,
        f"{route['method']} {route['path']}",
    )


def assert_error_envelope(
    testcase: unittest.TestCase,
    response: httpx.Response,
    expected_status: int,
    expected_code: ErrorCode,
) -> dict[str, Any]:
    """Assert the exact documented error envelope for one response."""
    testcase.assertEqual(
        response.status_code,
        expected_status,
        f"unexpected status for {expected_code}: {response.text}",
    )
    content_type = response.headers.get("content-type", "").split(";", 1)[0]
    testcase.assertEqual(content_type.strip(), "application/json")
    body = response.json()
    testcase.assertIsInstance(body, dict)
    testcase.assertEqual(set(body), {"error", "detail"})
    error = body["error"]
    testcase.assertIsInstance(error, dict)
    testcase.assertEqual(set(error), {"code", "message", "details"})
    testcase.assertEqual(error["code"], expected_code)
    testcase.assertEqual(ERROR_STATUS[expected_code], expected_status)
    testcase.assertIsInstance(error["message"], str)
    testcase.assertTrue(error["message"])
    testcase.assertEqual(body["detail"], error["message"])
    if expected_code == "validation_error":
        details = error["details"]
        testcase.assertIsInstance(details, dict)
        testcase.assertEqual(set(details), {"issues"})
        issues = details["issues"]
        testcase.assertIsInstance(issues, list)
        testcase.assertTrue(issues)
        for issue in issues:
            testcase.assertIsInstance(issue, dict)
            testcase.assertEqual(set(issue), {"location", "message", "type"})
            testcase.assertIsInstance(issue["location"], list)
            testcase.assertTrue(issue["location"])
            testcase.assertTrue(
                all(isinstance(part, str) for part in issue["location"])
            )
            testcase.assertIsInstance(issue["message"], str)
            testcase.assertTrue(issue["message"])
            testcase.assertIsInstance(issue["type"], str)
            testcase.assertTrue(issue["type"])
    else:
        testcase.assertIsNone(error["details"])
    return cast(dict[str, Any], body)
