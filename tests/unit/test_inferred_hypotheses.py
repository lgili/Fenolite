# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every ``INFERRED`` evidence of the package names the hypothesis it rests on (change c0200; the v1.0 rule
"no `INFERRED` without a hypothesis" of ``docs/roadmap.md``).

The test reads the source, not the replies: each call ``Evidence(Level.INFERRED, ...)`` must pass a non-empty
``hypotheses``. A call that is itself an argument of ``Evidence.combine`` only caps the level of the others,
whose hypotheses ``combine`` merges, so it is allowed. ``ALLOWED`` names the other exceptions, each with its
reason."""

from __future__ import annotations

import ast
from pathlib import Path

from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "fenolite"
ALLOWED = {
    ("lens/altium.py", "_written_claims"): "no Altium document among the written files: nothing is claimed",
}


def _is_inferred(node: ast.expr | None) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "INFERRED"
        and isinstance(node.value, ast.Name)
        and node.value.id == "Level"
    )


def _name(func: ast.expr) -> str:
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""


def _bare(tree: ast.AST) -> list[tuple[int, str]]:
    """The ``Evidence(Level.INFERRED)`` calls without hypotheses, outside ``combine``, with their function."""
    capped: set[int] = set()
    found: list[tuple[int, str]] = []
    scopes: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                scopes.setdefault(id(inner), node.name)
        if isinstance(node, ast.Call) and _name(node.func) == "combine":
            capped.update(id(arg) for arg in node.args)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _name(node.func) != "Evidence" or id(node) in capped:
            continue
        level = (
            node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "level"), None)
        )
        if not _is_inferred(level):
            continue
        cited = next((k.value for k in node.keywords if k.arg == "hypotheses"), None)
        if cited is None or (isinstance(cited, ast.Tuple) and not cited.elts):
            found.append((node.lineno, scopes.get(id(node), "")))
    return found


def _cited(tree: ast.AST) -> set[str]:
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("H-")
    }


def test_no_inferred_without_a_hypothesis() -> None:
    bare: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        rel = path.relative_to(PACKAGE).as_posix()
        for line, scope in _bare(ast.parse(path.read_text(encoding="utf-8"))):
            if (rel, scope) not in ALLOWED:
                bare.append(f"{rel}:{line} ({scope or 'module'})")
    assert bare == [], (
        "INFERRED evidence without a hypothesis: register one in docs/hypotheses.md and cite it"
    )


def test_allowed_exceptions_still_exist() -> None:
    """An exception whose call is gone is removed from ``ALLOWED``."""
    for rel, scope in ALLOWED:
        tree = ast.parse((PACKAGE / rel).read_text(encoding="utf-8"))
        assert any(found == scope for _, found in _bare(tree)), (rel, scope)


def test_the_new_rows_are_registered() -> None:
    """The hypotheses that change c0200 cites are rows of the register."""
    ids = {row.id for row in load_register(ROOT / "docs" / "hypotheses.md")}
    added = {
        "H-G-MODEL-OWN", "H-G-PLACE-RULES", "H-G-CATALOG", "H-G-IMP-TABLE", "H-G-VIEW-SCENE",
        "H-A-LAYOUT-REPLAY", "H-G-TIES", "H-G-CROSSINGS",
    }  # fmt: skip
    assert added <= ids
    cited = set().union(*(_cited(ast.parse(p.read_text(encoding="utf-8"))) for p in PACKAGE.rglob("*.py")))
    assert added <= cited
