"""Source-boundary checks for the shared service layer."""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "choosier"
SERVICES = PACKAGE / "services"
MAIN = ROOT / "main.py"

ALLOWED_CHOOSIER_SUBMODULES = {"chooser", "preview", "launcher", "storage", "services"}
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
SINGLE_DEFINITIONS = {
    "read_log_entries": PACKAGE / "storage.py",
    "parse_log_line": PACKAGE / "storage.py",
    "HistoryService": SERVICES / "history.py",
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


if __name__ == "__main__":
    unittest.main()
