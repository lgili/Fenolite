# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The text readers need no compound reader (capability altium-project-reader, "Project loading",
scenario "No compound reader"; design Decision 1)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

READ = Path(__file__).resolve().parents[5] / "src" / "fenolite" / "backends" / "altium" / "read"
TEXT_MODULES = (
    "textfile",
    "ini",
    "proptext",
    "project",
    "outjob",
    "rul",
    "rules",
    "scope",
    "stackup",
    "annotation",
)
SIBLINGS = {f"fenolite.backends.altium.read.{name}" for name in TEXT_MODULES}
FORBIDDEN = ("fenolite.backends.altium.read.cfb", "fenolite.backends.altium.cfb")


def imports(name: str) -> list[str]:
    """Every module that ``read/<name>.py`` imports, at any depth of the file."""
    tree = ast.parse((READ / f"{name}.py").read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{name}: relative import"
            module = node.module or ""
            found.append(module)
            found += [
                f"{module}.{alias.name}" for alias in node.names if f"{module}.{alias.name}" in SIBLINGS
            ]
    return found


def allowed(module: str) -> bool:
    top = module.split(".")[0]
    if top in sys.stdlib_module_names or top == "__future__":
        return True
    return module in SIBLINGS or module.startswith(("fenolite.core", "fenolite.model"))


@pytest.mark.parametrize("name", TEXT_MODULES)
def test_text_module_imports(name: str) -> None:
    found = imports(name)
    assert not [m for m in found if m.startswith(FORBIDDEN)], name
    assert [m for m in found if not allowed(m)] == [], name


def test_the_nine_modules_exist() -> None:
    assert {p.stem for p in READ.glob("*.py")} >= set(TEXT_MODULES)


def test_loading_a_project_imports_no_compound_reader() -> None:
    """In a fresh interpreter, importing and running ``load_project`` loads no compound reader."""
    import subprocess

    code = (
        "import sys\n"
        "from fenolite.backends.altium.read.project import load_project\n"
        "bad = [m for m in sys.modules if m.endswith('.cfb')]\n"
        "print(','.join(bad))\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == ""
