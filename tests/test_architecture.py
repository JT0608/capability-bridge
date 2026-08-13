import ast
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
CORE = PROJECT_ROOT / "src" / "capability_bridge" / "core"
PROVIDERS = PROJECT_ROOT / "src" / "capability_bridge" / "providers"

FORBIDDEN_ANYWHERE = {"mcp", "fastmcp", "anthropic", "openai"}


def _import_module_names(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _top_level(names: list[str]) -> set[str]:
    return {n.split(".")[0] for n in names}


def test_core_never_imports_mcp_clients_or_concrete_layers() -> None:
    for py in CORE.rglob("*.py"):
        names = _import_module_names(py)
        assert not (_top_level(names) & FORBIDDEN_ANYWHERE), (
            f"{py.relative_to(PROJECT_ROOT)} imports {_top_level(names) & FORBIDDEN_ANYWHERE}"
        )
        assert not any(
            n.startswith("capability_bridge.providers")
            or n.startswith("capability_bridge.transports")
            for n in names
        ), f"{py.relative_to(PROJECT_ROOT)} imports a concrete layer"


def test_providers_never_import_mcp_or_transports() -> None:
    for py in PROVIDERS.rglob("*.py"):
        names = _import_module_names(py)
        assert not (_top_level(names) & FORBIDDEN_ANYWHERE), (
            f"{py.relative_to(PROJECT_ROOT)} imports {_top_level(names) & FORBIDDEN_ANYWHERE}"
        )
        assert not any(n.startswith("capability_bridge.transports") for n in names), (
            f"{py.relative_to(PROJECT_ROOT)} imports transports"
        )


def test_core_and_providers_directories_exist() -> None:
    assert CORE.is_dir(), "core/ directory missing"
    assert PROVIDERS.is_dir(), "providers/ directory missing"
