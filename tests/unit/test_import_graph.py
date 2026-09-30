# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Package layering (openspec change c0002, capability package-layering).

Every package may import itself, ``core`` and the root ``fenolite`` namespace; other edges must be
listed in ALLOWED. The stdlib-only packages may not import third-party code at all; other packages
may import third-party code only inside functions or under ``try/except ImportError``.
"""

from __future__ import annotations

import ast
import sys
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
    "lens": {"model", "backends*"},
    "backends": {"model", "geometry", "backends*"},
    "backends.<x>": {"model", "geometry", "backends.base"},
    "libs": {"model", "geometry"},
    "checks": {"model", "geometry", "backends.base"},
    "analysis": {"model", "geometry", "backends.base"},
    "placement": {"model", "geometry", "backends.base"},
    "routing": {"model", "geometry"},
    "routing.plugins.<x>": {"routing", "backends.<same>"},
    "templates": {"model"},
    "render": {"model", "geometry", "backends*"},
    "exports": {"model", "geometry", "backends*"},
    "convert": {"model", "geometry", "backends*"},
    "verify": {"model", "geometry", "backends*"},
    "agent": {"cli"},
}
STDLIB_ONLY = {"core", "model", "geometry", "dsl"}


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


def _pattern(key: str) -> str:
    if key.startswith("backends.") and key not in ("backends.base", "backends.registry"):
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


def _violations() -> list[str]:
    problems: list[str] = []
    for path in _modules():
        source = _key(_dotted(path))
        rel = path.relative_to(SRC.parent).as_posix()
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
        ("routing.plugins.kicad", "backends.kicad", True),
        ("routing.plugins.kicad", "backends.altium", False),
        ("cli", "backends.kicad", True),
        ("agent", "model", False),
        ("dsl", "model", True),
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


def test_bare_import_without_extras() -> None:
    import subprocess

    code = "import fenolite, fenolite.cli.main, fenolite.cli.api, fenolite.cli.output, fenolite.core.io"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
