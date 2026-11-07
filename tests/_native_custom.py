# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored native custom field source, including symmetric side/mirror controls."""

from pathlib import Path

from _custom_fields import original

from fenolite.backends.kicad.embed import _flip
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse


def source_project(folder: Path, target: int, side: str, rotation: int, visible: bool, styled: bool) -> Path:
    source = original(folder, rotation, target, visible=visible, styled=styled)
    board = source.with_suffix(".kicad_pcb")
    root = parse(board.read_text())
    (fp,) = root.nodes("footprint")
    if side == "bottom":
        at = fp.find("at")
        issues = []
        fp = _flip(fp, issues)
        assert not issues
        fp = fp.with_children(tuple(at if isinstance(c, Node) and c.name == "at" else c for c in fp.children))
    prop = next(p for p in fp.nodes("property") if p.atoms()[0].value == "Author")
    effects = prop.find("effects")
    assert effects is not None
    justify = effects.find("justify")
    values = tuple(a for a in justify.atoms() if a.value != "mirror") if justify else ()
    if side == "top":
        values = (*values, Atom.symbol("mirror"))
    children = tuple(c for c in effects.children if c is not justify)
    if values:
        children = (*children, Node(Atom.symbol("justify"), values))
    effect2 = effects.with_children(children)
    prop2 = prop.with_children(tuple(effect2 if c is effects else c for c in prop.children))
    fp2 = fp.with_children(tuple(prop2 if c is prop else c for c in fp.children))
    board.write_text(
        dumps(
            root.with_children(
                tuple(fp2 if isinstance(c, Node) and c.name == "footprint" else c for c in root.children)
            )
        )
    )
    return source


def tab_project(folder: Path, target: int, side: str, rotation: int, visible: bool, styled: bool) -> Path:
    source = source_project(folder, target, side, rotation, visible, styled)
    board = source.with_suffix(".kicad_pcb")
    tree = parse(board.read_text())
    (fp,) = tree.nodes("footprint")
    prop = next(p for p in fp.nodes("property") if p.atoms()[0].value == "Author")
    value = "First\tauthored\nSecond\tline"
    changed = prop.with_children(
        (prop.atoms()[0], Atom.string(value), *prop.children[2:], parse("(unlocked yes)"))
    )
    fp2 = fp.with_children(tuple(changed if c is prop else c for c in fp.children))
    board.write_text(dumps(tree.with_children(tuple(fp2 if c is fp else c for c in tree.children))))
    return source
