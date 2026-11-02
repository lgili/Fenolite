# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 hierarchical root rename, complete strict proof and input preservation (c0330)."""

from __future__ import annotations

from pathlib import Path

import _drawn_fonts
import pytest
from _fidelity import ALL_LEVELS, roundtrip, snapshot

from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse


def renamed_project(folder: Path, target: int) -> Path:
    original = _drawn_fonts.styled_hierarchy(folder, target=target)
    old, new = "drawn_full", "authored root"

    def project_name(node: Node) -> Node:
        children = tuple(project_name(item) if isinstance(item, Node) else item for item in node.children)
        if node.name == "project" and node.atoms() and node.atoms()[0].value == old:
            children = (Atom.string(new), *children[1:])
        return node.with_children(children)

    for path in original.rglob("*.kicad_sch"):
        path.write_text(dumps(project_name(parse(path.read_text(encoding="utf-8")))), encoding="utf-8")
    for path in tuple(original.iterdir()):
        if path.is_file() and path.stem == old:
            path.rename(path.with_stem(new))
    project = original / f"{new}.kicad_pro"
    assert project.is_file()
    return project


@pytest.mark.parametrize("target", (9, 10))
def test_safe_project_root_rename_proves_every_level(target: int, tmp_path: Path) -> None:
    project = renamed_project(tmp_path / "original", target)
    before = snapshot(project.parent)
    reply = roundtrip(project, tmp_path / "proof")
    assert reply.exit_code == 0, (reply.error, reply.result.get("differences"))
    assert reply.result["equivalent"] is True
    assert reply.result["differences"] == reply.result["accepted"] == []
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    assert all(row["status"] == "equal" for row in reply.result["levels"])
    copper = next(row for row in reply.result["levels"] if row["level"] == 5)
    assert copper["summary"]["strict"]["tracks"]["matched"] == 1
    assert snapshot(project.parent) == before
