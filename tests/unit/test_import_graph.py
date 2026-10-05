# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Package layering (openspec changes c0002 and c0005, capability package-layering).

Every package may import itself, ``core`` and the root ``fenolite`` namespace; other edges must be
listed in ALLOWED. The stdlib-only packages may not import third-party code at all, statically or
dynamically; the one exception is ``geometry/boolean/_extra.py``, the loader of the ``geo`` extra,
whose ``GEO_MODULES`` must match that extra. Other packages may import third-party code only inside
functions or under ``try/except ImportError``.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "fenolite"
ANY = "*"

# source package key -> allowed target keys ("backends*" = backends and any backends.<x>)
ALLOWED: dict[str, set[str]] = {
    "root": {ANY},
    "cli": {ANY},
    "core": set(),
    "model": set(),
    "geometry": set(),
    "dsl": {"model"},
    "catalog": {"model"},
    "lens": {"model", "backends*"},
    "backends": {"model", "geometry", "backends*"},
    "backends.<x>": {"model", "geometry", "backends.base"},
    "libs": {"model", "geometry"},
    "checks": {"model", "geometry", "backends.base"},
    "analysis": {"model", "geometry", "backends.base"},
    "placement": {"model", "geometry", "backends.base"},
    "routing": {"model", "geometry"},
    "routing.plugins.<x>": {"routing", "model", "geometry", "backends.<same>"},
    "templates": {"model"},
    "render": {"model", "geometry", "backends*"},
    "exports": {"model", "geometry", "backends*"},
    "convert": {"model", "geometry", "backends*"},
    "verify": {"model", "geometry", "backends*"},
    "agent": {"cli"},
}
STDLIB_ONLY = {"core", "model", "geometry", "dsl", "catalog"}
EXTRA_LOADER = "geometry/boolean/_extra.py"
PYPROJECT = SRC.parents[1] / "pyproject.toml"


def _key(parts: list[str]) -> str:
    """Package key of a module given its dotted path below ``fenolite`` (package dirs vs modules)."""
    if not parts:
        return "root"
    head = parts[0]
    if (SRC / head).is_file() or (SRC / f"{head}.py").is_file() or head in ("__init__", "__main__"):
        return "root"
    if head == "backends" and len(parts) > 1:
        return f"backends.{parts[1]}" if (SRC / "backends" / parts[1]).is_dir() else f"backends.{parts[1]}"
    if head == "routing" and len(parts) > 2 and parts[1] == "plugins":
        return f"routing.plugins.{parts[2]}"
    return head


BACKENDS_TOP = ("backends.base", "backends.registry")  # top-level modules: the ``backends`` row


def _pattern(key: str) -> str:
    if key in BACKENDS_TOP:
        return "backends"
    if key.startswith("backends."):
        return "backends.<x>"
    if key.startswith("routing.plugins."):
        return "routing.plugins.<x>"
    return key


def _allowed(source: str, target: str) -> bool:
    if target in (source, "core", "root"):
        return True
    rules = ALLOWED[_pattern(source)]
    if ANY in rules:
        return True
    for rule in rules:
        if rule == "backends*" and (target == "backends" or target.startswith("backends.")):
            return True
        if rule == "backends.<same>" and target == "backends." + source.rsplit(".", 1)[-1]:
            return True
        if rule == target:
            return True
    return False


@dataclass(frozen=True)
class Edge:
    module: str
    line: int
    target: str  # dotted import name
    guarded: bool  # inside a function or a try/except ImportError


def _modules() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _dotted(path: Path) -> list[str]:
    rel = path.relative_to(SRC).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return parts


def _edges(path: Path) -> list[Edge]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parts = _dotted(path)
    package = parts if path.name == "__init__.py" else parts[:-1]
    edges: list[Edge] = []

    def visit(node: ast.AST, guarded: bool) -> None:
        for child in ast.iter_child_nodes(node):
            inner = guarded
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = True
            if isinstance(child, ast.Try) and any(
                isinstance(h.type, ast.Name) and h.type.id in ("ImportError", "ModuleNotFoundError")
                for h in child.handlers
            ):
                for stmt in child.body:
                    visit_stmt(stmt, True)
                for rest in (*child.handlers, *child.orelse, *child.finalbody):
                    visit(rest, guarded)
                continue
            visit_stmt(child, inner)

    def visit_stmt(node: ast.AST, guarded: bool) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                edges.append(Edge(str(path), node.lineno, alias.name, guarded))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = ["fenolite", *package[: len(package) - (node.level - 1)]]
                name = ".".join(base + ([node.module] if node.module else []))
            else:
                name = node.module or ""
            edges.append(Edge(str(path), node.lineno, name, guarded))
        visit(node, guarded or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))

    visit(tree, False)
    return edges


def _dynamic_imports(path: Path) -> list[int]:
    """Lines that call ``importlib.import_module``, ``import_module`` or ``__import__``."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call):
            func = node.func
            name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else func.id
                if isinstance(func, ast.Name)
                else ""
            )
            if name in ("import_module", "__import__"):
                lines.append(node.lineno)
    return lines


def _violations() -> list[str]:
    problems: list[str] = []
    for path in _modules():
        source = _key(_dotted(path))
        rel = path.relative_to(SRC.parent).as_posix()
        if source in STDLIB_ONLY and path.relative_to(SRC).as_posix() != EXTRA_LOADER:
            problems.extend(
                f"{rel}:{line}: dynamic import in {source}; only {EXTRA_LOADER} may load extras"
                for line in _dynamic_imports(path)
            )
        if _pattern(source) not in ALLOWED:
            problems.append(f"{rel}: package {source!r} is not in the layering table")
            continue
        for edge in _edges(path):
            top = edge.target.split(".")[0]
            if top == "fenolite":
                target = _key(edge.target.split(".")[1:])
                if not _allowed(source, target):
                    problems.append(f"{rel}:{edge.line}: {source} → {target} is not allowed")
            elif top not in sys.stdlib_module_names:
                if source in STDLIB_ONLY:
                    problems.append(f"{rel}:{edge.line}: {source} must be stdlib-only (imports {top})")
                elif not edge.guarded:
                    problems.append(f"{rel}:{edge.line}: unguarded third-party import {top}")
    return problems


def test_layering() -> None:
    problems = _violations()
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize(
    ("source", "target", "ok"),
    [
        ("model", "backends.kicad", False),
        ("backends.kicad", "backends.base", True),
        ("backends.kicad", "backends.altium", False),
        ("backends.specctra", "backends.base", True),
        ("backends.specctra", "geometry", True),
        ("backends.specctra", "backends.kicad", False),
        ("routing.plugins.kicad", "backends.kicad", True),
        ("routing.plugins.kicad", "backends.altium", False),
        ("routing.plugins.specctra", "backends.specctra", True),
        ("routing.plugins.specctra", "backends.kicad", False),
        ("routing.plugins.specctra", "backends.base", False),
        ("routing.plugins.kicad", "model", True),
        ("routing.plugins.kicad", "geometry", True),
        ("cli", "backends.kicad", True),
        ("agent", "model", False),
        ("dsl", "model", True),
        ("catalog", "model", True),
        ("lens", "backends.kicad", True),
    ],
)
def test_rule_table(source: str, target: str, ok: bool) -> None:
    assert _allowed(source, target) is ok


def test_detects_forbidden_edge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "fenolite"
    (fake / "model").mkdir(parents=True)
    (fake / "backends" / "kicad").mkdir(parents=True)
    (fake / "model" / "board.py").write_text("import fenolite.backends.kicad.pcb\nimport shapely\n")
    monkeypatch.setattr(sys.modules[__name__], "SRC", fake)
    problems = _violations()
    assert any("model → backends.kicad" in p for p in problems)
    assert any("must be stdlib-only (imports shapely)" in p for p in problems)


def test_registry_may_import_a_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_tree(
        tmp_path,
        "backends/registry.py",
        "def f():\n    import fenolite.backends.kicad.backend\nimport fenolite.backends.base\n",
    )
    (fake / "backends" / "base.py").write_text("import fenolite.model.design\n")
    monkeypatch.setattr(sys.modules[__name__], "SRC", fake)
    assert _violations() == []


def test_backend_may_not_import_another_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_tree(tmp_path, "backends/kicad/pcb.py", "import fenolite.backends.other.x\n")
    monkeypatch.setattr(sys.modules[__name__], "SRC", fake)
    problems = _violations()
    assert any("backends.kicad → backends.other" in p for p in problems), problems


def test_bare_import_without_extras() -> None:
    import subprocess

    code = "import fenolite, fenolite.cli.main, fenolite.cli.api, fenolite.cli.output, fenolite.core.io"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def _import_name(requirement: str) -> str:
    """Import name of a requirement string (distribution name normalised; same for every geo package)."""
    name = re.split(r"[\s<>=!~;\[]", requirement.strip(), maxsplit=1)[0]
    return name.lower().replace("-", "_")


def geo_modules_drift(pyproject_text: str, geo_modules: tuple[str, ...]) -> list[str]:
    extra = tomllib.loads(pyproject_text)["project"]["optional-dependencies"]["geo"]
    wanted = {_import_name(r) for r in extra}
    problems = [
        f"GEO_MODULES lacks {name!r} (in the geo extra)" for name in sorted(wanted - set(geo_modules))
    ]
    problems += [
        f"GEO_MODULES has {name!r}, not in the geo extra" for name in sorted(set(geo_modules) - wanted)
    ]
    return problems


def test_geo_modules_match_the_extra() -> None:
    from fenolite.geometry.boolean._extra import GEO_MODULES

    problems = geo_modules_drift(PYPROJECT.read_text(encoding="utf-8"), GEO_MODULES)
    assert not problems, "\n".join(problems)


def test_detects_geo_modules_drift() -> None:
    from fenolite.geometry.boolean._extra import GEO_MODULES

    text = PYPROJECT.read_text(encoding="utf-8").replace(
        'geo = ["shapely>=2.1", "pyclipper>=1.3"]', 'geo = ["shapely>=2.1", "pyclipper>=1.3", "rtree>=1.0"]'
    )
    assert geo_modules_drift(text, GEO_MODULES) == ["GEO_MODULES lacks 'rtree' (in the geo extra)"]


def _fake_tree(tmp_path: Path, rel: str, code: str) -> Path:
    fake = tmp_path / "fenolite"
    target = fake / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(code)
    return fake


def test_detects_function_level_import_in_geometry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_tree(tmp_path, "geometry/boolean/fallback.py", "def f():\n    import shapely\n")
    monkeypatch.setattr(sys.modules[__name__], "SRC", fake)
    problems = _violations()
    assert any("geometry/boolean/fallback.py" in p and "shapely" in p for p in problems), problems


def test_detects_dynamic_import_outside_the_loader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_tree(
        tmp_path, "geometry/polygon.py", 'import importlib\nimportlib.import_module("pyclipper")\n'
    )
    monkeypatch.setattr(sys.modules[__name__], "SRC", fake)
    problems = _violations()
    assert any(
        "geometry/polygon.py" in p and "only geometry/boolean/_extra.py may load extras" in p
        for p in problems
    ), problems


def test_loader_may_import_dynamically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_tree(tmp_path, EXTRA_LOADER, 'import importlib\nimportlib.import_module("shapely")\n')
    monkeypatch.setattr(sys.modules[__name__], "SRC", fake)
    assert _violations() == []


def test_geometry_imports_without_extras() -> None:
    import subprocess

    code = (
        "import sys; sys.modules['shapely'] = None; sys.modules['pyclipper'] = None\n"
        "import fenolite.geometry, fenolite.geometry.boolean"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
