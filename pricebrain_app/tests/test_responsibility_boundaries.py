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
