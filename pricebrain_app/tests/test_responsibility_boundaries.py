import ast
from pathlib import Path


def _module_imports(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def test_crawler_does_not_import_repository_or_firebase() -> None:
    crawler_root = Path(__file__).resolve().parents[1] / "crawler"
    forbidden = {"repository", "firebase", "firebase_admin", "google", "pipeline"}
    for path in crawler_root.rglob("*.py"):
        imports = _module_imports(path)
        assert imports.isdisjoint(forbidden), f"{path} imports forbidden modules: {imports & forbidden}"


def test_pipeline_does_not_import_firebase() -> None:
    pipeline_root = Path(__file__).resolve().parents[1] / "pipeline"
    forbidden = {"firebase", "firebase_admin", "google", "repository"}
    for path in pipeline_root.rglob("*.py"):
        imports = _module_imports(path)
        assert imports.isdisjoint(forbidden), f"{path} imports forbidden modules: {imports & forbidden}"



def test_analysis_does_not_import_firebase_or_repository() -> None:
    """analysis/ is pure computation: no Firestore, no repository, no crawler/pipeline."""
    analysis_root = Path(__file__).resolve().parents[1] / "analysis"
    forbidden_roots = {"firebase", "firebase_admin", "google"}
    forbidden_app_layers = {"firebase", "repository", "crawler", "pipeline", "api"}
    for path in analysis_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            else:
                continue
            for module in modules:
                parts = module.split(".")
                assert parts[0] not in forbidden_roots, f"{path} imports {module}"
                if parts[0] == "pricebrain_app" and len(parts) > 1:
                    assert parts[1] not in forbidden_app_layers, f"{path} imports {module}"
