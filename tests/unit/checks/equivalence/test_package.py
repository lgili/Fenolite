# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The equivalence package (capability design-equivalence, "Equivalence package"): its modules, what
they import, its exports, and that its code holds no float and names no backend."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from fenolite.checks import equivalence

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = ROOT / "src" / "fenolite" / "checks" / "equivalence"
MODULES = ("__init__.py", "codes.py", "exclusions.py", "levels.py", "model.py", "norm.py")
ALLOWED = (
    "fenolite.core",
    "fenolite.model",
    "fenolite.geometry",
    "fenolite.backends.base",
    "fenolite.checks",
)
EXPORTS = (
    "LEVELS", "LEVEL_NAMES", "Tolerances", "Difference", "Excluded", "LevelResult", "EquivalenceReport",
    "compare_designs", "max_level", "difference_issues", "Rule", "Profile", "load_profiles", "select_profile",
    "EQUIVALENCE_CODES",
)  # fmt: skip
BACKENDS = ("kicad", "altium")
NO_IO = {"subprocess", "os", "shutil", "tempfile", "socket", "pathlib", "io"}


def _docstrings(tree: ast.AST) -> set[int]:
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                found.add(id(first.value))
    for node in ast.walk(tree):  # a string that follows an assignment documents it
        body = getattr(node, "body", None)
        if isinstance(body, list):
            for before, after in zip(body, body[1:], strict=False):
                if (
                    isinstance(before, ast.Assign | ast.AnnAssign)
                    and isinstance(after, ast.Expr)
                    and isinstance(after.value, ast.Constant)
                ):
                    found.add(id(after.value))
    return found


def problems(path: Path) -> list[str]:
    """What the module at ``path`` holds against the package's rules."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    documented = _docstrings(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            names = (
                [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            )
            if isinstance(node, ast.ImportFrom) and node.level:
                found.append(f"{path.name}:{node.lineno}: relative import")
            for name in names:
                top = name.split(".")[0]
                if top == "fenolite":
                    if not any(name == ok or name.startswith(ok + ".") for ok in ALLOWED):
                        found.append(f"{path.name}:{node.lineno}: imports {name}")
                elif top not in sys.stdlib_module_names:
                    found.append(f"{path.name}:{node.lineno}: imports {name}, which is not standard library")
                elif top in NO_IO:
                    found.append(f"{path.name}:{node.lineno}: imports {name}: the comparison reads no file")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float":
            found.append(f"{path.name}:{node.lineno}: float call")
        elif isinstance(node, ast.Name) and node.id == "float":
            found.append(f"{path.name}:{node.lineno}: float name")
        elif isinstance(node, ast.Constant) and isinstance(node.value, float):
            found.append(f"{path.name}:{node.lineno}: float literal")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in documented:
            if any(name in node.value.lower() for name in BACKENDS):
                found.append(f"{path.name}:{node.lineno}: names a backend in {node.value!r}")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            found.append(f"{path.name}:{node.lineno}: true division")
    return found


def test_modules() -> None:
    assert tuple(sorted(p.name for p in PACKAGE.glob("*.py"))) == MODULES


def test_layering_holds() -> None:
    found = [problem for name in MODULES for problem in problems(PACKAGE / name)]
    assert not found, "\n".join(found)


def test_the_check_finds_what_it_forbids(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(
        '"""A docstring may say kicad."""\n'
        "import os\nimport shapely\nfrom fenolite.backends.kicad import pcb\nfrom fenolite.cli import api\n"
        'X = float("1")\nY = 0.5\nZ = "the altium reader"\nW = 1 / 2\n',
        encoding="utf-8",
    )
    found = problems(bad)
    for expected in (
        "bad.py:2: imports os: the comparison reads no file",
        "bad.py:3: imports shapely, which is not standard library",
        "bad.py:4: imports fenolite.backends.kicad",
        "bad.py:5: imports fenolite.cli",
        "bad.py:6: float call",
        "bad.py:7: float literal",
        "bad.py:8: names a backend in 'the altium reader'",
        "bad.py:9: true division",
    ):
        assert expected in found, expected
    assert not [p for p in found if p.startswith("bad.py:1:")]


def test_exports() -> None:
    assert set(EXPORTS) <= set(equivalence.__all__)
    assert sorted(equivalence.__all__) == sorted(set(equivalence.__all__))
    for name in equivalence.__all__:
        assert getattr(equivalence, name) is not None
