"""Source-boundary checks for the shared service layer."""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "choosier"
SERVICES = PACKAGE / "services"
MAIN = ROOT / "main.py"
WEB = PACKAGE / "web.py"
ADAPTERS = (WEB, PACKAGE / "cli.py", PACKAGE / "tui.py")

ALLOWED_CHOOSIER_SUBMODULES = {
    "chooser",
    "filters",
    "preview",
    "launcher",
    "storage",
    "services",
}
FORBIDDEN_CHOOSIER_SUBMODULES = {"web", "tui", "web_media", "cli"}
FORBIDDEN_TOP_LEVEL_MODULES = {
    "fastapi",
    "starlette",
    "uvicorn",
    "pydantic",
    "textual",
    "rich",
    "PIL",
}
FORBIDDEN_ADAPTER_REFERENCES = (
    "storage.log_selection",
    "storage.remove_log_item",
    "storage.remove_log_items",
    "storage.archive_log",
    "storage.reset_log",
    "read_log_entries",
    "parse_log_line",
)
ROUTE_DELEGATIONS = {
    "browse": ("services.browse_directory",),
    "state": ("services.build_state",),
    "state_filtered": ("services.build_state",),
    "pick": ("services.pick",),
    "preview": ("preview_entry",),
    "image": ("web_media.read_image", "web_media.make_thumbnail"),
    "video": ("web_media.read_video",),
    "open_entry": ("services.open_entry",),
    "archive": ("services.HistoryService",),
    "clear": ("services.HistoryService",),
    "remove_history_item": ("services.HistoryService",),
    "remove_history_items": ("services.HistoryService",),
}
SINGLE_DEFINITIONS = {
    "read_log_entries": PACKAGE / "storage.py",
    "parse_log_line": PACKAGE / "storage.py",
    "HistoryService": SERVICES / "history.py",
}


def _web_route_sources() -> dict[str, str]:
    """Map each nested route handler name to its source text."""
    source = WEB.read_text(encoding="utf-8")
    tree = ast.parse(source)
    create_app = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "create_app"
    )
    return {
        node.name: ast.get_source_segment(source, node) or ""
        for node in ast.walk(create_app)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _imported_modules(path: Path) -> set[str]:
    """Return every imported module name, including from-import symbols."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module is None:
                continue
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def _production_files() -> list[Path]:
    return sorted(PACKAGE.rglob("*.py")) + [MAIN]


class ServiceImportBoundaryTest(unittest.TestCase):
    def test_services_import_only_stdlib_and_core_modules(self) -> None:
        for path in sorted(SERVICES.glob("*.py")):
            for module in _imported_modules(path):
                with self.subTest(path=path.name, module=module):
                    if module == "choosier" or module.startswith("choosier."):
                        parts = module.split(".")
                        if len(parts) > 1:
                            self.assertIn(parts[1], ALLOWED_CHOOSIER_SUBMODULES)
                            self.assertNotIn(parts[1], FORBIDDEN_CHOOSIER_SUBMODULES)
                        continue
                    root = module.split(".")[0]
                    self.assertNotIn(root, FORBIDDEN_TOP_LEVEL_MODULES)
                    self.assertIn(root, sys.stdlib_module_names)

    def test_web_media_is_imported_only_by_web_adapter(self) -> None:
        importers = {
            path
            for path in _production_files()
            if any(
                module == "choosier.web_media"
                or module.startswith("choosier.web_media.")
                for module in _imported_modules(path)
            )
        }
        self.assertEqual(importers, {PACKAGE / "web.py"})


class SingleDefinitionTest(unittest.TestCase):
    def test_history_primitives_have_one_production_definition(self) -> None:
        found: dict[str, list[Path]] = {}
        for path in _production_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    if node.name in SINGLE_DEFINITIONS:
                        found.setdefault(node.name, []).append(path)
        for name, expected in SINGLE_DEFINITIONS.items():
            with self.subTest(name=name):
                self.assertEqual(found.get(name), [expected])


class WebRouteDelegationTest(unittest.TestCase):
    def test_business_routes_call_expected_services(self) -> None:
        sources = _web_route_sources()
        for route, expected in ROUTE_DELEGATIONS.items():
            with self.subTest(route=route):
                self.assertIn(route, sources)
                for token in expected:
                    self.assertIn(token, sources[route])

    def test_defaults_route_is_transport_only(self) -> None:
        source = _web_route_sources()["defaults"]
        self.assertNotIn("services.", source)
        self.assertNotIn("web_media.", source)
        self.assertIn("DefaultsResponse(", source)


class AdapterBypassTest(unittest.TestCase):
    def test_adapters_do_not_bypass_service_history_paths(self) -> None:
        for path in ADAPTERS:
            source = path.read_text(encoding="utf-8")
            for reference in FORBIDDEN_ADAPTER_REFERENCES:
                with self.subTest(path=path.name, reference=reference):
                    self.assertNotIn(reference, source)


if __name__ == "__main__":
    unittest.main()
