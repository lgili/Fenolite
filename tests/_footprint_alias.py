# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored source-instance alias input shared by independent unit/native c0342 controls."""

from pathlib import Path

from _importcode import copy_project

from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse


def alias_project(
    tmp_path: Path, alias: str = "Original:Mini_LED_THT_3mm", *, native_target: int = 10
) -> Path:
    project = copy_project(tmp_path, native_target=native_target)
    sheet = project.with_suffix(".kicad_sch")
    root = parse(sheet.read_text())
    changed = []
    replaced = 0
    for child in root.children:
        if not isinstance(child, Node) or child.name != "symbol":
            changed.append(child)
            continue
        props = {p.atoms()[0].value: p for p in child.nodes("property")}
        if props["Reference"].atoms()[1].value != "J1":
            changed.append(child)
            continue
        replaced += 1
        field = props["Footprint"]
        replacement = field.with_children(
            (
                field.children[0],
                Atom.string(alias),
                *(p for p in field.children[2:] if not isinstance(p, Node) or p.name != "hide"),
            )
        )
        changed.append(child.with_children(replacement if p is field else p for p in child.children))
    assert replaced == 1
    sheet.write_text(dumps(root.with_children(changed)))
    return project
