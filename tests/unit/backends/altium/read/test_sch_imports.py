# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The reader imports no writer module and nothing under ``tests`` (capability altium-schematic-reader,
"Reader does not import the writer")."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import fenolite.backends.altium.read.sch as sch_package

READ = Path(sch_package.__file__).resolve().parent.parent
MODULES = sorted([*(READ / "sch").glob("*.py"), READ / "schlib.py"])
WRITERS = {"ascii", "binary", "schdoc", "schlib", "altsym", "layout", "project"}


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def problems(path: Path) -> list[str]:
    out: list[str] = []
    for name in sorted(_imports(path)):
        parts = name.split(".")
        if parts[0] == "tests" or (parts[0].startswith("_") and parts[0] != "__future__"):
            out.append(f"{path.name}: imports {name}")
            continue
        if parts[0] != "fenolite":
            if parts[0] not in sys.stdlib_module_names and parts[0] != "__future__":
                out.append(f"{path.name}: imports {name}, which is not in the standard library")
            continue
        allowed = name.startswith(("fenolite.core", "fenolite.backends.altium.read"))
        if not allowed:
            out.append(f"{path.name}: imports {name}")
        if parts[:3] == ["fenolite", "backends", "altium"] and len(parts) > 3 and parts[3] in WRITERS:
            out.append(f"{path.name}: imports the writer module {name}")
    return out


def test_reader_does_not_import_the_writer() -> None:
    assert len(MODULES) >= 10
    found = [problem for path in MODULES for problem in problems(path)]
    assert found == []


def test_sch_never_imports_schlib() -> None:
    for path in (READ / "sch").glob("*.py"):
        assert not any(name.startswith("fenolite.backends.altium.read.schlib") for name in _imports(path)), (
            path
        )


def test_the_check_sees_a_writer_import(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from fenolite.backends.altium import schdoc\nimport _altium_read\nimport numpy\n", encoding="utf-8"
    )
    assert problems(bad) == [
        "bad.py: imports _altium_read",
        "bad.py: imports fenolite.backends.altium",
        "bad.py: imports fenolite.backends.altium.schdoc",
        "bad.py: imports the writer module fenolite.backends.altium.schdoc",
        "bad.py: imports numpy, which is not in the standard library",
    ]
