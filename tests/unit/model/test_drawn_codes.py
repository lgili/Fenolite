# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawn schematic codes (capability drawn-schematic, "Drawn schematic issue codes"; change c0276)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from fenolite.cli import explain
from fenolite.core.errors import ISSUE_CODE
from fenolite.model.drawn_connect import ISSUE_CODES

CODE = re.compile(r"drawn\.[a-z0-9-]+")
SRC = Path(__file__).resolve().parents[3] / "src" / "fenolite"
MODULES = (
    "model/drawn_connect.py",
    "backends/kicad/drawn.py",
    "lens/build.py",
    "lens/sync.py",
    "checks/drawn.py",
    "cli/cmd_build.py",
    "cli/cmd_sync.py",
)


def _emitted() -> set[str]:
    """Every ``drawn.*`` code that a module of the change passes as the first argument of a call."""
    found: set[str] = set()
    for module in MODULES:
        path = SRC / module
        if not path.is_file():
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            first = node.args[0]
            if (
                isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and CODE.fullmatch(first.value)
            ):
                found.add(first.value)
    return found


def test_closed_and_explained() -> None:
    """Scenario "Closed and explained"."""
    assert set(ISSUE_CODES) == {
        "drawn.netlist-differs", "drawn.symbol-missing", "drawn.part-unknown", "drawn.sheet-pin-unmatched",
        "drawn.sheet-unknown", "drawn.repeated-value-differs", "drawn.net-name-differs", "drawn.unit-missing",
        "drawn.dangling", "drawn.label-unconnected", "drawn.bus-member-unknown", "drawn.placements-ignored",
        "drawn.opaque-dropped", "drawn.frozen", "drawn.altium-repeat-flattened",
    }  # fmt: skip
    errors = {code for code, severity in ISSUE_CODES.items() if severity == "error"}
    assert errors == {
        "drawn.netlist-differs", "drawn.symbol-missing", "drawn.part-unknown", "drawn.sheet-pin-unmatched",
        "drawn.sheet-unknown", "drawn.repeated-value-differs",
    }  # fmt: skip
    assert {c for c, s in ISSUE_CODES.items() if s == "info"} == {
        "drawn.opaque-dropped",
        "drawn.frozen",
        "drawn.altium-repeat-flattened",
    }
    emitted = _emitted() - {"drawn.opaque-dropped", "drawn.altium-repeat-flattened"}  # the Altium phase (6.1)
    assert emitted <= set(ISSUE_CODES)
    assert emitted == set(ISSUE_CODES) - {"drawn.opaque-dropped", "drawn.altium-repeat-flattened"}
    for code in ISSUE_CODES:
        assert ISSUE_CODE.match(code)
        found = explain.explain(code)
        assert found is not None and found.meaning, code
