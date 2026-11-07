# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 dated-parent/blank-child hierarchy, independent of external projects."""

from __future__ import annotations

from pathlib import Path

import _drawn_fonts

from fenolite.backends.kicad.sexpr import dumps, parse

DATE = "2026-11-02"


def dated_parent_blank_child(folder: Path, target: int) -> Path:
    original = _drawn_fonts.styled_hierarchy(folder, target=target)
    block = parse(f'(title_block (date "{DATE}"))')
    board = next(original.glob("*.kicad_pcb"))
    root = parse(board.read_text())
    board.write_text(
        dumps(
            root.with_children(
                (*[c for c in root.children if getattr(c, "name", "") != "title_block"], block)
            )
        )
    )
    for path in original.rglob("*.kicad_sch"):
        root = parse(path.read_text())
        children = [c for c in root.children if getattr(c, "name", "") != "title_block"]
        if path.stem == "drawn_full":
            children.append(block)
        path.write_text(dumps(root.with_children(children)))
    return original
