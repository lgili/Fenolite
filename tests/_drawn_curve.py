# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 circular-pad controls with one routed segment and explicit teardrop settings."""

from __future__ import annotations

from pathlib import Path

import _drawn_fonts

from fenolite.backends.kicad.lowering import millimetres
from fenolite.backends.kicad.pro import read_project_text, write_project_text
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.backends.kicad.teardrops import emit
from fenolite.model.board import Teardrop


def curve_project(folder: Path, target: int, error_nm: int | None) -> Path:
    project = _drawn_fonts.original(folder, target=target)
    board = project / "font_probe.kicad_pcb"
    root = parse(board.read_text())
    footprint = root.nodes("footprint")[0]

    def circular(pad: Node) -> Node:
        children = [
            Atom.symbol("circle") if index == 2 else child
            for index, child in enumerate(pad.children)
            if not isinstance(child, Node) or child.name not in {"size", "roundrect_rratio", "teardrops"}
        ]
        children += [
            parse("(size 1 1)"),
            emit(Teardrop(True, 1_000_000, 2_000_000, 500_000, 1_000_000, False, 900_000, True, False)),
        ]
        return pad.with_children(children)

    changed = footprint.with_children(
        tuple(
            circular(child) if isinstance(child, Node) and child.name == "pad" else child
            for child in footprint.children
        )
    )
    board.write_text(
        dumps(root.with_children(tuple(changed if child is footprint else child for child in root.children)))
    )
    path = project / "font_probe.kicad_pro"
    data = read_project_text(path.read_text())
    rules = data["board"]["design_settings"]["rules"]
    if error_nm is None:
        rules.pop("max_error", None)
    else:
        rules["max_error"] = millimetres(error_nm)
    path.write_text(write_project_text(data))
    return project
