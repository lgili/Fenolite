# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The outward height of a part: one function reads it from the footprint's bodies (change c0140)."""

from __future__ import annotations

import ast
from pathlib import Path

from fenolite.core.coords import Point
from fenolite.model.board import ComponentBody, FootprintInstance, outward_height

MM = 1_000_000
SRC = Path(__file__).resolve().parents[3] / "src" / "fenolite"


def _footprint(*bodies: ComponentBody) -> FootprintInstance:
    return FootprintInstance(
        id="fpi_00000000-0000-4000-8000-000000000001",
        component_id="cmp_00000000-0000-4000-8000-000000000001",
        lib_ref="Mini:Mini_R_0603",
        position=Point(0, 0),
        bodies=bodies,
    )


def _body(n: int, height: int, standoff: int = 0) -> ComponentBody:
    return ComponentBody(
        id=f"bdy_00000000-0000-4000-8000-00000000000{n}", kind="extruded", height=height, standoff=standoff
    )


def test_largest_known_body() -> None:
    footprint = _footprint(_body(1, 2 * MM), _body(2, 9 * MM, standoff=MM), _body(3, 3 * MM))
    assert outward_height(footprint) == 9 * MM


def test_standoff_is_not_read() -> None:
    assert outward_height(_footprint(_body(1, 4 * MM, standoff=3 * MM))) == 4 * MM


def test_no_known_height() -> None:
    assert outward_height(_footprint()) is None
    assert outward_height(_footprint(_body(1, 0))) is None


# The files of the placement rules: a part's height is reached only through ``outward_height``.
READERS = ("checks/placement.py", "cli/cmd_place.py", "cli/cmd_build.py")


def _iterates_bodies(node: ast.AST) -> bool:
    if isinstance(node, (ast.For, ast.comprehension)):
        return isinstance(node.iter, ast.Attribute) and node.iter.attr == "bodies"
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("max", "sorted", "list", "tuple")
    ):
        return any(isinstance(arg, ast.Attribute) and arg.attr == "bodies" for arg in node.args)
    return False


def test_one_reader() -> None:
    for name in READERS:
        tree = ast.parse((SRC / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            assert not (isinstance(node, ast.Attribute) and node.attr == "z_max"), f"{name} reads .z_max"
            assert not _iterates_bodies(node), f"{name}:{getattr(node, 'lineno', 0)} iterates over .bodies"
    placement = (SRC / "checks/placement.py").read_text(encoding="utf-8")
    assert "outward_height(" in placement
