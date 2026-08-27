"""Architecture guard — application code must not bypass persist_service."""

from __future__ import annotations

import ast
from pathlib import Path

import pricebrain_app

_FORBIDDEN_WRITE_SYMBOLS = frozenset(
    {
        "write_validated_product",
        "_write_validated_product",
        "save_validated_product",
    }
)

_APP_ROOT = Path(pricebrain_app.__file__).resolve().parent
_SKIP_DIR_NAMES = frozenset({"tests", "repository", "__pycache__"})


def application_python_files() -> list[Path]:
    files: list[Path] = []
    for path in _APP_ROOT.rglob("*.py"):
        if any(part in _SKIP_DIR_NAMES for part in path.relative_to(_APP_ROOT).parts):
            continue
        files.append(path)
    return files


def forbidden_persist_bypass_violations(source: str, *, origin: str) -> list[str]:
    tree = ast.parse(source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            if module in {
                "pricebrain_app.repository",
                "pricebrain_app.repository.service",
                "pricebrain_app.repository._testing.persist_helpers",
            }:
                for name in names:
                    if name in _FORBIDDEN_WRITE_SYMBOLS:
                        violations.append(f"{origin}: import {module}.{name}")
            if module == "pricebrain_app.repository.product_repository":
                if "ProductRepository" in names:
                    # allowed only if no upsert_from_validated call — checked below
                    pass
        if isinstance(node, ast.Attribute) and node.attr == "upsert_from_validated":
            violations.append(f"{origin}: ProductRepository.upsert_from_validated")
        if isinstance(node, ast.Attribute) and node.attr == "_write_validated_product":
            violations.append(f"{origin}: _write_validated_product attribute")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "getattr" and len(node.args) >= 2:
                attr = node.args[1]
                if isinstance(attr, ast.Constant) and attr.value in {
                    "upsert_from_validated",
                    "_write_validated_product",
                    "save_validated_product",
                }:
                    violations.append(f"{origin}: getattr({attr.value})")
            imported = None
            if isinstance(func, ast.Attribute) and func.attr == "import_module":
                imported = node.args[0] if node.args else None
            if isinstance(imported, ast.Constant) and isinstance(imported.value, str):
                if imported.value in {
                    "pricebrain_app.repository.service",
                    "pricebrain_app.repository._testing.persist_helpers",
                }:
                    violations.append(f"{origin}: importlib.import_module({imported.value})")
    return violations


def scan_application_persist_bypasses() -> list[str]:
    violations: list[str] = []
    for path in application_python_files():
        origin = str(path.relative_to(_APP_ROOT.parent))
        violations.extend(
            forbidden_persist_bypass_violations(
                path.read_text(encoding="utf-8"),
                origin=origin,
            )
        )
    return violations


def package_exports_save_validated_product(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "pricebrain_app.repository.service":
                if any(alias.name == "save_validated_product" for alias in node.names):
                    return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and elt.value == "save_validated_product":
                                return True
    return False


def test_architecture_application_modules_do_not_bypass_persist() -> None:
    assert scan_application_persist_bypasses() == []


def test_architecture_repository_package_does_not_export_save_validated_product() -> None:
    init_source = Path(pricebrain_app.__file__).resolve().parent.joinpath(
        "repository", "__init__.py"
    ).read_text(encoding="utf-8")
    assert package_exports_save_validated_product(init_source) is False


def test_architecture_guard_detects_forbidden_import_pattern() -> None:
    sample = """
from pricebrain_app.repository.service import _write_validated_product
"""
    violations = forbidden_persist_bypass_violations(sample, origin="sample")
    assert any("_write_validated_product" in item for item in violations)


def test_phase16_m28_public_export_detected() -> None:
    restored = '''
from pricebrain_app.repository.service import save_validated_product
__all__ = ["save_validated_product"]
'''
    assert package_exports_save_validated_product(restored) is True


def test_phase16_m29_direct_product_upsert_detected() -> None:
    sample = """
from pricebrain_app.repository.product_repository import ProductRepository
ProductRepository(db).upsert_from_validated(data)
"""
    violations = forbidden_persist_bypass_violations(sample, origin="app")
    assert any("upsert_from_validated" in item for item in violations)


def test_phase16_m30_write_validated_product_import_detected() -> None:
    sample = "from pricebrain_app.repository.service import _write_validated_product\n"
    violations = forbidden_persist_bypass_violations(sample, origin="app")
    assert any("_write_validated_product" in item for item in violations)


def test_phase18_m36_direct_upsert_detected() -> None:
    sample = """
from pricebrain_app.repository.product_repository import ProductRepository
ProductRepository(db).upsert_from_validated(data)
"""
    violations = forbidden_persist_bypass_violations(sample, origin="app")
    assert any("upsert_from_validated" in item for item in violations)


def test_phase18_m37_write_helper_import_detected() -> None:
    sample = "from pricebrain_app.repository.service import _write_validated_product\n"
    violations = forbidden_persist_bypass_violations(sample, origin="app")
    assert any("_write_validated_product" in item for item in violations)


def test_phase18_m38_save_validated_product_not_defined_on_service() -> None:
    service_source = Path(pricebrain_app.__file__).resolve().parent.joinpath(
        "repository", "service.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(service_source)
    defined = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "save_validated_product"
    ]
    assert defined == []


def test_phase18_getattr_upsert_detected() -> None:
    sample = 'getattr(repo, "upsert_from_validated")(data)\n'
    violations = forbidden_persist_bypass_violations(sample, origin="app")
    assert any("getattr" in item for item in violations)


def test_phase18_ast_guard_does_not_claim_dynamic_import_coverage() -> None:
    """Computed module names are outside static AST guard scope."""
    sample = """
import importlib
name = "pricebrain_app.repository.service"
importlib.import_module(name)
"""
    violations = forbidden_persist_bypass_violations(sample, origin="app")
    assert violations == []
